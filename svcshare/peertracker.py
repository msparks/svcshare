import time


class PeerTracker(object):
  def __init__(self):
    self.clear()

  def clear(self):
    self._peers = {}
    self._last_cleared = time.time()

  def add(self, peername):
    self._peers[peername] = time.time()

  def remove(self, peername):
    if peername in self._peers:
      del self._peers[peername]

  def rename(self, old_name, new_name):
    if old_name in self._peers:
      self._peers[new_name] = self._peers[old_name]
      self.remove(old_name)

  def peers(self):
    return self._peers.keys()
