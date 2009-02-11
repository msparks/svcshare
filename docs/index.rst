svcshare
========

Requirements
------------

As of version 0.3.0, the "simplejson" Python module is required for Python
versions prior to 2.6. It can be easily installed with::

  $ easy_install -U simplejson

:command:`easy_install` is part of the *setuptools* package, which is available
for download for various platforms, including Windows.

Installation
------------

#. Ensure all requirements are met.

#. Following a :command:`git clone`, copy :file:`config.py.dist` to
   :file:`config.py` and edit :file:`config` with your favorite editor. The
   items should be self-explanatory.

#. Configure your client to use the tunnel/proxy created by svcshare. This
   only requires changing your current settings to use *localhost:8999* as the
   server (or wherever svcshare is running).

Running
-------

Start your client first and then run :command:`./ssclient.py`.

On startup, svcshare will pause the client and proxy, and connect to the IRC
server specified in the configuration.

Commands
--------

The svcshare program is controlled by commands sent to the IRC channel or the
bot directly.

Two commands are available only in the public channel: :command:`.status`,
:command:`.version`.

:command:`.status`:
  Request client status from any bots which active connections.

:command:`.version`:
  Request version information from all bots.

The rest of the commands can be used in the public channel by addressing a bot
using :command:`<botnick>: <command> [<extra>]`, or by sending a private
message to the bot with :command:`<command> [<extra>]`.

:command:`election`:
  *Aliases: resume, continue*
  Start a major election. A major election requests queue sizes from peers, and
  if we have the smallest queue, the client is resumed.

:command:`enqueue <id>`:
  *Aliases: enq*

  Add report with id *<id>* to the queue.

:command:`force [<mb>]`:
  Activate force mode. This immediately resumes the client without first
  performing an election. If *<mb>* is specified, election requests from peers
  will be ignored until *<mb>* has been processed, effectively monopolizing the
  shared resource. If *<mb>* is not specified, it is assumed to be 0, and
  election requests from peers are not ignored.

:command:`halt [<minutes>]`:
  Activate halt mode. This immediately pauses the client and will not
  automatically resume client for any reason unless *<minutes>* is specified
  and is greater than 0, and *<minutes>* minutes have passed. If *<minutes>* is
  not specified, an indefinite halt is activated. Indefinite halts do not end
  until svcshare is restarted or :command:`unhalt` or :command:`force` is used.
  While in halt mode, no elections will be started, and an empty queue will be
  reported to peers.

:command:`pause`:
  Pause client and proxy. This will also clear a force.

:command:`unhalt`:
  Deactivate halt mode.
