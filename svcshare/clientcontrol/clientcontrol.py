import os
import re
import sys

from svcshare.clientcontrol import hellanzbcontrol


class ClientControl:
  """Interface to the client using the shared service."""
  def __init__(self, client_name, client_url):
    """Create a ClientControl object.

    Args:
      client_name: client name (supported: 'hellanzb', None)
      client_url: URL to control client
    """
    self.client_name = client_name
    self.client_url = client_url

    if client_name == "hellanzb":
      self.client = hellanzbcontrol.HellanzbControl(client_url)
    else:
      self.client = None

  def pause(self):
    if self.client:
      return self.client.pause()

  def resume(self):
    if self.client:
      return self.client.resume()

  def eta(self):
    if self.client:
      return self.client.eta()

  def queue_size(self):
    if self.client:
      return self.client.queue_size()

  def is_paused(self):
    if self.client:
      return self.client.is_paused()

  def enqueue(self, id):
    if self.client:
      return self.client.enqueue(id)
