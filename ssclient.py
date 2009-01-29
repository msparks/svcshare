#!/usr/bin/python
import logging
import os
import random
import re
import socket
import sys
import time

from svcshare.clientcontrol import clientcontrol
from svcshare import connectionproxy
from svcshare import feedwatcher
from svcshare import irclib
from svcshare import jobqueue
from svcshare import peertracker

import config

__version__ = "0.1"

cur_count = 0
start_bytes_transferred = 0
total_bytes_transferred = 0
start_time = 0
bot = None
svcclient = None
proxy = None
feeds = None
tracker = None


def sighup_handler(signum, frame):
  print "sighup received, ignoring"


def sigint_handler(signum, frame):
  print "sigint received, exiting"
  sys.exit(0)


def init_signals():
  if sys.platform != "darwin" and sys.platform != "linux2":
    return

  import signal
  signal.signal(signal.SIGHUP, sighup_handler)
  signal.signal(signal.SIGINT, sigint_handler)


class Bot(irclib.SimpleIRCClient):
  def __init__(self, server, port, nick, channel):
    irclib.SimpleIRCClient.__init__(self)
    self.server = server
    self.port = port
    self.channel = channel
    self.nick = nick
    self.connect(server, port, nick)
    self._nick_counter = 1

  def on_welcome(self, connection, event):
    self._nick_counter = 1
    if irclib.is_channel(self.channel):
      connection.join(self.channel)

  def on_disconnect(self, connection, event):
    time.sleep(30)
    self.connect(self.server, self.port, self.nick)

  def on_pubmsg(self, connection, event):
    if event.target() != self.channel:
      return

    msg = event.arguments()[0]
    m = re.search(r"^\.ss (.+?) (.+?)\s*$", msg)

    # .usenet
    if msg == ".usenet" and proxy.num_active() > 0:
      active = proxy.num_active()
      connection.privmsg(event.target(), "%d connections active" % active)

    # .ss version
    if msg == ".ss version":
      connection.privmsg(event.target(), "svcshare version %s" % __version__)

    if not m:
      return

    target, command = m.group(1), m.group(2)
    command = command.lower()
    if target.lower() != config.NICK.lower():
      return

    # pause
    if command == "pause":
      if svcclient:
        if svcclient.pause():
          connection.privmsg(event.target(), "paused downloader")
        else:
          connection.privmsg(event.target(), "failed to pause downloader")
      else:
        connection.privmsg(event.target(), "pausing only proxy")
      proxy.pause()

    # resume/continue
    elif command == "resume" or command == "continue":
      if svcclient:
        if svcclient.resume():
          connection.privmsg(event.target(), "resumed downloader")
        else:
          connection.privmsg(event.target(), "failed to resume downloader")
      else:
        connection.privmsg(event.target(), "resuming only proxy")
      proxy.resume()

    # eta
    elif command == "eta":
      if svcclient:
        eta_msg = svcclient.eta()
        if eta_msg:
          connection.privmsg(event.target(), eta_msg)
      else:
        connection.privmsg(event.target(),
                           "downloader does not provide queue access")


  def on_nicknameinuse(self, connection, event):
    # When nick is in use, append a number to the base nick.
    rand = random.randint(0, 9)
    time.sleep(1)
    self._nick_counter += 1
    connection.nick("%s%d" % (self.nick, self._nick_counter))

  def on_ctcp(self, connection, event):
    args = event.arguments()
    ctcp_type = args[0]
    nick = event.source().split("!")[0]
    if ctcp_type == "SS_PING":
      logging.debug("sending SS_PONG to %s" % nick)
      connection.ctcp("SS_PONG", nick, " ".join(args[1:]))
    elif ctcp_type == "SS_PONG":
      logging.debug("received pong from %s" % nick)
      tracker.update(nick)

  def connection_change(self, cur_count, elapsed, transferred):
    if cur_count == 0:
      min = elapsed / 60
      sec = elapsed % 60
      mb = transferred / 1024 / 1024
      rate = (transferred / 1024) / elapsed

      msg = ("%s has 0 connections. [tx: %d MB in %dm%ds (%d KB/s)]" %
             (config.NICK, mb, min, sec, rate))
      self.connection.privmsg(self.channel, msg)
    else:
      self.connection.privmsg(self.channel,
                              "%s has %d connections" %
                              (config.NICK, cur_count))
    self.connection.ctcp("SS_CONNUPDATE", self.channel,
                         "%s %d" % (config.NICK, cur_count))


def ping():
  tracker.clear()
  bot.connection.ctcp("SS_PING", bot.channel, str(int(time.time())))


def check_connections():
  global cur_count
  global start_time
  global start_bytes_transferred
  global total_bytes_transferred

  total_bytes_transferred = proxy.transferred()
  active = proxy.num_active()
  pl = active == 1 and "connection" or "connections"

  if active != cur_count:
    print "%s has %d %s" % (config.NICK, active, pl)

    # if establishing new connections, record start time
    if cur_count == 0:
      start_time = int(time.time())
      start_bytes_transferred = total_bytes_transferred

    # if closing all connections, calculate elapsed time
    elapsed = 0
    tx = 0
    if active == 0:
      elapsed = int(time.time()) - start_time
      tx = total_bytes_transferred - start_bytes_transferred

    cur_count = active

    # notify
    bot.connection_change(cur_count, elapsed, tx)


def check_queue():
  queue_size = svcclient.queue_size()
  if queue_size is None:
    return
  paused = svcclient.is_paused()
  bot.connection.privmsg(bot.channel, "queue: %s, paused: %s" %
                         (svcclient.queue_size(), paused and True or False))


def check_feeds():
  for url in config.NEWZBIN_FEEDS:
    if not url:
      continue
    logging.debug("Refreshing %s" % url)
    entries = feeds.poll_feed(url)
    for entry in entries:
      id = feeds.extract_nzbid(entry.id)
      if enqueue(id):
        feeds.mark_old(entry)
        logging.info("Queued: %s (%s)" % (entry.title, id))
    feeds.save()


def enqueue(nzbid):
  if svcclient:
    return svcclient.enqueue(nzbid)
  else:
    return False


def ircloop():
  jobs = jobqueue.JobQueue()
  jobs.add_job("conn", time.time() + 5)
  #jobs.add_job("ping", time.time() + 5)
  jobs.add_job("feed", time.time() + config.FEED_POLL_PERIOD)

  while True:
    bot.ircobj.process_once(timeout=0.4)

    while jobs.has_next_job():
      nj = jobs.next_job()

      if nj == "ping":
        jobs.add_job(nj, time.time() + 60)
        ping()
      elif nj == "conn":
        jobs.add_job(nj, time.time() + 10)
        check_connections()
      elif nj == "feed":
        jobs.add_job(nj, time.time() + config.FEED_POLL_PERIOD)
        check_feeds()


def main():
  global bot
  global svcclient
  global proxy
  global feeds
  global tracker

  irclib.DEBUG = 0

  # set up logging
  _fmt = "%(asctime)s [%(levelname)s] %(message)s"
  logging.basicConfig(level=logging.DEBUG,
                      format=_fmt)

  # initialize signals
  init_signals()

  # set up connection proxy
  _local_addr = (config.LOCAL_HOST, config.LOCAL_PORT)
  _target_addr = (config.TARGET_HOST, config.TARGET_PORT)
  proxy = connectionproxy.ConnectionProxyServer(_local_addr, _target_addr)
  proxy.start()

  # set up access to service client
  if config.SERVICE_CLIENT != "proxy":
    svcclient = clientcontrol.ClientControl(config.SERVICE_CLIENT,
                                            config.SERVICE_CLIENT_URL)

  # set up feedwatcher
  _path = os.path.normpath(os.path.join(os.path.dirname(sys.argv[0]),
                                        config.FEED_DATA_FILE))
  feeds = feedwatcher.Feedwatcher(_path)

  # set up peer tracker (keep track of other bots)
  tracker = peertracker.PeerTracker()

  while True:
    try:
      bot = Bot(config.BOT_IRCSERVER, config.BOT_IRCPORT,
                config.BOT_NICK, config.BOT_CHANNEL)
    except irclib.ServerConnectionError, x:
      print "exception: %s" % x
      time.sleep(60)
      continue
    except Exception, x:
      # any other exception
      print x
      time.sleep(60)

    print "Connected, starting main loop"
    try:
      ircloop()
    except irclib.IRCError:
      pass
    print "Exited main loop"
    time.sleep(30)


if __name__ == "__main__":
    main()
