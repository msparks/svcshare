import httplib
import socket
import urllib
import urlparse
import time


class Report(object):
  def __init__(self, bytes_transferred, duration):
    self._bytes = bytes_transferred
    self._duration = duration

  def send(self, url, key):
    end = time.time()
    start = end - self._duration
    data = {"private_key": key,
            "bytes": self._bytes,
            "start": start,
            "end": end}
    params = urllib.urlencode(data)
    headers = {"Content-type": "application/x-www-form-urlencoded"}

    parse = urlparse.urlparse(url)
    hostname = parse.hostname
    port = parse.port or 80

    if not hostname:
      return False

    try:
      http = httplib.HTTPConnection(parse.netloc, parse.port)
      http.request("POST", "/post", params, headers)
      resp = http.getresponse()
    except (socket.gaierror, socket.error):
      return False
    else:
      return resp.read(amt=2) == "ok"
