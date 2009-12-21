import logging

from svcshare import exc
from svcshare import network
from svcshare import peers


class PeerTracker(network.Network.Notifiee):
  def __init__(self):
    network.Network.Notifiee.__init__(self)
    self._logger = logging.getLogger('PeerTracker')
    self._peerNetwork = peers.PeerNetwork()

  def peerNetwork(self):
    return self._peerNetwork

  def onLeaveEvent(self, event):
    peerName = event.source().split('!')[0]

    if peerName == self._notifier.nick():
      self._logger.debug('we left the control channel, flushing peer network')
      self._peerNetwork.networkEmpty()
      return

    try:
      self._peerNetwork.peerDel(peerName)
    except exc.NameNotFoundException:
      self._logger.debug('%s not found in peer network' % peerName)
    else:
      self._logger.debug('%s removed from the peer network' % peerName)

  def onControlMessage(self, event):
    peer = peers.Peer(event.source().split('!')[0])
    args = event.arguments()
    if len(args) == 1 and args[0] == 'SS_ANNOUNCE':
      self._onAnnounce(peer, args[1:])

  def _onAnnounce(self, peer, args):
    self._logger.debug('received announce message from %s' % peer.name())
    try:
      self._peerNetwork.peerIs(peer)
    except exc.NameInUseException:
      self._logger.critical('peer announcement came from a peer already in '
                            'the peer network')
      raise
    else:
      self._logger.debug('%s added to the peer network' % peer.name())
      self._notifier.controlMessageIs(peer.name(), 'SS_ACK')
