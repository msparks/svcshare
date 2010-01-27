import logging
import random
import sys
import threading
import time

from svcshare import exc
from svcshare import clientqueue
from svcshare.clientcontrol import hellanzbcontrol
from svcshare.clientcontrol import sabnzbdcontrol


class ClientMonitor(object):
  def __init__(self, client, clientName, clientUrl, clientKey):
    self._client = client
    self._name = clientName
    self._url = clientUrl
    self._logger = logging.getLogger('ClientMonitor')
    self._control = None
    self._initializeControl(clientName, clientUrl, clientKey)

  def _initializeControl(self, clientName, clientUrl, clientKey):
    if clientName == 'hellanzb':
      self._control = hellanzbcontrol.HellanzbControl(clientUrl)
    elif clientName == 'sabnzbd':
      self._control = sabnzbdcontrol.SabnzbdControl(clientUrl, clientKey)
    else:
      self._logger.critical('unrecognized client: %s' % clientName)
      raise exc.RangeException

  def _checkQueue(self):
    curQueue = self._control.queue()
    oldQueue = self._client.queue()
    if curQueue != oldQueue:
      self._client.queueIs(curQueue)

  def control(self):
    '''Get the client control object'''
    return self._control

  def start(self):
    while True:
      try:
        self._checkQueue()
      except exc.ResourceException:
        self._logger.critical('caught ResourceException. Exiting.')
      time.sleep(10)


class Client(object):
  def __init__(self, clientName, clientUrl, clientKey):
    # Hack: this needs to be done in the main thread to avoid crashing on OS X
    if sys.platform == 'darwin':
      from ctypes import cdll
      from ctypes.util import find_library
      cdll.LoadLibrary(find_library('SystemConfiguration'))

    self._queue = clientqueue.ClientQueue()
    self._monitor = ClientMonitor(self, clientName, clientUrl, clientKey)
    self._monitorThread = threading.Thread(target=self._monitor.start)
    self._monitorThread.daemon = True
    self._monitorThread.start()
    self._logger = logging.getLogger('Client')

  def queue(self):
    return self._queue

  def queueIs(self, queue):
    self._logger.debug('queue now has %d items' % queue.items())
    self._queue = queue

  def control(self):
    return self._monitor.control()