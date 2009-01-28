import logging
import threading


class Connection(object):
  """Class representing a connection between two peers.

  Attributes:
    bytes: bytes transferred on this connection
  """
  def __init__(self, source_addr, target_addr):
    self._lock = threading.RLock()
    self.bytes = 0
    self.source_addr = source_addr
    self.target_addr = target_addr
    logging.info("registered connection for %s to %s" % (str(source_addr),
                                                         str(target_addr)))

  def transfer(self, bytes):
    """Record a transfer for a connection.

    Args:
      conn_id: integer connection ID
      bytes: integer number of bytes transferred
    """
    self._lock.acquire()
    self.bytes += bytes
    self._lock.release()


class ConnectionStats(object):
  """Maintain transfer statistics for a collection of connections."""
  def __init__(self):
    self._conns = {}
    self._bytes_transferred = 0
    self._count = 0

  def register(self, source_addr, target_addr):
    """Register a new active connection.

    Bi-directional connections share the same Connection object.

    Args:
      source_addr: (host, port) tuple
      target_addr: (host, port) tuple

    Returns:
      Connection object
    """
    if (source_addr, target_addr) in self._conns:
      return self._conns[(source_addr, target_addr)]
    elif (target_addr, source_addr) in self._conns:
      return self._conns[(target_addr, source_addr)]
    else:
      conn = Connection(source_addr, target_addr)
      self._conns[(source_addr, target_addr)] = conn
      self._count += 1
      return conn

  def close(self, conn):
    """Close an active connection.
    """
    key = (conn.source_addr, conn.target_addr)
    self._bytes_transferred += conn.bytes
    if key in self._conns:
      del self._conns[key]

  def active_connections(self):
    """Get list of active connections.

    Returns:
      list of Connection instances
    """
    return self._conns.keys()

  def total_count(self):
    """Get the number of connections made.

    Returns:
      integer
    """
    return self._count

  def total_transferred(self):
    """Get the total bytes transferred over all connections.

    Returns:
      integer
    """
    bytes = self._bytes_transferred
    for conn in self._conns:
      bytes += self._conns[conn].bytes
    return bytes
