import os
import re
import socket
import xmlrpclib


class HellanzbControl:
  """Control for the hellanzb client.
  """
  def __init__(self, xmlrpc_url):
    self._url = xmlrpc_url
    self._server = xmlrpclib.ServerProxy(self._url)

  def pause(self):
    try:
      resp = self._server.pause()
    except socket.error:
      return False
    else:
      return resp["is_paused"] == True

  def resume(self):
    try:
      resp = getattr(self._server, "continue")()
    except socket.error:
      return False
    else:
      return resp["is_paused"] == False

  def _status(self):
    resp = self._server.status()
    current_item_size = 0  # MB
    queue_size = 0         # MB
    queue_items = 0
    speed = 0              # KB/s

    current_item_size = resp["queued_mb"]

    for item in resp["queued"]:
      queue_size += item["total_mb"]

    queue_items = len(resp["queued"])
    speed = resp["rate"]

    return current_item_size, queue_size, queue_items, speed

  def _eta_time(self, size, speed):
    if speed == 0:
      return 0, 0

    eta = size * 1024 / float(speed)  # seconds
    eta_h = int(eta / 3600)
    eta_m = int((eta % 3600) / 60)

    return eta_h, eta_m

  def eta(self):
    try:
      current_item_size, queue_size, queue_items, speed = self._status()
    except socket.error:
      return None

    total_size = current_item_size + queue_size
    eta_str = ""

    if speed > 0:
      total_eta_h, total_eta_m = self._eta_time(total_size, speed)
      cur_eta_h, cur_eta_m = self._eta_time(current_item_size, speed)
      eta_str = " [%dh%dm / %dh%dm]" % (cur_eta_h, cur_eta_m,
                                        total_eta_h, total_eta_m)

    plural = queue_items == 1 and "item" or "items"
    msg = "%d MB + %d MB queued (%d %s) @ %d KB/s%s"

    return msg % (current_item_size, queue_size,
                  queue_items, plural, speed, eta_str)

  def queue_size(self):
    try:
      current_item_size, queue_size, queue_items, speed = self._status()
    except socket.error:
      return 0

    total_size = current_item_size + queue_size
    return total_size

  def is_paused(self):
    try:
      resp = self._server.status()
    except socket.error:
      return True
    return resp["is_paused"]

  def enqueue(self, id):
    try:
      resp = self._server.enqueuenewzbin(id)
    except socket.error:
      return False
    else:
      return True
