from nose.tools import *
from svcshare import msgtypes
from svcshare import network
from svcshare import peertracker


class Test_PeerTracker:
  def setup(self):
    self._net = network.Network('server', 1337, 'nick', 'channel')
    self._pt = peertracker.PeerTracker()
    self._pt.notifierIs(self._net)
    self._peerNetwork = self._pt.peerNetwork()

  def _send_queuestatus(self, peerName):
    version = 2
    data = ''
    self._net.controlMessageNew(peerName, version, msgtypes.QUEUESTATUS, data)

  def _leave(self, peerName):
    self._net.leaveEventNew(peerName)

  def test_announce(self):
    self._send_queuestatus('peer1')
    self._send_queuestatus('peer2')
    assert_equals(self._peerNetwork.peers(), 2)

  def test_leave(self):
    self._leave('peer1')
    self._leave('peer2')
    assert_equals(self._peerNetwork.peers(), 0)
