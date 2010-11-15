#!/usr/bin/python
import logging
import os
import sys
import time

from svcshare import client
from svcshare import network
from svcshare import peertracker
from svcshare import protocoldirector
from svcshare import exc

import config

__version__ = 2, 0, 0


def initializeSignals():
  if sys.platform != 'darwin' and sys.platform != 'linux2':
    return
  import signal

  def sighupHandler(signum, frame):
    logging.warning('sighup received, ignoring')

  def sigintHandler(signum, frame):
    logging.critical('sigint received, exiting')
    sys.exit(1)

  def sigusr1Handler(signum, frame):
    logging.info('sigusr1 received, dropping into debugger')
    import pdb
    pdb.set_trace()

  signal.signal(signal.SIGHUP, sighupHandler)
  signal.signal(signal.SIGINT, sigintHandler)
  signal.signal(signal.SIGUSR1, sigusr1Handler)


def main():
  initializeSignals()

  # set up logging
  _fmt = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
  logging.basicConfig(level=logging.DEBUG,
                      format=_fmt)

  logging.debug('Initializing client monitor')
  ck = getattr(config, 'SERVICE_CLIENT_KEY', '')
  c = client.Client(config.SERVICE_CLIENT, config.SERVICE_CLIENT_URL, ck)
  control = c.control()

  logging.debug('Initializing network subsystem')
  _useSSL = getattr(config, 'BOT_USE_SSL', False)
  net = network.Network(config.BOT_IRCSERVER, config.BOT_IRCPORT,
                        config.BOT_NICK, config.BOT_CHANNEL,
                        ssl=_useSSL)
  net.isolationIs('open')

  logging.debug('Initializing protocol director')
  pd = protocoldirector.ProtocolDirector(net, c)

  logging.debug('Initializing peer tracker')
  pt = peertracker.PeerTracker()
  pt.notifierIs(pd)

  # pause client
  #control.pausedIs(True)

  logging.debug('Main thread sleeping')
  while True:
    time.sleep(60)


if __name__ == "__main__":
    main()
