from nose.tools import *
from svcshare import clientqueue


class Test_ClientQueue:
  def setup(self):
    self._queue = clientqueue.ClientQueue()
    self._item1 = clientqueue.ClientQueueItem('foo', 1234)
    self._item2 = clientqueue.ClientQueueItem('bar', 5678)
    self._itemList = [self._item1, self._item2]
    for item in self._itemList:
      self._queue.itemIs(item)
    self._queueString = 'foo:1234 bar:5678'

  def test_insert(self):
    q = clientqueue.ClientQueue()
    assert_equals(q.items(), 0)

    q.itemIs(self._item1)
    assert_equals(q.items(), 1)
    assert_equals(q.item(0), self._item1)

    q.itemIs(self._item2)
    assert_equals(q.items(), 2)
    assert_equals(q.item(1), self._item2)

  def test_list(self):
    assert_equals(self._queue.itemList(), self._itemList)

  def test_eq(self):
    queue2 = clientqueue.ClientQueue()
    for item in [self._item1, self._item2]:
      queue2.itemIs(item)
    assert_equals(self._queue, queue2)

  def test_string(self):
    assert_equals(self._queue.string(), self._queueString)

  def test_stringIs(self):
    q = clientqueue.ClientQueue()
    q.stringIs(self._queue.string())
    assert_equals(q, self._queue)
    assert_equals(q.string(), self._queue.string())
