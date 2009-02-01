import os
import re
import sys

from svcshare.clientcontrol import hellanzbcontrol


class ClientControl(object):
  """Interface to the client using the shared service."""
  def __init__(self, proxy, client_name, client_url):
    """Create a ClientControl object.

    Args:
      proxy: ConnectionProxyServer instance
      client_name: client name (supported: 'hellanzb', None)
      client_url: URL to control client
    """
    self.client_name = client_name
    self.client_url = client_url
    self.proxy = proxy

    if client_name == "hellanzb":
      self.client = hellanzbcontrol.HellanzbControl(client_url)
    else:
      self.client = None

  def pause(self):
    self.proxy.pause()
    if self.client:
      return self.client.pause()

  def resume(self):
    self.proxy.resume()
    if self.client:
      return self.client.resume()

  def eta(self):
    if self.client:
      return self.client.eta()
    else:
      return ""

  def queue_size(self):
    if self.client:
      return self.client.queue_size()
    else:
      return 0

  def is_paused(self):
    if self.client:
      return self.client.is_paused()
    return self.proxy.is_paused()

  def enqueue(self, id):
    if self.client:
      return self.client.enqueue(id)
