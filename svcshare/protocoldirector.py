import logging
import threading
import time

from svcshare import exc
from svcshare import msgtypes
from svcshare import network


class ProtocolDirector(network.Network.Notifiee):
  class Notifiee(object):
    def __init__(self):
      self._notifier = None

    def notifierIs(self, notifier):
      if self._notifier is not None:
        notifier._notifiees.remove(self)
      self._notifier = notifier
      notifier._notifiees.append(self)

    def onJoinEvent(self, name):
      pass

    def onLeaveEvent(self, name):
      pass

    def onQueueStatus(self, clientQueue):
      pass

    def onLockStatus(self, lockInfo):
      pass

  def __init__(self, net, client):
    network.Network.Notifiee.__init__(self)
    self.notifierIs(net)
    self._net = net
    self._notifiees = []
    self._logger = logging.getLogger('ProtocolDirector')

    if net and client:
      self._broadcasterThread = threading.Thread(target=self._broadcaster)
      self._broadcasterThread.daemon = True
      self._broadcasterThread.start()

  def _broadcaster(self):
    time.sleep(5)
    while True:
      self._logger.debug('broadcast')
      time.sleep(10)

  def _doNotification(self, methodName, *args):
    for notifiee in self._notifiees:
      method = getattr(notifiee, methodName, None)
      if method is not None:
        method(*args)

  def network(self):
    return self._net

  def onJoinEvent(self, name):
    if name == self._notifier.nick():
      #self._logger.debug('joined the control channel, sending announcement')
      #self._notifier.controlMessageIs(self._notifier.channel(), 'SS_ANNOUNCE')
      # TODO(ms): send a QUEUESTATUS here
      pass

  def onLeaveEvent(self, name):
    self._doNotification('onLeaveEvent', name)

  def onControlMessage(self, name, version, type, message=None):
    # TODO(ms): logging needed here; also magic number
    if version != 2:
      return

    if type == msgtypes.QUEUESTATUS:
      self._doNotification('onQueueStatus', name, None)
    elif type == msgtypes.LOCKSTATUS:
      self._doNotification('onLockStatus', name, None)