import logging
import socket
import threading
import time
import SocketServer
from nose.tools import *
from svcshare import connectionproxy
from svcshare import exc


PROXY_SERVER_ADDRESS = ('localhost', 57819)
ECHO_SERVER_ADDRESS = ('localhost', 23949)
echoServer = None
echoServerThread = None


class EchoServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
  class _Handler(SocketServer.StreamRequestHandler):
    def handle(self):
      logging.debug('EchoServer got connection')

      while True:
        buf = self.request.recv(4096)
        if len(buf) != 0:
          logging.debug('EchoServer sending %s bytes' % len(buf))
          self.request.send(buf)
        else:
          break

      logging.debug('EchoServer closing connection')
      self.request.close()

  def __init__(self, address):
    self.allow_reuse_address = True
    SocketServer.TCPServer.__init__(self, address, self._Handler)


def echoServerThreadFunc():
  global echoServer
  echoServer = EchoServer(ECHO_SERVER_ADDRESS)
  echoServer.serve_forever()


def startEchoServer():
  global echoServerThread
  echoServerThread = threading.Thread(target=echoServerThreadFunc)
  echoServerThread.setDaemon(True)
  echoServerThread.start()


startEchoServer()


class test_ConnectionProxy:
  def setUp(self):
    self._addr = PROXY_SERVER_ADDRESS
    self._target = ECHO_SERVER_ADDRESS
    self._cp = connectionproxy.ConnectionProxy(self._addr, self._target)
    self._stats = self._cp.stats()

    # wait for echo server and connection proxy to start
    time.sleep(1)

  def tearDown(self):
    self._stopProxy()

  def _connectToProxy(self):
    self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self._sock.settimeout(1)
    self._sock.connect(self._addr)

  def _disconnectFromProxy(self):
    self._sock.close()

  def _startProxy(self):
    self._cp.runningIs(True)
    time.sleep(1)

  def _stopProxy(self):
    self._cp.runningIs(False)
    time.sleep(1)

  def _sendToProxy(self, data):
    return self._sock.send(data)

  def _recvFromProxy(self):
    return self._sock.recv(65536)

  @raises(socket.error)
  def test_notRunning(self):
    assert_equals(self._cp.running(), False)
    assert_equals(self._stats.activeConnections(), 0)
    self._connectToProxy()

  def test_isRunning(self):
    self._startProxy()
    self._connectToProxy()
    buf = 'foo bar baz'
    self._sendToProxy(buf)
    assert_equals(self._recvFromProxy(), buf)
    assert_equals(self._stats.activeConnections(), 1)

  def test_largeTransfer(self):
    self._startProxy()
    self._connectToProxy()
    buf = 'a' * 23942
    assert_equals(self._sendToProxy(buf), len(buf))
    time.sleep(1)
    assert_equals(self._recvFromProxy(), buf)
    assert_equals(self._stats.activeConnections(), 1)
    assert_equals(self._stats.totalTransferred(), len(buf) * 2)

  def test_closeOpenConnections(self):
    self._startProxy()
    self._connectToProxy()
    buf = 'aaaaaaaaaa'
    self._sendToProxy(buf)
    self._recvFromProxy()
    self._stopProxy()
    assert_equals(self._recvFromProxy(), '')

  def test_multipleSerialConnections(self):
    self._startProxy()
    self._connectToProxy()
    time.sleep(1)
    assert_equals(self._stats.activeConnections(), 1)
    self._disconnectFromProxy()
    time.sleep(1)
    assert_equals(self._stats.activeConnections(), 0)
    assert_equals(self._stats.totalConnections(), 1)
    self._connectToProxy()
    time.sleep(1)
    assert_equals(self._stats.activeConnections(), 1)
    assert_equals(self._stats.totalConnections(), 2)

  def test_multipleSerialTransfers(self):
    buf = 'a' * 200
    self._startProxy()
    self._connectToProxy()
    self._sendToProxy(buf)
    self._recvFromProxy()
    self._disconnectFromProxy()
    self._connectToProxy()
    self._sendToProxy(buf)
    self._recvFromProxy()
    self._disconnectFromProxy()
    time.sleep(1)
    assert_equals(self._stats.activeConnections(), 0)
    assert_equals(self._stats.totalConnections(), 2)
    assert_equals(self._stats.totalTransferred(), 4 * len(buf))