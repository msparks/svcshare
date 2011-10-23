import os
import re
import sys

from svcshare.clientcontrol import hellanzbcontrol
from svcshare.clientcontrol import sabnzbdcontrol


class ClientControl(object):
  """Interface to the client using the shared service."""
  def __init__(self, proxy, client_name, client_url, client_key):
    """Create a ClientControl object.

    Args:
      proxy: ConnectionProxyServer instance
      client_name: client name (supported: 'hellanzb', 'sabnzbd', None)
      client_url: URL to control client
    """
    self.client_name = client_name
    self.client_url = client_url
    self.proxy = proxy

    if client_name == "hellanzb":
      self.client = hellanzbcontrol.HellanzbControl(client_url)
    elif client_name == "sabnzbd":
      self.client = sabnzbdcontrol.SabnzbdControl(client_url, client_key)
    else:
      self.client = None

  def pause(self):
    self.proxy.runningIs(False)
    if self.client:
      return self.client.pause()

  def resume(self):
    self.proxy.runningIs(True)
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
    return (not self.proxy.running())

  def enqueue(self, id):
    if self.client:
      return self.client.enqueue(id)
