import logging

from svcshare import exc
from svcshare import msgtypes
from svcshare import network
from svcshare import peers


class PeerTracker(network.Network.Notifiee):
  def __init__(self):
    network.Network.Notifiee.__init__(self)
    self._logger = logging.getLogger('PeerTracker')
    self._peerNetwork = peers.PeerNetwork()

  def peerNetwork(self):
    return self._peerNetwork

  def onJoinEvent(self, name):
    if name == self._notifier.nick():
      #self._logger.debug('joined the control channel, sending announcement')
      #self._notifier.controlMessageIs(self._notifier.channel(), 'SS_ANNOUNCE')
      # TODO(ms): send a QUEUESTATUS here
      pass

  def onLeaveEvent(self, name):
    if name == self._notifier.nick():
      self._logger.debug('left the control channel, flushing peer network')
      self._peerNetwork.networkEmpty()
      return
    if self._peerNetwork.peer(name) is not None:
      self._peerNetwork.peerDel(name)
      self._logger.debug('%s removed from the peer network' % name)

  def onControlMessage(self, name, version, type, message=None):
    # TODO(ms): logging needed here; also magic number
    if version != 2:
      return

    if type == msgtypes.QUEUESTATUS or type == msgtypes.LOCKSTATUS:
      # Make sure peer is in network, else add new peer.
      if self._peerNetwork.peer(name) is None:
        peer = peers.Peer(name)
        self._peerNetwork.peerIs(peer)
        self._logger.debug('%s added to the peer network' % peer.name())
