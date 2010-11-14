import logging

from svcshare import exc
from svcshare.clientcontrol import sabnzbdcontrol


class ClientControl(object):
  '''Interface to the client using the shared service.'''
  def __init__(self, proxy, client_name, client_url, client_key):
    '''Create a ClientControl object.

    Args:
      proxy: ConnectionProxyServer instance
      client_name: client name (supported: 'sabnzbd')
      client_url: URL to control client
    '''
    self._proxy = proxy
    self._logger = logging.getLogger('ClientControl')

    if client_name == 'sabnzbd':
      self._client = sabnzbdcontrol.SabnzbdControl(client_url, client_key)
    else:
      self._logger.warning('unsupported client: %s' % client_name)
      raise exc.RangeException

  def paused(self):
    return not self._proxy.running()

  def pausedIs(self, paused):
    self._proxy.runningIs(not paused)
    self._client.pausedIs(paused)

  def queue(self):
    return self._client.queue() if self._client else None

  def queueItemIdIs(self, id):
    return self._client.enqueue(id)
