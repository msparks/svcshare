import logging
import urllib
import urlparse

try:
  import json
except ImportError:
  import simplejson as json

from svcshare import clientqueue
from svcshare import exc


class SabnzbdControl(object):
  '''Control for the SABnzbd client.'''
  def __init__(self, url, apikey):
    self._url = url
    self._apikey = apikey
    self._logger = logging.getLogger('SabnzbdControl')

  def _call(self, mode, params=None):
    if params is None:
      params = {}
    enc = urllib.urlencode(params)
    url = urlparse.urljoin(self._url,
                           '/sabnzbd/api?mode=%s&apikey=%s&%s' %
                           (mode, self._apikey, enc))

    try:
      urlHandle = urllib.urlopen(url)
    except IOError:
      self._logger.warning('failed to make API call "%s" to SABnzbd. '
                           'Check URL.' % mode)
      raise exc.ResourceException

    data = urlHandle.read()
    try:
      return json.loads(data)
    except ValueError:
      self._logger.warning('failed to parse JSON response')
      raise exc.ResourceException
    return data

  def pausedIs(self, paused):
    if paused:
      self._call('pause')
    else:
      self._call('resume')

  def paused(self):
    response = self._call('qstatus', {'output': 'json'})
    try:
      return response['paused']
    except KeyError:
      self._logger.warning('paused not reported in status information')
      raise exc.ResourceException

  def rate(self):
    _rate = 0
    response = self._call('qstatus', {'output': 'json'})
    try:
      _rate = response['kbpersec']
    except KeyError:
      self._logger.warning('kbpersec not reported in status information')
      raise exc.ResourceException
    else:
      return _rate

  def newzbinItemNew(self, id):
    self._call('addid', {'name': id})

  def queue(self):
    response = self._call('qstatus', {'output': 'json'})
    _queue = clientqueue.ClientQueue()

    for item in response['jobs']:
      if 'mbleft' in item:
        itemSize = item['mbleft']
      else:
        itemSize = 1024
      itemName = item['msgid']
      _queue.itemIs(clientqueue.ClientQueueItem(itemName, itemSize))

    return _queue