import logging
import random
import threading
import time
import irclib


STATUS = {'disconnected': 'disconnected',
          'connecting': 'connecting',
          'connected': 'connected',
          'synced': 'synced'}

# ISOLATION is the ability for the client to connect to the network.
#   isolated cuts off the client from the network.
#   open will allow connections to the network.
ISOLATION = {'isolated': 'isolated',
             'open': 'open'}


class NetworkEvent(object):
  def __init__(self, type, source, target, arguments):
    self._type = type
    self._source = source
    self._target = target
    self._arguments = arguments

  def __str__(self):
    return '<NetworkEvent(%s): %s -> %s %s>' % (self._type, self._source,
                                                self._target, self._arguments)

  def type(self):
    return self._type

  def source(self):
    return self._source

  def target(self):
    return self._target

  def arguments(self):
    return self._arguments


class Network(object):
  class Notifiee(object):
    def __init__(self):
      self._notifier = None

    def notifierIs(self, notifier):
      if self._notifier is not None:
        notifier._notifiees.remove(self)
      self._notifier = notifier
      notifier._notifiees.append(self)

    def onStatus(self, status):
      pass

    def onJoinEvent(self, event):
      pass

    def onLeaveEvent(self, event):
      pass

    def onControlMessage(self, event):
      pass

    def onChatMessage(self, event):
      pass

  def __init__(self, server, port, nick, channel, ssl=False):
    self._status = STATUS['disconnected']
    self._bot = Bot(self, server, port, nick, channel, ssl=ssl)
    self._botThread = threading.Thread(target=self._bot.start)
    self._botThread.daemon = True
    self._isolation = ISOLATION['isolated']
    self._logger = logging.getLogger('Network')
    self._notifiees = []

  def _doNotification(self, methodName, *args):
    for notifiee in self._notifiees:
      try:
        method = getattr(notifiee, methodName)
      except AttributeError:
        return
      else:
        method(*args)

  def isolation(self):
    return self._isolation

  def isolationIs(self, iso):
    if iso == 'isolated':
      self._isolation = ISOLATION[iso]
      self._bot.disconnect()
    elif iso == 'open':
      self._isolation = ISOLATION[iso]
      if not self._botThread.is_alive():
        self._botThread.start()
      self._bot.connect()

  def server(self):
    return self._bot.server()

  def port(self):
    return self._bot.port()

  def nick(self):
    return self._bot.nick()

  def channel(self):
    return self._bot.channel()

  def status(self):
    return self._status

  def statusIs(self, status):
    if self._status == status:
      return
    self._logger.debug('status is now %s' % status)
    self._status = status
    self._doNotification('onStatus', status)

  def joinEventNew(self, event):
    self._logger.debug(event)
    self._doNotification('onJoinEvent', event)

  def leaveEventNew(self, event):
    self._logger.debug(event)
    self._doNotification('onLeaveEvent', event)

  def controlMessageNew(self, event):
    self._logger.debug(event)
    self._doNotification('onControlMessage', event)

  def chatMessageNew(self, event):
    self._logger.debug(event)
    self._doNotification('onChatMessage', event)

  def controlMessageIs(self, target, type, message=None):
    self._bot.connection.ctcp(type, target, message)

  def chatMessageIs(self, target, message):
    self._bot.connection.privmsg(target, message)


class Bot(irclib.SimpleIRCClient):
  def __init__(self, network, server, port, nick, channel, ssl=False):
    irclib.SimpleIRCClient.__init__(self)
    #irclib.DEBUG = 1
    self._network = network
    self._server = server
    self._port = port
    self._nick = nick
    self._channel = channel
    self._ssl = ssl
    self._curNick = None
    self._nickCounter = 1
    self._reconnectDelay = 15
    self._rejoinDelay = 5
    self._logger = logging.getLogger('Bot')

  def server(self):
    return self._server

  def port(self):
    return self._port

  def nick(self):
    return self._curNick

  def channel(self):
    return self._channel

  def _reconnect(self):
    self._logger.debug('Reconnecting in %d seconds' % self._reconnectDelay)
    time.sleep(self._reconnectDelay)
    self.connect()

  def _rejoin(self):
    self._logger.debug('Rejoining control channel in %s seconds' %
                       self._rejoinDelay)
    time.sleep(self._rejoinDelay)
    self.connection.join(self._channel)

  def connect(self):
    self._logger.debug('Connecting to %s:%s' % (self._server, self._port))
    self._network.statusIs(STATUS['connecting'])
    try:
      irclib.SimpleIRCClient.connect(self, self._server, self._port, self._nick,
                                     ssl=self._ssl)
    except irclib.ServerConnectionError, e:
      self._logger.debug(e)
      self._reconnect()

  def _addNetworkEvent(self, methodName, event):
    networkEvent = NetworkEvent(event.eventtype(), event.source(),
                                event.target(), event.arguments())
    if methodName in dir(self._network):
      method = getattr(self._network, methodName)
      method(networkEvent)

  def on_nicknameinuse(self, connection, event):
    # When nick is in use, append a number to the base nick.
    rand = random.randint(0, 9)
    self._nickCounter += 1
    newNickAttempt = '%s%d' % (self._nick, self._nickCounter)
    self._logger.debug('nick %s in use, trying %s' % (event.target(),
                                                      newNickAttempt))
    connection.nick(newNickAttempt)

  def on_welcome(self, connection, event):
    self._curNick = event.target()
    self._network.statusIs(STATUS['connected'])
    self._logger.debug('Connected to IRC. Nick is %s.' % self._curNick)
    if irclib.is_channel(self._channel):
      connection.join(self._channel)

  def on_disconnect(self, connection, event):
    self._network.statusIs('disconnected')
    self._logger.debug('Disconnected from IRC server: %s' % event.arguments()[0])
    self._reconnect()

  def on_join(self, connection, event):
    nick = event.source().split("!")[0]
    chan = event.target()
    self._logger.debug("JOIN %s -> %s" % (nick, chan))

    if nick == self._curNick and chan == self._channel:
      self._network.statusIs(STATUS['synced'])
    else:
      self._addNetworkEvent('joinEventNew', event)

  def on_part(self, connection, event):
    self._addNetworkEvent('leaveEventNew', event)

  def on_quit(self, connection, event):
    self._addNetworkEvent('leaveEventNew', event)

  def on_kick(self, connection, event):
    kickedNick = event.arguments()[0]
    if kickedNick == self._curNick:
      self._network.statusIs(STATUS['connected'])

    if len(event.arguments()) > 1:
      kickMsg = event.arguments()[1]
    else:
      kickMsg = ''
    newArgs = [event.source(), kickMsg]
    self._addNetworkEvent('leaveEventNew',
                          irclib.Event(event.eventtype(), kickedNick,
                                       event.target(), newArgs))
    self._rejoin()

  def on_nick(self, connection, event):
    pass

  def on_privmsg(self, connection, event):
    self._addNetworkEvent('chatMessageNew', event)

  def on_pubmsg(self, connection, event):
    self._addNetworkEvent('chatMessageNew', event)

  def on_ctcp(self, connection, event):
    self._addNetworkEvent('controlMessageNew', event)
