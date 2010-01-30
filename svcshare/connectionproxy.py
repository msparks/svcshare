import logging
import socket
import SocketServer
import threading

from svcshare import connection
from svcshare import connectionstats

BUFFER_SIZE = 1048576


class ConnectionProxy(object):
  def __init__(self, address, target):
    '''Create a connection proxy.

    The proxy server will start paused.

    Args:
      address: (host, port) tuple for the local server
      target: (host, port) tuple for the target server
    '''
    self._logger = logging.getLogger('ConnectionProxy')
    self._stats = connectionstats.ConnectionStats()
    self._address = address
    self._target = target
    self._ev = threading.Event()
    self._ev.clear()

    self._thread = threading.Thread(target=self._serverThread)
    self._thread.setDaemon(True)
    self._thread.start()

  def _serverThread(self):
    while True:
      self._ev.wait()
      self._server = _ThreadingTCPServer(self._address, _ProxyRequestHandler)
      self._server._stats = self._stats
      self._server._target = self._target

      while True:
        self._server.handle_request()
        if not self._ev.isSet():
          self._server.shutdown()
          break

  def runningIs(self, running):
    '''Start or stop the proxy.'''
    if running and not self._ev.isSet():
      self._logger.debug('starting proxy')
      self._ev.set()
    elif not running and self._ev.isSet():
      self._logger.debug('stopping proxy')
      self._ev.clear()

  def running(self):
    '''Return True if the proxy is running.

    Returns:
      True if the proxy is running.
    '''
    return self._ev.isSet()

  def stats(self):
    '''Get the ConnectionStats object for this proxy.'''
    return self._stats


class _ThreadingTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
  def __init__(self, address, handler):
    self.allow_reuse_address = True
    self.request_queue_size = 10
    self.timeout = 0.5
    self._shutdown = False
    self._sockets = []
    self._logger = logging.getLogger('ConnectionProxy')
    SocketServer.TCPServer.__init__(self, address, handler)

  def handle_timeout(self):
    pass

  def shutdown(self):
    self._shutdown = True
    self.socket.close()


class _ProxyRequestHandler(SocketServer.StreamRequestHandler):
  def __init__(self, *args):
    self._logger = logging.getLogger('ConnectionProxy')
    SocketServer.StreamRequestHandler.__init__(self, *args)

  def handle(self):
    self._logger.debug('proxy connection from: %s:%s' % self.client_address)
    clientSock = self.request
    targetSock = socket.socket()
    try:
      targetSock.connect(self.server._target)
    except socket.error:
      self._logger.warning('failed to connect to proxy target: %s:%s' %
                           self.server._target)
      return

    conn = self.server._stats.connectionNew(clientSock.getpeername(),
                                            targetSock.getpeername())
    clientToTarget = _SocketForwarder(self.server, clientSock, targetSock,
                                      conn=conn)
    clientToTarget.setDaemon(True)
    clientToTarget.start()

    targetToClient = _SocketForwarder(self.server, targetSock, clientSock,
                                      conn=conn)
    targetToClient.setDaemon(True)
    targetToClient.start()

    clientToTarget.join()
    clientSock.close()
    targetSock.close()
    targetToClient.join()

    self._logger.debug('closing connection from %s:%s' % self.client_address)
    self.server._stats.connectionDel(conn)


class _SocketForwarder(threading.Thread):
  '''Forward data between Socket objects.'''
  def __init__(self, server, source, target, conn=None):
    '''Create a forwarder.

    Args:
      server: _ThreadingTCPServer object
      source: source socket object
      target: target socket object
      conn: connection.Connection object
    '''
    threading.Thread.__init__(self)
    self._logger = logging.getLogger('ConnectionProxy')
    self._server = server
    self._source = source
    self._target = target
    self._conn = conn

  def run(self):
    self._source.settimeout(0.5)
    self._target.settimeout(0.5)

    while True:
      try:
        buf = self._source.recv(BUFFER_SIZE)
        bytes = len(buf)
        if bytes == 0:
          break
        else:
          self._target.send(buf)
          self._conn.bytesInc(bytes)
      except socket.timeout:
        pass
      except socket.error, e:
        break

      if self._server._shutdown:
        break