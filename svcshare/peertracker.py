import time


class PeerTracker(object):
  def __init__(self):
    self.clear()

  def clear(self):
    self._peers = {}
    self._last_cleared = time.time()

  def update(self, peername):
    self._peers[peername] = time.time()

  def peers(self):
    return self._peers.keys()
