import httplib
import socket
import threading
import time
import urllib
import urlparse


class ReportThread(threading.Thread):
  def __init__(self, bytes_transferred, duration, url, key):
    threading.Thread.__init__(self)
    self._bytes = bytes_transferred
    self._duration = duration
    self._url = url
    self._key = key

  def run(self):
    end = time.time()
    start = end - self._duration
    data = {"private_key": self._key,
            "bytes": self._bytes,
            "start": start,
            "end": end}
    params = urllib.urlencode(data)
    headers = {"Content-type": "application/x-www-form-urlencoded"}

    # pull hostname and port from URL
    parse = urlparse.urlsplit(self._url)
    split = parse[1].split(":")
    if len(split) > 1:
      hostname, port = split[0], split[1]
    else:
      hostname, port = split[0], 80

    if not hostname:
      return False

    try:
      http = httplib.HTTPConnection(hostname, port)
      http.request("POST", "/post", params, headers)
      resp = http.getresponse()
    except (socket.gaierror, socket.error):
      return False
    else:
      return resp.read(amt=2) == "ok"


class Report(object):
  def __init__(self, bytes_transferred, duration):
    self._bytes = bytes_transferred
    self._duration = duration

  def send(self, url, key):
    thr = ReportThread(self._bytes, self._duration, url, key)
    thr.setDaemon(True)
    thr.start()
