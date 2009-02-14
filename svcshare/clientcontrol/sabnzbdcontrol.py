import logging
import os
import urllib
import urlparse

try:
  import json
except ImportError:
  import simplejson as json

from svcshare.clientcontrol import clientcontrolbase


class SabnzbdControl(clientcontrolbase.ClientControlBase):
  """Control for the SABnzbd client."""
  def __init__(self, url):
    self._url = url

  def _api_call(self, mode, params=None):
    if params is None:
      params = {}
    enc = urllib.urlencode(params)
    url = urlparse.urljoin(self._url,
                           "/sabnzbd/api?mode=%s&%s" % (mode, enc))

    try:
      url_handle = urllib.urlopen(url)
    except IOError:
      logging.warning("failed to make API call '%s' to SABnzbd. Check URL." %
                      mode)
      raise

    data = url_handle.read()
    try:
      return json.loads(data)
    except ValueError:
      return data

  def pause(self):
    try:
      return self._api_call("pause").startswith("ok")
    except IOError:
      return False

  def resume(self):
    try:
      return self._api_call("resume").startswith("ok")
    except IOError:
      return False

  def _status(self):
    status = self._api_call("qstatus", {"output": "json"})
    current_item_size = 0  # MB
    queue_size = 0         # MB
    queue_items = 0
    speed = 0              # KB/s

    if status["jobs"]:
      current_item_size = status["jobs"][0]["mbleft"]

    if len(status["jobs"]) > 1:
      queue_items = len(status["jobs"]) - 1

      for item in status["jobs"]:
        if "mbleft" in item:
          queue_size += item["mbleft"]
        else:
          queue_size += 1
    else:
      queue_items = 0

    speed = status["kbpersec"]

    return current_item_size, queue_size, queue_items, speed

  def eta(self):
    try:
      return self._eta(self._status())
    except IOError:
      return None

  def queue_size(self):
    try:
      return self._queue_size(self._status())
    except IOError:
      return 0

  def is_paused(self):
    try:
      status = self._api_call("qstatus", {"output": "json"})
      return status["paused"]
    except IOError:
      return True

  def enqueue(self, id):
    try:
      return self._api_call("addid", {"name": id}).startswith("ok")
    except IOError:
      return False
