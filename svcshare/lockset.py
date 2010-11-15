import logging


class LockSetItem(object):
  def __init__(self, name, locked):
    self._name = name
    self._locked = locked

  def __eq__(self, other):
    return (self._name == other._name and self._locked == other._locked)

  def __ne__(self, other):
    return not self.__eq__(other)

  def __str__(self):
    return '(%s, %d)' % (self._name, int(self._locked))

  def __repr__(self):
    return self.__str__()

  def name(self):
    return self._name

  def locked(self):
    return self._locked


class LockSet(object):
  def __init__(self):
    self._items = {}
    self._logger = logging.getLogger('LockSet')

  def __eq__(self, other):
    if other.items() != self.items():
      return False
    for key in self._items:
      if other.item(key) != self.item(key):
        return False
    return True

  def __str__(self):
    return str([self._items[x] for x in sorted(self._items.keys())])

  def __repr__(self):
    return self.__str__()

  def itemIs(self, item):
    self._items[item.name()] = item

  def items(self):
    return len(self._items)

  def item(self, name):
    try:
      return self._items[name]
    except KeyError:
      return None

  def itemDict(self):
    return self._items

  def string(self):
    items = []
    for key in sorted(self._items.keys()):
      items.append('%s:%d' % (key, int(self._items[key].locked())))
    return ' '.join(items)

  def stringIs(self, string):
    self._items = {}
    tokens = string.split(' ')
    for token in tokens:
      if token.count(':') != 1:
        continue
      name, locked = token.split(':')
      try:
        locked = bool(int(locked))
      except ValueError:
        continue
      self.itemIs(LockSetItem(name, locked))
