import exc


class Peer(object):
  def __init__(self, name, queue):
    self._name = name
    self._queue = queue

  def name(self):
    return self._name

  def queue(self):
    return self._queue

  def queueIs(self, queue):
    self._queue = queue


class PeerNetwork(object):
  """Network of Peers"""
  def __init__(self):
    self._peers = {}

  def peerIs(self, peer):
    if peer.name() in self._peers:
      # XXX need logging
      raise exc.NameInUseException
    self._peers[peer.name()] = peer

  def peerDel(self, name):
    try:
      peer = self._peers[name]
    except KeyError:
      # XXX need logging
      raise exc.NameNotFoundException
    else:
      del self._peers[name]
      return peer

  def networkEmpty(self):
    self._peers = {}

  def peers(self):
    return len(self._peers.keys())

  def peerList(self):
    return self._peers.values()

  def peer(self, name):
    try:
      return self._peers[name]
    except KeyError:
      return None
