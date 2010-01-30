import logging
from svcshare import connection
from svcshare import exc


class ConnectionStats(object):
  '''Maintain transfer statistics for a collection of connections.'''
  def __init__(self):
    self._conns = {}
    self._bytesTransferred = 0
    self._count = 0

  def connectionNew(self, source, target):
    '''Register a new active connection.

    Bi-directional connections share the same Connection object.

    Args:
      source: (host, port) tuple
      target: (host, port) tuple

    Returns:
      Connection object for new connection
    '''
    if (source, target) in self._conns:
      return self._conns[(source, target)]
    elif (target, source) in self._conns:
      return self._conns[(target, source)]
    else:
      conn = connection.Connection(source, target)
      self._conns[(source, target)] = conn
      self._count += 1
      return conn

  def connectionDel(self, conn):
    '''Close an active connection.

    Args:
      conn: Connection object

    Returns:
      deleted Connection or None if not found
    '''
    key = (conn.source(), conn.target())
    if key in self._conns:
      self._bytesTransferred += conn.bytes()
      del self._conns[key]
      return conn
    return None

  def activeConnections(self):
    '''Get number of active connections.

    Returns:
      integer
    '''
    return len(self._conns.keys())

  def totalConnections(self):
    '''Get the number of connections made.

    Returns:
      integer
    '''
    return self._count

  def totalTransferred(self):
    '''Get the total bytes transferred over all connections.

    Returns:
      integer
    '''
    bytes = self._bytesTransferred
    for conn in self._conns:
      bytes += self._conns[conn].bytes()
    return bytes