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
from svcshare import irclib
from svcshare import jobqueue
from svcshare import network
from svcshare import peertracker
from svcshare import reporter

import config

__version__ = "0.3.6"
_version_string = None

cur_count = 0
start_bytes_transferred = 0
total_bytes_transferred = 0
start_time = 0
bot = None
svcclient = None
proxy = None
tracker = None
election = None
jobs = None
state = None

last_major_election = 0  # epoch of last major election
last_queue_size = 0


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


class BotMsgCallbacks(object):
  def msg_election(self, bot, event, target, ext):
    if state.halted():
      bot.send_halt_error(target)
      return

    queue_size = svcclient.queue_size()
    start_election(queue_size, major=True)
    bot.connection.privmsg(target, "Election started.")
  msg_resume = msg_election
  msg_continue = msg_election

  def msg_enqueue(self, bot, event, target, ext):
    # verify caller is owner
    if event.source().split("!")[0] != config.NICK:
      return

    if not ext:
      return

    ids = ext.split(" ")
    qd_ids = []
    for id in ids:
      if id and svcclient.enqueue(id):
        qd_ids.append(id)
    if qd_ids:
      bot.connection.privmsg(target, "Queued: %s" % ", ".join(qd_ids))
      jobs.add_job(check_queue, delay=10)
    else:
      bot.connection.privmsg(target, "Failed to queue items.")
  msg_enq = msg_enqueue

  def msg_force(self, bot, event, target, ext):
    try:
      queue_size = svcclient.queue_size()
      min_mb = int(ext)
      min_mb = min_mb < queue_size and min_mb or queue_size
    except (TypeError, ValueError):
      min_mb = 0
    logging.debug("force for a minimum of %d MB" % min_mb)
    bot.connection.privmsg(target,
                           "Resuming. Forced allotment: %d MB." % min_mb)
    bot.send_yield()
    if state.halted():
      logging.debug("unhalting")
      state.unhalt()
    state.force(allotment=min_mb)

  def msg_halt(self, bot, event, target, ext):
    try:
      minutes = int(ext)
    except (TypeError, ValueError):
      minutes = 0
      time_str = "indefinitely"
    else:
      time_str = "for %d minutes" % minutes
    logging.debug("halting %s" % time_str)
    bot.connection.privmsg(target, "Halting %s." % time_str)
    svcclient.pause()
    state.unforce()
    state.halt(minutes)

  def msg_unhalt(self, bot, event, target, ext):
    if state.halted():
      state.unhalt()
      jobs.add_job(check_queue)
      logging.debug("unhalted")
      bot.connection.privmsg(target, "Unhalted.")
    else:
      bot.connection.privmsg(target, "System was not in halted state.")

  def msg_pause(self, bot, event, target, ext):
    if svcclient.pause():
      bot.connection.privmsg(target, "Paused client.")
    else:
      bot.connection.privmsg(target,
                             "Paused proxy. Failed to pause client.")
    state.unforce()

  def msg_status(self, bot, event, target, ext):
    bot.announce_status(target)
  msg_eta = msg_status

  def msg_version(self, bot, event, target, ext):
    bot.connection.privmsg(target, "svcshare version %s" % _version_string)


class BotCtcpCallbacks(BotMsgCallbacks):
  def ctcp_ack(self, bot, event, nick, args):
    """Presence acknowledgement"""
    tracker.add(nick)  # we're the newcomer, adding existing peers
    logging.debug("received ack from %s" % nick)
    logging.debug("current peers: %s" % ", ".join(tracker.peers()))

  def ctcp_announce(self, bot, event, nick, args):
    """Presence announcement"""
    tracker.add(nick)  # add newcomer
    logging.debug("sending SS_ACK to %s" % nick)
    bot.connection.ctcp("SS_ACK", nick, " ".join(args[1:]))
    logging.debug("current peers: %s" % ", ".join(tracker.peers()))

  def ctcp_connstat(self, bot, event, nick, args):
    """Request for connections status"""
    bot.send_connupdate(nick)

  def ctcp_connupdate(self, bot, event, nick, args):
    """Connections update after a CONNSTAT"""
    if " " in args[1]:
      owner_nick, count = args[1].split(" ")
    else:
      count = args[1]

    try:
      count = int(count)
    except ValueError:
      logging.debug("received bogus data for SS_CONNUPDATE from %s: %s" %
                    (nick, args[2]))
      return
    except IndexError:
      logging.debug("received no data for SS_CONNUPDATE from %s" % nick)
      logging.debug("args: %s" % str(args))
      return

    if election:
      logging.debug("%s reported %d connections" % (nick, count))
      election.update(nick, count)
      jobs.add_job(check_election)
    elif not election and count == 0 and svcclient.queue_size():
      delay = random.randint(180, 300)
      jobs.add_job(check_queue, delay=delay, name="autoresume_check")
      logging.debug("checking queue in %d seconds" % delay)

  def ctcp_queuesize(self, bot, event, nick, args):
    """Queue size request during an election"""
    if not election:
      return

    try:
      size = float(args[1])
    except ValueError:
      size = 0
    except IndexError:
      logging.debug("SS_QUEUESIZE from %s received, but no arg?" % nick)
      return

    logging.debug("%s reported queue size: %.2f MB" % (nick, size))
    election.update(nick, size)
    jobs.add_job(check_election)

  def ctcp_startelection(self, bot, event, nick, args):
    """Start an election"""
    queue_size = svcclient and svcclient.queue_size() or 0
    if state.forced():
      # we're in forced state, ignore election
      logging.debug("election request from %s while in forced state" % nick)
    elif state.halted():
      logging.debug("election request from %s while halted, sending 0 MB" %
                    nick)
      bot.connection.ctcp("SS_QUEUESIZE", nick, "0")
    else:
      logging.debug("election request from %s, sending queue size: %f MB" %
                    (nick, queue_size))
      bot.connection.ctcp("SS_QUEUESIZE", nick, "%f" % queue_size)

  def ctcp_yield(self, bot, event, nick, args):
    """Yield request"""
    if not svcclient.is_paused():
      bot.connection.privmsg(bot.channel, "Yield request received. Pausing.")
      svcclient.pause()
      state.unforce()
    if jobs.remove_job("autoresume_check"):
        logging.debug("removed autoresume job")


class BotCallbacks(BotCtcpCallbacks):
  pass


class SvcshareState(object):
  def __init__(self):
    self._force_end_bytes = proxy.stats().totalTransferred()
    self._halt_end_time = time.time()
    self.last_force_state = False

  def force(self, allotment=0):
    self._force_end_bytes = (proxy.stats().totalTransferred() +
                             allotment * 1024 * 1024)
    svcclient.resume()

  def force_diff(self):
    """Get the remaining forced allotment in MB
    """
    diff = self._force_end_bytes - proxy.stats().totalTransferred()
    if diff < 0:
      diff = 0
    return diff / 1024.0 / 1024.0

  def forced(self):
    """Determine if a force is in effect.

    Returns:
      True if force is in effect.
    """
    return (self.force_diff() > 0)

  def unforce(self):
    """Clear forced state
    """
    self._force_end_bytes = proxy.stats().totalTransferred()

  def halt(self, minutes=0):
    """Put system into a halted state.

    Args:
      minutes: how long to maintain halted state (0 = until manually unhalted)
    """
    if minutes > 0:
      self._halt_end_time = time.time() + minutes * 60
      logging.debug("halted for %d minutes" % minutes)
    else:
      logging.debug("halted")
      self._halt_end_time = 0

  def halt_diff(self):
    """Seconds left before halt ends.

    Returns:
      seconds value or None if permanent halt is in effect
    """
    if self._halt_end_time == 0:
      return None
    else:
      diff = self._halt_end_time - time.time()
      if diff < 0:
        return 0
      return diff

  def halted(self):
    """Determine if system is in halted state.

    Returns:
      True if system is halted, False otherwise
    """
    d = self.halt_diff()
    return (d is None or d > 0)

  def unhalt(self):
    """Cancel current halt state.
    """
    self._halt_end_time = time.time()
    logging.debug("unhalted")


class NetworkReactor(network.Network.Notifiee):
  def __init__(self):
    network.Network.Notifiee.__init__(self)
    self._logger = logging.getLogger('NetworkReactor')

  def onStatus(self, status):
    self._logger.info('Status is: %s.' % status)

  def onJoinEvent(self, name):
    self._logger.info('%s joined the network.' % name)

  def onLeaveEvent(self, name):
    self._logger.info('%s left the network.' % name)

  def onControlMessage(self, name, target, type, message=None):
    self._logger.debug('[Control message] <%s:%s> [%s] %s' % (name, target,
                                                              type, message))

  def onChatMessage(self, name, target, message):
    self._logger.debug('<%s:%s> %s' % (name, target, message))


class Bot(irclib.SimpleIRCClient):
  def __init__(self, network, server, port, nick, channel, cb, ssl=False):
    irclib.SimpleIRCClient.__init__(self)
    self._network = network

    self.server = server
    self.port = port
    self.nick = nick
    self.channel = channel
    self.cb = cb
    self.ssl = ssl

    self._nick_counter = 1
    self._first_time = True
    self._unhalt_on_connect = True
    self._reconnect_delay = 15
    self._rejoin_delay = 5
    self._logger = logging.getLogger('Bot')

  def _addNetworkEvent(self, method_name, *args):
    method = getattr(self._network, method_name, None)
    if method:
      method(*args)

  def _status_msg(self):
    active = proxy.stats().activeConnections()
    extra = ["%d conn" % active]

    if state.forced():
      extra.append("force: %d MB" % state.force_diff())

    if state.halted() and state.halt_diff():
      min = state.halt_diff() / 60
      extra.append("halted: %dm" % min)
    elif state.halted():
      extra.append("halted")

    eta_msg = svcclient.eta() or "Queue status unknown"
    return "%s (%s)" % (eta_msg, ", ".join(extra))

  def announce_status(self, target):
    self.connection.privmsg(target, self._status_msg())

  def announce_force_end(self):
    msg = "Force has ended. Queue: %s" % self._status_msg()
    self.connection.privmsg(self.channel, msg)

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
      self.announce_status(self.channel)

    self.send_connupdate(self.channel)

  def send_yield(self):
    self.connection.ctcp("SS_YIELD", self.channel)

  def send_startelection(self):
    self.connection.ctcp("SS_STARTELECTION", self.channel)

  def send_connstat(self):
    self.connection.ctcp("SS_CONNSTAT", self.channel)

  def send_connupdate(self, target):
    count = proxy.stats().activeConnections()
    self.connection.ctcp("SS_CONNUPDATE", target,
                         "%s %d" % (config.NICK, count))

  def send_halt_error(self, target):
    halt_diff = state.halt_diff()
    if halt_diff:
      min = halt_diff / 60
      pl = min == 1 and "minute" or "minutes"
      self.connection.privmsg(target,
                              "System is halted for another %d %s." %
                              (min, pl))
    else:
      self.connection.privmsg(target, "System is indefinitely halted.")

  def _reconnect(self):
    self._logger.debug('Reconnecting in %d seconds.' % self._reconnect_delay)
    time.sleep(self._reconnect_delay)
    self.connect()

  def _rejoin(self):
    self._logger.debug('Rejoining control channel in %s seconds.' %
                       self._rejoin_delay)
    time.sleep(self._rejoin_delay)
    self.connection.join(self.channel)

  def connect(self):
    self._logger.debug('Connecting to %s:%s.' % (self.server, self.port))
    self._network.statusIs(network.STATUS['connecting'])
    try:
      irclib.SimpleIRCClient.connect(self,
                                     self.server, self.port, self.nick,
                                     ssl=self.ssl)
    except irclib.ServerConnectionError, e:
      self._logger.debug(e)
      self._reconnect()

  def on_nicknameinuse(self, connection, event):
    # When nick is in use, append a number to the base nick.
    old_nick = event.arguments()[0]
    self._nick_counter += 1
    new_nick = '%s%d' % (self.nick, self._nick_counter)
    self._logger.debug('Nick %s in use, trying %s.' % (old_nick, new_nick))
    connection.nick(new_nick)

  def on_welcome(self, connection, event):
    self.nick = event.target()
    self._nick_counter = 1

    self._network.statusIs(network.STATUS['connected'])
    self._logger.debug('Connected to IRC. Nick is %s.' % self.nick)

    if irclib.is_channel(self.channel):
      connection.join(self.channel)

  def on_disconnect(self, connection, event):
    self._network.statusIs(network.STATUS['disconnected'])
    msg = event.arguments()[0]
    self._logger.debug('Disconnected from IRC server: %s' % msg)

    # We left the network.
    self._addNetworkEvent('leaveEventNew', self.nick)

    svcclient.pause()
    state.unforce()
    if state.halted():
      self._unhalt_on_connect = False
    else:
      self._unhalt_on_connect = True
      state.halt(0)

    self._reconnect()

  def on_join(self, connection, event):
    nick = event.source().split('!')[0]
    target = event.target()
    self._logger.debug('join %s -> %s' % (nick, target))

    if nick == self.nick and target == self.channel:
      self._network.statusIs(network.STATUS['synced'])
    self._addNetworkEvent('joinEventNew', nick)

    if nick == self.nick and target == self.channel:
      if self._first_time:
        # adding jobs to job queue
        jobs.add_job(check_connections, delay=10, periodic=True)
        jobs.add_job(check_queue, delay=1800, periodic=True)
        jobs.add_job(check_queue, delay=10)
        jobs.add_job(check_for_force_transition, delay=10, periodic=True)
        jobs.add_job(check_for_queue_transition, delay=60, periodic=True)
        self._first_time = False

      self._logger.debug('Sending SS_ANNOUNCE')
      tracker.clear()
      connection.ctcp('SS_ANNOUNCE', target)
      if self._unhalt_on_connect:
        jobs.add_job(state.unhalt, delay=8)

  def on_part(self, connection, event):
    nick = event.source().split('!')[0]
    target = event.target()
    logging.debug('part %s <- %s' % (nick, target))
    self._addNetworkEvent('leaveEventNew', nick)

    if target == self.channel:
      tracker.remove(nick)
      logging.debug('current peers: %s' % ', '.join(tracker.peers()))

  def on_quit(self, connection, event):
    nick = event.source().split('!')[0]
    logging.debug('quit %s' % nick)
    self._addNetworkEvent('leaveEventNew', nick)

    tracker.remove(nick)
    logging.debug('current peers: %s' % ', '.join(tracker.peers()))

  def on_kick(self, connection, event):
    kicked_nick = event.arguments()[0]
    self._addNetworkEvent('leaveEventNew', kicked_nick)

    chan = event.target()
    if chan == self.channel and kicked_nick != self.nick:
      tracker.remove(self.nick)
      logging.debug('current peers: %s' % ', '.join(tracker.peers()))
    elif kicked_nick == self.nick:
      # We're no longer synced.
      self._network.statusIs(network.STATUS['connected'])
      self._rejoin()

  def on_nick(self, connection, event):
    old_nick = event.source().split("!")[0]
    nick = event.target()
    if old_nick == self.nick:
      self.nick = event.target()
      logging.debug("new bot nick is %s" % self.nick)
    tracker.rename(old_nick, nick)

  def on_privmsg(self, connection, event):
    nick = event.source().split('!')[0]
    msg = event.arguments()[0]
    target = None
    self._addNetworkEvent('chatMessageNew', nick, target, message)

    m = re.search(r"^\s*(.+?)(?:\s+(.+?))?\s*$", msg)
    if not m:
      return
    command, ext = m.group(1).lower(), m.group(2)

    callback = getattr(self.cb, 'msg_%s' % command, None)
    if callback is not None:
      # jump to callback
      callback(self, event, nick, ext)

  def on_pubmsg(self, connection, event):
    nick = event.source().split('!')[0]
    msg = event.arguments()[0]
    target = event.target()
    self._addNetworkEvent('chatMessageNew', nick, target, msg)

    if target != self.channel:
      return

    # .status
    if msg == ".status" and proxy.stats().activeConnections() > 0:
      self.cb.msg_eta(self, event, event.target(), "")

    # .version
    if msg == ".version":
      self.cb.msg_version(self, event, event.target(), "")

    m = re.search(r"^(%s):\s*(.+?)(?:\s+(.+?))?\s*$" % re.escape(self.nick),
                  msg)
    if not m:
      return

    target, command, ext = m.group(1), m.group(2).lower(), m.group(3)
    if target.lower() != self.nick.lower():
      return

    callback = getattr(self.cb, "msg_%s" % command, None)
    if callback is not None:
      # jump to callback
      callback(self, event, event.target(), ext)

  def on_ctcp(self, connection, event):
    nick = event.source().split('!')[0]
    args = event.arguments()
    ctcp_type = args[0]

    callback = getattr(self.cb, "ctcp_%s" % ctcp_type[3:].lower(), None)
    if callback is not None:
      # jump to callback
      callback(self, event, nick, args)

    # This is the new protocol.

    if len(args) == 0 or args[0] != 'SSMSG':
      # Ignore all other CTCPs.
      return

    msg = args[1].split(' ')
    if len(msg) < 2:
      # Incomplete message.
      return

    try:
      version = int(msg[0])
      type = int(msg[1])
    except ValueError:
      # Not a well-formed message.
      return

    if len(msg) >= 3:
      message = ' '.join(msg[2:])
    else:
      message = ''

    self._addNetworkEvent('controlMessageNew', nick, version, type, message)


def check_connections():
  global cur_count
  global start_time
  global start_bytes_transferred
  global total_bytes_transferred

  total_bytes_transferred = proxy.stats().totalTransferred()
  active = proxy.stats().activeConnections()

  if active != cur_count and (active == 0 or cur_count == 0):
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

    # notify to IRC
    bot.connection_change(cur_count, elapsed, tx)

    # report to webapp
    if active == 0 and getattr(config, "REPORTER_URL", None):
      report = reporter.Report(tx, elapsed)
      report.send(getattr(config, "REPORTER_URL", ""),
                  getattr(config, "REPORTER_KEY", ""))


def check_for_force_transition():
  """See if the force status goes from force to non-force.

  If so, notify IRC.
  """
  if state.last_force_state == True and not state.forced():
    # notify IRC
    bot.announce_force_end()
    state.last_force_state = False
  elif state.forced():
    state.last_force_state = True


def check_for_queue_transition():
  """See if the queue goes from empty to non-empty.

  If so, call a minor election. If a force is in effect with an empty queue, the
  force will be cleared.
  """
  if state.halted():
    return

  global last_queue_size
  queue_size = svcclient.queue_size()

  if last_queue_size == 0 and queue_size > 0 and svcclient.is_paused():
    # an item was queued since we last checked, start minor election
    logging.debug("noticed queue transition from empty to non-empty")

    if config.AUTO_RESUME:
      start_election(queue_size, major=False)
    else:
      logging.debug("skipping election; AUTO_RESUME is disabled")
  elif queue_size == 0 and state.forced():
    logging.debug("queue is empty with a force in effect. Unforcing.")
    state.unforce()

  last_queue_size = queue_size


def check_queue():
  queue_size = svcclient.queue_size()
  if not queue_size or not svcclient.is_paused():
    return
  if state.halted():
    return

  global last_queue_size
  last_queue_size = queue_size

  # we have a queue and we're currently paused. Investigate options.
  if not config.AUTO_RESUME:
    logging.debug("skipping election; AUTO_RESUME is disabled")

  # Call a major election if possible.
  if last_major_election + 1800 < time.time():
    start_election(queue_size, major=True)
  # Last election was too recent, start a minor election.
  else:
    start_election(queue_size, major=False)


def start_election(queue_size, major=True):
  global election
  global last_major_election

  if major:
    logging.debug("starting major election")
    logging.debug("Current queue size: %.2f MB" % queue_size)
    last_major_election = time.time()
  else:
    logging.debug("starting minor election")

  election = electiontracker.Election(bot, major)
  election.start()
  jobs.add_job(check_election, delay=20)


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
    election = None
    return

  # Results are in for a major election
  if election.is_major():
    winner = bot.nick
    queue_size = svcclient.queue_size()

    results = election.results()
    for peer in results:
      size = results[peer]
      if size > 0 and size < queue_size:
        winner = peer
        queue_size = size

    logging.debug("election winner: %s, queue size: %d MB" %
                  (winner, queue_size))

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

  # Results are in for a minor election
  else:
    queue_size = svcclient.queue_size()
    occupied = False
    results = election.results()
    for peer in results:
      count = results[peer]
      if count > 0:
        occupied = True
        logging.debug("Service is occupied by %s with %s connections" %
                      (peer, count))

    if not occupied and queue_size > 0:
      bot.connection.privmsg(bot.channel,
                             "Autoresume activated. Queue size: %d MB." %
                             queue_size)
      bot.send_yield()
      svcclient.resume()
    elif not occupied and queue_size == 0:
      logging.debug("won minor election, but queue size is 0. ignoring.")

  election = None


def version_string():
  git_path = os.path.normpath(os.path.join(os.path.dirname(sys.argv[0]),
                                           ".git/refs/heads/master"))
  if not os.path.exists(git_path):
    return __version__

  fd = open(git_path, "r")
  id = fd.read()
  fd.close()

  return "%s (%s)" % (__version__, id[0:5])


def ircloop():
  while True:
    bot.ircobj.process_once(timeout=0.4)

    while jobs.has_next_job():
      nj = jobs.next_job()
      nj.func(*nj.args)


def main():
  global bot
  global jobs
  global proxy
  global state
  global svcclient
  global tracker
  global _version_string

  irclib.DEBUG = 0

  # Set up logging.
  _fmt = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
  logging.basicConfig(level=logging.DEBUG,
                      format=_fmt)

  # initialize signals
  init_signals()

  # job queue
  jobs = jobqueue.JobQueue()

  # set up connection proxy
  _local_addr = (config.LOCAL_HOST, config.LOCAL_PORT)
  _target_addr = (config.TARGET_HOST, config.TARGET_PORT)
  proxy = connectionproxy.ConnectionProxy(_local_addr, _target_addr)
  proxy.runningIs(True)

  # state
  state = SvcshareState()

  # set up access to service client
  _client_key = getattr(config, "SERVICE_CLIENT_KEY", "")
  svcclient = clientcontrol.ClientControl(proxy,
                                          config.SERVICE_CLIENT,
                                          config.SERVICE_CLIENT_URL,
                                          _client_key)
  svcclient.pause()
  state.halt(0)  # start halted

  # Network abstraction.
  net = network.Network()

  # Reactor for network events.
  net_reactor = NetworkReactor()
  net_reactor.notifierIs(net)

  # set up peer tracker (keep track of other bots)
  tracker = peertracker.PeerTracker()

  # populate version string
  _version_string = version_string()

  while True:
    try:
      use_ssl = getattr(config, 'BOT_SSL', False)
      bot = Bot(net,
                config.BOT_IRCSERVER, config.BOT_IRCPORT,
                config.BOT_NICK, config.BOT_CHANNEL,
                BotCallbacks(), ssl=use_ssl)
      bot.connect()
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
