from nose.tools import *
import time
from svcshare import electiontracker
from svcshare import network
from svcshare import peertracker


class Test_ElectionTracker:
  def setup(self):
    self._net = network.Network('server', 1337, 'nick', 'channel')
    self._pt = peertracker.PeerTracker()
    self._pt.notifierIs(self._net)
    self._et = electiontracker.ElectionTracker(self._pt)
    self._et.notifierIs(self._net)

  def _announce(self, peerName):
    self._net.controlMessageNew(peerName, 'channel', 'SS_ANNOUNCE')

  def _leave(self, peerName):
    self._net.leaveEventNew(peerName)

  def test_simpleElection(self):
    self._announce('Bob')
    self._announce('Alice')
    assert_equals(self._pt.peerNetwork().peers(), 2)
    assert_equals(len(self._et.peerResponses()), 0)
    self._et.durationIs(1)
    self._et.statusIs(electiontracker.STATUS['running'])
    time.sleep(2)
    assert_equals(self._et.status(), 'stopped')
    peerResponses = self._et.peerResponses()
    assert_equals(len(peerResponses), 2)
    assert_equals(peerResponses['Bob'], -1)
    assert_equals(peerResponses['Alice'], -1)
