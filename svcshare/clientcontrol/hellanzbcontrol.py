import logging
import socket
import xmlrpclib

from svcshare import clientqueue
from svcshare import exc


class HellanzbControl(object):
  '''Control for the hellanzb client.'''
  def __init__(self, xmlrpc_url):
    self._url = xmlrpc_url
    self._server = xmlrpclib.ServerProxy(self._url)
    self._logger = logging.getLogger('HellanzbControl')

  def _call(self, methodName, *args):
    try:
      return getattr(self._server, methodName)(*args)
    except socket.error:
      self._logger.warning('failed to make API call "%s" to Hellanzb. '
                           'Check URL.' % method_name)
      raise exc.ResourceException

  def pausedIs(self, paused):
    if paused:
      self._call('pause')
    else:
      self._call('continue')

  def paused(self):
    response = self._call('status')
    try:
      return response['is_paused']
    except KeyError:
      self._logger.warning('is_paused not reported in status information')
      raise exc.ResourceException

  def rate(self):
    _rate = 0
    try:
      response = self._call('status')
      _rate = response['rate']
    except KeyError:
      self._logger.warning('rate not reported in status information')
      raise exc.ResourceException
    else:
      return _rate

  def newzbinItemNew(self, id):
    self._call('enqueuenewzbin', id)

  def queue(self):
    response = self._call('status')
    _queue = clientqueue.ClientQueue()

    if response['currently_downloading']:
      currentItemSize = response['queued_mb']
      currentItemName = response['currently_downloading'][0]['id']
      _queue.itemIs(clientqueue.ClientQueueItem(currentItemName,
                                                currentItemSize))

    for item in response['queued']:
      if 'total_mb' in item:
        itemSize = item['total_mb']
      else:
        itemSize = 1024  # sometimes items don't list size
      itemName = item['id']
      _queue.itemIs(clientqueue.ClientQueueItem(itemName, itemSize))

    return _queue