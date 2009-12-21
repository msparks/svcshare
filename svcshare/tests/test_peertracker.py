from nose.tools import *
from svcshare import network
from svcshare import peertracker


class Test_PeerTracker:
  def setup(self):
    self._net = network.Network('server', 1337, 'nick', 'channel')
    self._pt = peertracker.PeerTracker()
    self._pt.notifierIs(self._net)
    self._peerNetwork = self._pt.peerNetwork()

  def _announce(self, peerName):
    self._net.controlMessageNew(peerName, 'channel', 'SS_ANNOUNCE')

  def _leave(self, peerName):
    self._net.leaveEventNew(peerName)

  def test_announce(self):
    self._announce('peer1')
    self._announce('peer2')
    assert_equals(self._peerNetwork.peers(), 2)

  def test_leave(self):
    self._announce('peer1')
    self._leave('peer1')
    assert_equals(self._peerNetwork.peers(), 0)
