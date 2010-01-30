import logging
import threading
from svcshare import exc


class Connection(object):
  '''Class representing a connection between two peers.'''
  def __init__(self, sourceAddr, targetAddr):
    self._logger = logging.getLogger('Connection')
    self._bytes = 0
    self._source = sourceAddr
    self._target = targetAddr
    self._lock = threading.RLock()
    self._logger.debug('registered connection for %s to %s' %
                       (str(self._source), str(self._target)))

  def bytes(self):
    '''Get number of bytes transferred on this connection.'''
    return self._bytes

  def bytesInc(self, delta):
    '''Increase number of bytes transferred on this connection.

    Args:
      delta: integer number of bytes transferred
    '''
    if delta < 0:
      raise exc.RangeException('delta must be non-negative')
    self._lock.acquire()
    self._bytes += delta
    self._lock.release()

  def source(self):
    '''Get source address of this connection.'''
    return self._source

  def target(self):
    '''Get target of this connection.'''
    return self._target