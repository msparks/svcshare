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
from svcshare import electiontracker
from svcshare import feedwatcher
from svcshare import irclib
from svcshare import jobqueue
from svcshare import peertracker

import config

__version__ = "0.2.1"

cur_count = 0
start_bytes_transferred = 0
total_bytes_transferred = 0
start_time = 0
bot = None
svcclient = None
proxy = None
feeds = None
tracker = None
election = None
jobs = None
state = None


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


class SvcshareState(object):
  def __init__(self):
    self._force_end_bytes = proxy.transferred()

  def force(self, allotment=0):
    self._force_end_bytes = proxy.transferred() + allotment * 1024 * 1024
    svcclient.resume()

  def forced_diff(self):
    """Get the remaining forced allotment in MB
    """
    diff = self._force_end_bytes - proxy.transferred()
    if diff < 0:
      diff = 0
    return diff / 1024.0 / 1024.0

  def unforce(self):
    """Clear forced state
    """
    self._force_end_bytes = proxy.transferred()


class Bot(irclib.SimpleIRCClient):
  def __init__(self, server, port, nick, channel):
    irclib.SimpleIRCClient.__init__(self)
    self.server = server
    self.port = port
    self.channel = channel
    self.nick = nick
    self.connect(server, port, nick)
    self._nick_counter = 1

  def on_nicknameinuse(self, connection, event):
    # When nick is in use, append a number to the base nick.
    rand = random.randint(0, 9)
    time.sleep(1)
    self._nick_counter += 1
    connection.nick("%s%d" % (self.nick, self._nick_counter))

  def on_welcome(self, connection, event):
    self.nick = event.target()
    self._nick_counter = 1
    logging.debug("bot nick is %s" % self.nick)
    if irclib.is_channel(self.channel):
      connection.join(self.channel)

  def on_disconnect(self, connection, event):
    time.sleep(30)
    self.connect(self.server, self.port, self.nick)

  def on_join(self, connection, event):
    nick = event.source().split("!")[0]
    chan = event.target()
    logging.debug("JOIN %s -> %s" % (nick, chan))

    if nick == self.nick and chan == self.channel:
      logging.debug("Sending SS_ANNOUNCE")
      connection.ctcp("SS_ANNOUNCE", chan)

  def on_part(self, connection, event):
    nick = event.source().split("!")[0]
    chan = event.target()
    logging.debug("PART %s <- %s" % (nick, chan))

    if chan == self.channel:
      tracker.remove(nick)
      logging.debug("current peers: %s" % str(tracker.peers()))

  def on_quit(self, connection, event):
    nick = event.source().split("!")[0]
    logging.debug("QUIT %s" % nick)
    tracker.remove(nick)
    logging.debug("current peers: %s" % str(tracker.peers()))

  def on_nick(self, connection, event):
    old_nick = event.source().split("!")[0]
    nick = event.target()
    if old_nick == self.nick:
      self.nick = event.target()
      logging.debug("new bot nick is %s" % self.nick)
    tracker.rename(old_nick, nick)

  def on_pubmsg(self, connection, event):
    if event.target() != self.channel:
      return

    nick = event.source().split("!")[0]
    msg = event.arguments()[0]
    m = re.search(r"^\.ss\s+(.+?)\s+(.+?)(?: (.+?))?\s*$", msg)

    # .usenet
    if msg == ".usenet" and proxy.num_active() > 0:
      self.announce_status()

    # .ss version
    if msg == ".ss version":
      connection.privmsg(event.target(),
                         "svcshare version %s" % version_string())

    if not m:
      return

    target, command, ext = m.group(1), m.group(2), m.group(3)
    command = command.lower()
    if target.lower() != config.NICK.lower():
      return

    # pause
    if command == "pause":
      if svcclient.pause():
        state.unforce()
        connection.privmsg(event.target(), "Paused client.")
      else:
        connection.privmsg(event.target(),
                           "Paused proxy. Failed to pause client.")

    # resume: start an election (old resume)
    elif command == "resume" or command == "continue" or command == "election":
      start_election()
      connection.privmsg(event.target(), "Election started.")

    # eta
    elif command == "eta":
      self.announce_status()

    # force: forcefully start downloading by yielding peers
    elif command == "force":
      try:
        min_mb = int(ext)
      except TypeError:
        min_mb = 0
      except ValueError:
        min_mb = 0
      logging.debug("force for a minimum of %d MB" % min_mb)
      connection.privmsg(event.target(),
                         "Resuming. Forced allotment: %d MB." % min_mb)
      self.send_yield()
      state.force(allotment=min_mb)

    # enqueue
    elif nick == config.NICK and (command == "enq" or command == "enqueue"):
      ids = ext.split(" ")
      qd_ids = []
      for id in ids:
        if id and svcclient.enqueue(id):
          qd_ids.append(id)
      if qd_ids:
        connection.privmsg(event.target(), "Queued: %s" % ", ".join(qd_ids))
      else:
        connection.privmsg(event.target(), "Failed to queue items.")

  def on_ctcp(self, connection, event):
    args = event.arguments()
    ctcp_type = args[0]
    nick = event.source().split("!")[0]

    # SS_ANNOUNCE (announce presence)
    if ctcp_type == "SS_ANNOUNCE":
      tracker.add(nick)  # add newcomer
      logging.debug("sending SS_ACK to %s" % nick)
      connection.ctcp("SS_ACK", nick, " ".join(args[1:]))
      logging.debug("current peers: %s" % str(tracker.peers()))

    # SS_ACK (acknowledge presence)
    elif ctcp_type == "SS_ACK":
      tracker.add(nick)  # we're the newcomer, adding existing peers
      logging.debug("received ack from %s" % nick)
      logging.debug("current peers: %s" % str(tracker.peers()))

    # SS_STARTELECTION
    elif ctcp_type == "SS_STARTELECTION":
      queue_size = svcclient and svcclient.queue_size() or 0
      if state.forced_diff() > 0:
        # we're in forced state, ignore election
        logging.debug("election request from %s while in forced state" % nick)
      else:
        logging.debug("election request from %s, sending queue size: %d MB" %
                      (nick, queue_size))
        connection.ctcp("SS_QUEUESIZE", nick, "%s" % queue_size)

    # SS_QUEUESIZE (during an election)
    elif ctcp_type == "SS_QUEUESIZE" and election:
      try:
        size = int(args[1])
      except ValueError:
        size = 0
      except IndexError:
        logging.debug("SS_QUEUESIZE from %s received, but no arg?" % nick)
        return

      logging.debug("%s reported queue size: %d MB" % (nick, size))
      election.update(nick, size)
      jobs.add_job("election", time.time())

    # SS_YIELD (give up the service)
    elif ctcp_type == "SS_YIELD":
      if not svcclient.is_paused():
        connection.privmsg(self.channel, "Yield request received. Pausing.")
        state.unforce()
        svcclient.pause()

  def connection_change(self, cur_count, elapsed, transferred):
    if cur_count == 0:
      min = elapsed / 60
      sec = elapsed % 60
      mb = transferred / 1024 / 1024
      rate = (transferred / 1024) / elapsed

      msg = ("0 connections. [%d MB in %dm%ds (%d KB/s)]" %
             (mb, min, sec, rate))
      self.connection.privmsg(self.channel, msg)
    else:
      self.announce_status()
    self.connection.ctcp("SS_CONNUPDATE", self.channel,
                         "%s %d" % (config.NICK, cur_count))

  def send_yield(self):
    self.connection.ctcp("SS_YIELD", self.channel)

  def announce_status(self):
    active = proxy.num_active()
    conn_str = "%d conn" % active
    forced_diff = state.forced_diff()
    if forced_diff:
      forced_str = ", force: %d MB" % forced_diff
    else:
      forced_str = ""

    eta_msg = svcclient.eta() or "Failed to retrieve queue status"
    self.connection.privmsg(self.channel, "%s (%s%s)" %
                            (eta_msg, conn_str, forced_str))


def check_connections():
  global cur_count
  global start_time
  global start_bytes_transferred
  global total_bytes_transferred

  total_bytes_transferred = proxy.transferred()
  active = proxy.num_active()

  if active != cur_count:
    pl = active == 1 and "connection" or "connections"

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
  if not svcclient.queue_size() or not svcclient.is_paused():
    return

  # we have a queue and we're currently paused. Call an election.
  start_election()


def start_election():
  global election
  logging.debug("starting election")
  election = electiontracker.Election(bot)
  election.start()
  jobs.add_job("election", time.time() + 20)


def check_election():
  global election
  if not election or not svcclient:
    return

  # still waiting for results?
  deadline = election.start_time() + 20
  now = time.time()
  if election.peers() != tracker.peers() and now < deadline:
    return

  # did we get all results?
  if election.peers() != tracker.peers():
    diff = list(set(tracker.peers()) - set(election.peers()))
    logging.debug("election failed. Failed to receive responses from: %s" %
                  ", ".join(diff))
    return

  # all results in
  winner = bot.nick
  queue_size = svcclient.queue_size()

  results = election.results()
  for peer in results:
    size = results[peer]
    if size > 0 and size < queue_size:
      winner = peer
      queue_size = size

  logging.debug("election winner: %s, queue size: %d MB" % (winner, queue_size))

  # did we win?
  if winner == bot.nick and queue_size > 0:
    bot.connection.privmsg(bot.channel,
                           "Election won. Queue size: %d MB." % queue_size)
    logging.debug("winner, sending force yield")
    bot.send_yield()
    logging.debug("resuming client")
    svcclient.resume()
  elif winner == bot.nick and queue_size == 0:
    bot.connection.privmsg(bot.channel,
                           "Election won, but queue is empty. Ignoring.")
    logging.debug("won the election, but queue size is 0. ignoring.")

  election = None


def check_feeds():
  logging.debug("Refreshing feeds...")
  for url in config.NEWZBIN_FEEDS:
    if not url:
      continue
    entries = feeds.poll_feed(url)
    for entry in entries:
      id = feeds.extract_nzbid(entry.id)
      if svcclient.enqueue(id):
        feeds.mark_old(entry)
        logging.info("Queued: %s (%s)" % (entry.title, id))
    feeds.save()


def ircloop():
  jobs.add_job("conn", time.time() + 5)
  jobs.add_job("feed", time.time() + config.FEED_POLL_PERIOD)
  jobs.add_job("queue", time.time() + 10)

  while True:
    bot.ircobj.process_once(timeout=0.4)

    while jobs.has_next_job():
      nj = jobs.next_job()

      if nj == "conn":
        jobs.add_job(nj, time.time() + 10)
        check_connections()
      elif nj == "feed":
        jobs.add_job(nj, time.time() + config.FEED_POLL_PERIOD)
        check_feeds()
      elif nj == "election":
        check_election()
      elif nj == "queue":
        jobs.add_job("queue", time.time() + 1800)
        check_queue()


def version_string():
  git_path = os.path.normpath(os.path.join(os.path.dirname(sys.argv[0]),
                                           ".git/refs/heads/master"))
  if not os.path.exists(git_path):
    return __version__

  fd = open(git_path, "r")
  id = fd.read()
  fd.close()

  return "%s (%s)" % (__version__, id[0:5])


def main():
  global bot
  global feeds
  global jobs
  global proxy
  global state
  global svcclient
  global tracker

  irclib.DEBUG = 0

  # set up logging
  _fmt = "%(asctime)s [%(levelname)s] %(message)s"
  logging.basicConfig(level=logging.DEBUG,
                      format=_fmt)

  # initialize signals
  init_signals()

  # job queue
  jobs = jobqueue.JobQueue()

  # set up connection proxy
  _local_addr = (config.LOCAL_HOST, config.LOCAL_PORT)
  _target_addr = (config.TARGET_HOST, config.TARGET_PORT)
  proxy = connectionproxy.ConnectionProxyServer(_local_addr, _target_addr)
  proxy.start()

  # state
  state = SvcshareState()

  # set up access to service client
  svcclient = clientcontrol.ClientControl(proxy,
                                          config.SERVICE_CLIENT,
                                          config.SERVICE_CLIENT_URL)
  svcclient.pause()

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
      logging.debug("exception: %s" % x)
      time.sleep(60)
      continue
    except Exception, x:
      # any other exception
      print x
      time.sleep(60)

    try:
      ircloop()
    except irclib.IRCError:
      pass
    logging.info("Exited main loop")
    time.sleep(30)


if __name__ == "__main__":
    main()
