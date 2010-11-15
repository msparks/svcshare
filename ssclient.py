#!/usr/bin/python
import logging
import optparse
import os
import sys
import time

from svcshare import client
from svcshare import exc
from svcshare import network
from svcshare import peertracker
from svcshare import protocoldirector
from svcshare import scheduler

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


def parseArgs():
  parser = optparse.OptionParser()
  parser.add_option('-p', '--pdb', action='store_true', default=False,
                    help='drop into PDB after initialization')
  (options, args) = parser.parse_args()
  return (options, args)


def main():
  options, args = parseArgs()
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

  logging.debug('Initializing scheduler')
  sched = scheduler.Scheduler(pd, c)
  sched.isolationIs('open')

  # pause client
  #control.pausedIs(True)

  if options.pdb:
    time.sleep(2)
    import pdb
    pdb.set_trace()

  logging.debug('Main thread sleeping')
  while True:
    time.sleep(60)


if __name__ == "__main__":
    main()
