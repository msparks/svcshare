import logging
import threading
from svcshare import connection
from svcshare import exc


class ConnectionStats(object):
  '''Maintain transfer statistics for a collection of connections.'''
  def __init__(self):
    self._conns = {}
    self._bytesTransferred = 0
    self._count = 0
    self._lock = threading.RLock()

  def connectionNew(self, source, target):
    '''Register a new active connection.

    Bi-directional connections share the same Connection object.

    Args:
      source: (host, port) tuple
      target: (host, port) tuple

    Returns:
      Connection object for new connection
    '''
    self._lock.acquire()
    if (source, target) in self._conns:
      c = self._conns[(source, target)]
      self._lock.release()
      return c
    elif (target, source) in self._conns:
      c = self._conns[(target, source)]
      self._lock.release()
      return c
    else:
      conn = connection.Connection(source, target)
      self._conns[(source, target)] = conn
      self._count += 1
      self._lock.release()
      return conn

  def connectionDel(self, conn):
    '''Close an active connection.

    Args:
      conn: Connection object

    Returns:
      deleted Connection or None if not found
    '''
    key = (conn.source(), conn.target())
    conn = None
    self._lock.acquire()
    if key in self._conns:
      conn = self._conns[key]
      self._bytesTransferred += conn.bytes()
      del self._conns[key]
    self._lock.release()
    return conn

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
    self._lock.acquire()
    for conn in self._conns:
      bytes += self._conns[conn].bytes()
    self._lock.release()
    return bytes