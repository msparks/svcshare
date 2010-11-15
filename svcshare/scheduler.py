import logging
import threading
import time

from svcshare import exc


# ISOLATION is the ability for the scheduler to run.
#   isolated makes the scheduler inert
#   open allows the scheduler to make decisions and affect the local state
ISOLATION = {'isolated': 'isolated',
             'open': 'open'}


class Scheduler(object):
  def __init__(self, pd, client):
    self._pd = pd
    self._client = client
    self._logger = logging.getLogger('Scheduler')
    self._schedulerThread = threading.Thread(target=self._scheduler)
    self._schedulerThread.daemon = True
    self._isolation = ISOLATION['isolated']

  def _scheduler(self):
    self._logger.debug('scheduler thread starting')
    while True:
      if self._isolation == ISOLATION['isolated']:
        time.sleep(5)
        continue
      self._logger.debug('running')
      time.sleep(60)

  def isolation(self):
    return self._isolation

  def isolationIs(self, iso):
    if iso == 'isolated':
      self._isolation = ISOLATION[iso]
    elif iso == 'open':
      self._isolation = ISOLATION[iso]
      if not self._schedulerThread.is_alive():
        self._schedulerThread.start()
