import logging
import os
import re
import socket
import xmlrpclib

from svcshare.clientcontrol import clientcontrolbase


class HellanzbControl(clientcontrolbase.ClientControlBase):
  """Control for the hellanzb client."""
  def __init__(self, xmlrpc_url):
    self._url = xmlrpc_url
    self._server = xmlrpclib.ServerProxy(self._url)

  def _call(self, method_name, *args):
    try:
      return getattr(self._server, method_name)(*args)
    except socket.error:
      logging.warning("failed to make API call '%s' to Hellanzb. Check URL." %
                      method_name)
      raise

  def _status(self):
    resp = self._call("status")
    current_item_size = 0  # MB
    queue_size = 0         # MB
    queue_items = 0
    speed = 0              # KB/s

    current_item_size = resp["queued_mb"]

    for item in resp["queued"]:
      if "total_mb" in item:
        queue_size += item["total_mb"]
      else:
        queue_size += 1  # sometimes items don't list size

    queue_items = len(resp["queued"])
    speed = resp["rate"]

    return current_item_size, queue_size, queue_items, speed

  def pause(self):
    try:
      resp = self._call("pause")
    except socket.error:
      return False
    else:
      return resp["is_paused"] == True

  def resume(self):
    try:
      resp = self._call("continue")
    except socket.error:
      return False
    else:
      return resp["is_paused"] == False

  def eta(self):
    try:
      return self._eta(self._status())
    except socket.error:
      return None

  def queue_size(self):
    try:
      return self._queue_size(self._status())
    except socket.error:
      return 0

  def is_paused(self):
    try:
      resp = self._call("status")
    except socket.error:
      return True
    return resp["is_paused"]

  def enqueue(self, id):
    try:
      resp = self._call("enqueuenewzbin", id)
    except socket.error:
      return False
    else:
      return True
