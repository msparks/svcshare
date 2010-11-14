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

  def peerNetwork(self):
    return self._peerNetwork

  def onLeaveEvent(self, name):
    if name == self._notifier.network().nick():
      self._logger.debug('left the control channel, flushing peer network')
      self._peerNetwork.networkEmpty()
    elif self._peerNetwork.peer(name) is not None:
      self._peerNetwork.peerDel(name)
      self._logger.debug('%s removed from the peer network' % name)

  def onQueueStatus(self, name, queue):
    if self._peerNetwork.peer(name) is None:
      peer = peers.Peer(name, queue)
      self._peerNetwork.peerIs(peer)
      self._logger.debug('%s added to the peer network' % peer.name())
    else:
      peer = self._peerNetwork.peer(name)
      peer.queueIs(queue)
