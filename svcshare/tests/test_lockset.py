from nose.tools import *
from svcshare import lockset


class Test_LockSet:
  def setup(self):
    self._ls = lockset.LockSet()
    self._item1 = lockset.LockSetItem('l1', False)
    self._item2 = lockset.LockSetItem('l2', False)
    self._itemList = [self._item1, self._item2]
    for item in self._itemList:
      self._ls.itemIs(item)
    self._setString = 'l1:0 l2:0'

  def test_insert(self):
    ls = lockset.LockSet()
    assert_equals(ls.items(), 0)

    ls.itemIs(self._item1)
    assert_equals(ls.items(), 1)
    assert_equals(ls.item(self._item1.name()), self._item1)

    ls.itemIs(self._item2)
    assert_equals(ls.items(), 2)
    assert_equals(ls.item(self._item2.name()), self._item2)

  def test_string(self):
    assert_equals(self._ls.string(), self._setString)

  def test_stringIs(self):
    ls = lockset.LockSet()
    ls.stringIs(self._ls.string())
    assert_equals(ls, self._ls)
    assert_equals(ls.string(), self._ls.string())

  def test_malformed_strings(self):
    bad_string = 'l1:0 l2'
    l1 = lockset.LockSetItem('l1', 0)
    ls = lockset.LockSet()
    ls.stringIs(bad_string)
    assert_equals(ls.items(), 1)
    assert_equals(ls.item('l1'), l1)

    bad_string2 = 'l1:0 l2:'
    ls2 = lockset.LockSet()
    ls2.stringIs(bad_string2)
    assert_equals(ls.items(), 1)
    assert_equals(ls.item('l1'), l1)
