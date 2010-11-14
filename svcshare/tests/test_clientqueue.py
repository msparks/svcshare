from nose.tools import *
from svcshare import clientqueue


class Test_ClientQueue:
  def setup(self):
    self._queue = clientqueue.ClientQueue()
    self._item1 = clientqueue.ClientQueueItem('foo', 1234)
    self._item2 = clientqueue.ClientQueueItem('bar', 5678)

  def test_insert(self):
    assert_equals(self._queue.items(), 0)

    self._queue.itemIs(self._item1)
    assert_equals(self._queue.items(), 1)
    assert_equals(self._queue.item(0), self._item1)

    self._queue.itemIs(self._item2)
    assert_equals(self._queue.items(), 2)
    assert_equals(self._queue.item(1), self._item2)

  def test_list(self):
    l = [self._item1, self._item2]
    for item in l:
      self._queue.itemIs(item)
    assert_equals(self._queue.itemList(), l)

  def test_eq(self):
    queue2 = clientqueue.ClientQueue()
    for item in [self._item1, self._item2]:
      self._queue.itemIs(item)
      queue2.itemIs(item)
    assert_equals(self._queue, queue2)
