import time


class Election(object):
  def __init__(self, bot):
    """Create Election instance.

    Args:
      bot: Bot instance
      tracker: PeerTracker instance
    """
    self._bot = bot
    self._peers = {}
    self._starttime = time.time()

  def start(self):
    """Start the election.
    """
    self._bot.connection.ctcp("SS_STARTELECTION", self._bot.channel)

  def update(self, peername, size):
    """Update the election status with a new result from a peer.

    Args:
      peername: peer name
      size: queue size
    """
    self._peers[peername] = size

  def peers(self):
    """Get list of peers who have voted.

    Returns:
      sorted list
    """
    lst = self._peers.keys()
    lst.sort()
    return lst

  def results(self):
    """Get election results.

    Returns:
      dict of peername => size key/value pairs
    """
    return self._peers

  def start_time(self):
    """Get epoch of start time.

    Returns:
      epoch
    """
    return self._starttime
