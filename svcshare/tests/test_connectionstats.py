from nose.tools import *
from svcshare import connectionstats
from svcshare import exc


class Test_ConnectionStats:
  def setUp(self):
    self._cs = connectionstats.ConnectionStats()
    self._source = ('localhost', 1234)
    self._target = ('localhost', 4321)
    self._source2 = ('localhost', 1235)
    self._target2 = ('localhost', 5321)

  def test_oneActiveConnection(self):
    assert_equal(self._cs.activeConnections(), 0)
    conn = self._cs.connectionNew(self._source, self._target)
    assert_equal(self._cs.activeConnections(), 1)
    assert_equal(self._cs.connectionDel(conn), conn)
    assert_equal(self._cs.activeConnections(), 0)
    assert_equal(self._cs.totalConnections(), 1)

  def test_twoActiveConnections(self):
    conn1 = self._cs.connectionNew(self._source, self._target)
    assert_equal(self._cs.activeConnections(), 1)
    conn2 = self._cs.connectionNew(self._source2, self._target2)
    assert_equal(self._cs.activeConnections(), 2)
    assert_equal(self._cs.totalConnections(), 2)
    conn1.bytesInc(42)
    conn2.bytesInc(4)
    assert_equal(self._cs.totalTransferred(), 46)

  def test_totalTransferred(self):
    assert_equal(self._cs.totalTransferred(), 0)
    conn = self._cs.connectionNew(self._source, self._target)
    conn.bytesInc(42)
    assert_equal(self._cs.totalTransferred(), 42)