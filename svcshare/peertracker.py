import logging

from svcshare import exc
from svcshare import msgtypes
from svcshare import peers
from svcshare import protocoldirector


class PeerTracker(protocoldirector.ProtocolDirector.Notifiee):
  def __init__(self):
    protocoldirector.ProtocolDirector.Notifiee.__init__(self)
    self._logger = logging.getLogger('PeerTracker')
    self._peerNetwork = peers.PeerNetwork()

  def _peer(self, name):
    if self._peerNetwork.peer(name) is None:
      peer = peers.Peer(name)
      self._peerNetwork.peerIs(peer)
      self._logger.debug('%s added to the peer network' % name)
      return peer
    else:
      return self._peerNetwork.peer(name)

  def peerNetwork(self):
    return self._peerNetwork

  def onSelfJoinEvent(self):
    self._logger.debug('joined the control channel')

  def onSelfLeaveEvent(self):
    self._logger.debug('left the control channel, flushing peer network')
    self._peerNetwork.networkEmpty()

  def onPeerLeaveEvent(self, name):
    if self._peerNetwork.peer(name) is not None:
      self._peerNetwork.peerDel(name)
      self._logger.debug('%s removed from the peer network' % name)

  def onQueueStatus(self, name, queue):
    peer = self._peer(name)
    peer.queueIs(queue)
    self._logger.debug('%s queue: %s' % (name, queue))

  def onLockStatus(self, name, locks):
    peer = self._peer(name)
    peer.locksetIs(locks)
    self._logger.debug('%s locks: %s' % (name, locks))
