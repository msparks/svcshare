from nose.tools import *
from svcshare import peers
from svcshare import exc


class Test_Peers:
  def setup(self):
    self.network = peers.PeerNetwork()

  def test_emptyNetwork(self):
    self.network.networkEmpty()
    assert_equal(self.network.peers(), 0)

  def test_addPeers(self):
    peer1 = peers.Peer("Bob")
    peer2 = peers.Peer("Alice")
    self.network.peerIs(peer1)
    self.network.peerIs(peer2)
    assert_equal(self.network.peers(), 2)
    assert_equal(self.network.peer("Bob"), peer1)
    assert_equal(self.network.peer("Alice"), peer2)
    assert_equal(sorted(self.network.peerList()), [peer1, peer2])

  def test_removeAllPeers(self):
    peer = peers.Peer("Bob")
    self.network.peerIs(peer)
    assert_equal(self.network.peers(), 1)
    self.network.networkEmpty()
    assert_equal(self.network.peers(), 0)

  def test_getUnknownPeer(self):
    assert_equal(self.network.peer("Fred"), None)

  @raises(exc.NameNotFoundException)
  def test_removeUnknownPeer(self):
    peer = self.network.peerDel("Fred")

  def test_removeOnePeer(self):
    peer1 = peers.Peer("Bob")
    peer2 = peers.Peer("Alice")
    self.network.peerIs(peer1)
    self.network.peerIs(peer2)
    self.network.peerDel("Bob")
    assert_equal(self.network.peers(), 1)
    assert_equal(self.network.peer("Bob"), None)
