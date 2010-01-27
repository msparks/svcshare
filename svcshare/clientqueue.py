import logging


class ClientQueueItem(object):
  def __init__(self, name, size):
    self._name = name
    self._size = size

  def __eq__(self, other):
    return (self._name == other.name() and self._size == other.size())

  def __ne__(self, other):
    return not self.__eq__(other)

  def name(self):
    return self._name

  def size(self):
    return self._size


class ClientQueue(object):
  def __init__(self):
    self._items = []
    self._logger = logging.getLogger('ClientQueue')

  def __eq__(self, other):
    if other.items() != self.items():
      return False
    for idx, item in enumerate(self._items):
      if item != other.item(idx):
        return False
    return True

  def __ne__(self, other):
    return not self.__eq__(other)

  def itemIs(self, item):
    self._items.append(item)

  def items(self):
    return len(self._items)

  def item(self, index):
    try:
      return self._items[index]
    except IndexError:
      return None