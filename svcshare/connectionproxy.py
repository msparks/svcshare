import logging
import socket
import SocketServer
import threading

import connectionstats

BUFFER_SIZE = 1048576


class SocketForwarder(threading.Thread):
  """Forward data between Socket objects."""
  def __init__(self, source, target, stats=None, continue_event=None):
    """Create a forwarder.

    Args:
      source: source Socket object
      target: target Socket object
      stats: connectionstats.Connection object
      continue_event: Event object to pause/continue transfer
    """
    threading.Thread.__init__(self)
    self.source = source
    self.target = target
    self.conn_stats = stats
    if not continue_event:
      continue_event = threading.Event()
      continue_event.set()
    self.continue_event = continue_event

  def run(self):
    while True:
      try:
        buf = self.source.recv(BUFFER_SIZE)
        bytes = len(buf)
        if bytes == 0:
          return
      except:
        return

      try:
        self.target.send(buf)
      except:
        return

      if self.conn_stats:
        self.conn_stats.transfer(bytes)

      if not self.continue_event.isSet():
        return


class ThreadingTCPServer(SocketServer.ThreadingMixIn,
                         SocketServer.TCPServer):
  pass


class ProxyRequestHandler(SocketServer.StreamRequestHandler):
  def handle(self):
    logging.info("proxy connection from: %s:%s" % self.client_address)
    s = socket.socket()
    try:
      s.connect(self.server.target)
    except:
      logging.warning("failed to connect to proxy target: %s:%s" %
                      self.server.target)
      return
    conn_stats = self.server.stats.register(self.request.getpeername(),
                                            s.getpeername())
    continue_event = self.server.continue_event
    c2t = SocketForwarder(self.request, s, stats=conn_stats,
                          continue_event=continue_event)
    t2c = SocketForwarder(s, self.request, stats=conn_stats,
                          continue_event=continue_event)
    c2t.setDaemon(True)
    t2c.setDaemon(True)
    c2t.start()
    t2c.start()
    c2t.join()
    t2c.join()
    s.close()
    logging.info("closing connection from %s:%s" % self.client_address)
    logging.info("transferred %s bytes" % conn_stats.bytes)
    self.server.stats.close(conn_stats)


class ConnectionProxyServer(object):
  def __init__(self, address, target):
    """Create a connection proxy.

    Args:
      address: (host, port) tuple for the local server
      target: (host, port) tuple for the target server
    """
    self._server = ThreadingTCPServer(address, ProxyRequestHandler)
    self._server.stats = connectionstats.ConnectionStats()
    self._server.target = target
    self._server.continue_event = threading.Event()
    self._server.continue_event.set()

  def _server_thread(self):
    while True:
      try:
        client, client_addr = self._server.get_request()
      except socket.error, e:
        continue
      if (self._server.continue_event.isSet() and
          self._server.verify_request(client, client_addr)):
        self._server.process_request(client, client_addr)
      else:
        client.close()

  def start(self):
    """Start the proxy.
    """
    logging.debug("starting threading connection proxy server")
    self._thread = threading.Thread(target=self._server_thread)
    self._thread.setDaemon(True)
    self._thread.start()

  def pause(self):
    """Pause the proxy.

    This will cause all current connections to close and all future connections
    will be refused until the proxy resumes.
    """
    logging.debug("pausing proxy")
    self._server.continue_event.clear()

  def resume(self):
    """Resume the proxy after being paused.
    """
    logging.debug("resuming proxy")
    self._server.continue_event.set()

  def is_paused(self):
    """Return True if the proxy is paused.

    Returns:
      True is the proxy is paused.
    """
    return not self._server.continue_event.isSet()

  def num_active(self):
    """Get the number of active connections through the proxy.

    Returns:
      integer
    """
    return len(self._server.stats.active_connections())

  def transferred(self):
    """Total number of bytes transferred through the proxy.

    Returns:
      integer
    """
    return self._server.stats.total_transferred()
