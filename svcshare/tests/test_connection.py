from nose.tools import *
from svcshare import connection
from svcshare import exc


class Test_Connection:
  def setUp(self):
    self._source = ('localhost', 1234)
    self._target = ('localhost', 4321)
    self._c = connection.Connection(self._source, self._target)

  def test_bytes(self):
    assert_equal(self._c.bytes(), 0)
    self._c.bytesInc(42)
    assert_equal(self._c.bytes(), 42)

  @raises(exc.RangeException)
  def test_invalidIncrement(self):
    self._c.bytesInc(-42)

  def test_source(self):
    assert_equal(self._c.source(), self._source)

  def test_target(self):
    assert_equal(self._c.target(), self._target)