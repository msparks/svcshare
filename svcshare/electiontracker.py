import logging
import threading
import time

from svcshare import exc
from svcshare import network
from svcshare import peers


STATUS = {'running': 'running',
          'stopped': 'stopped'}


class ElectionTracker(network.Network.Notifiee):
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

  def __init__(self, pt):
    '''Constructor.

    Args:
      pt: PeerTracker instance
    '''
    network.Network.Notifiee.__init__(self)
    self._notifiees = []
    self._logger = logging.getLogger('ElectionTracker')
    self._status = STATUS['stopped']
    self._startTime = 0
    self._pt = pt
    self._queueSize = 0
    self._duration = 10
    self._peers = {}
    self._thread = threading.Thread(target=self._thread)
    self._thread.daemon = True
    self._thread.start()

  def _doNotification(self, methodName, *args):
    for notifiee in self._notifiees:
      try:
        method = getattr(notifiee, methodName)
      except AttributeError:
        return
      else:
        method(*args)

  def _thread(self):
    while True:
      epoch = time.time()
      if (self._status == STATUS['running'] and
          self._startTime + self._duration < epoch):
        self._status = STATUS['stopped']
        self._electionEnded()
      time.sleep(1)

  def duration(self):
    '''Get the maximum duration of an election, in seconds.

    Returns:
      seconds
    '''
    return self._duration

  def durationIs(self, seconds):
    '''Set the maximum duration of an election.

    Args:
      seconds: maximum duration
    '''
    self._duration = seconds

  def queueSizeIs(self, qs):
    '''Set the queue size to report to peers running elections.

    Args:
      qs: value to report
    '''
    self._queueSize = qs

  def status(self):
    return self._status

  def statusIs(self, status):
    if self._status == status:
      return
    if status not in STATUS:
      raise exc.RangeException

    if status == STATUS['running']:
      self._startTime = time.time()
      self._electionStarted()
    self._status = status
    self._doNotification('onStatus', status)

  def peerResponses(self):
    return self._peers

  def onControlMessage(self, name, target, type, message=None):
    if type == 'SS_STARTELECTION':
      self._replyToElection(name, message)
    elif type == 'SS_QUEUESIZE':
      self._handleElectionReply(name, message)

  def _replyToElection(self, name, message):
    if self._notifier:
      self._notifier.controlMessageIs(name, str(self._queueSize))

  def _handleElectionReply(self, name, message):
    try:
      size = float(message)
    except (ValueError, TypeError):
      size = 0
    if name in self._peers:
      self._peers[name] = size

  def _electionStarted(self):
    # Network object (the notifier) is set after ElectionTracker instantiation
    if self._notifier is not None:
      self._notifier.controlMessageIs(self._notifier.channel(),
                                      'SS_STARTELECTION')
      self._startTime = time.time()

      self._peers = {}
      peerList = self._pt.peerNetwork().peerList()
      for peer in peerList:
        self._peers[peer.name()] = -1
      self._logger.debug('Election started with %d peers' % len(self._peers))

  def _electionEnded(self):
    self._logger.debug('Election ended')
    for peerName in self._peers:
      size = self._peers[peerName]
      if size > -1:
        self._logger.debug('Peer %s reported size %.3f' % (peerName, size))
      else:
        self._logger.debug('No valid size from %s' % peerName)