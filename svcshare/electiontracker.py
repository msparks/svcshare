import time


class Election(object):
  def __init__(self, bot, major):
    """Create Election instance.

    Args:
      bot: Bot instance
      major: (boolean) True if major election, False if minor
    """
    self._bot = bot
    self._peers = {}
    self._starttime = time.time()
    self._major = major

  def start(self):
    """Start the election.
    """
    if self._major:
      self._bot.send_startelection()
    else:
      self._bot.send_connstat()

  def update(self, peername, count):
    """Update the election status with a new result from a peer.

    Args:
      peername: peer name
      count: argument from peer (could be queue size or # of connections)
    """
    self._peers[peername] = count

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
      dict of peername => count key/value pairs
    """
    return self._peers

  def start_time(self):
    """Get epoch of start time.

    Returns:
      epoch
    """
    return self._starttime

  def is_major(self):
    """Is the election a major election?

    Returns:
      True if election is major, False if minor
    """
    return self._major
