# @copyright
# @license

r""" Interface to system-dependent file polling.

History
-------

- April 25, 2010 @lisa: Created

This module is intended for socket file descriptors.  Not
tested with other types of files.

http://scotdoyle.com/python-epoll-howto.html

"""

import select

from ipoller import *

Poller = None

if hasattr(select, 'epoll'):
    import epoller
    Poller = epoller.Poller
elif hasattr(select, 'poll'):
    import poller
    Poller = poller.Poller
elif hasattr(select, 'select'):
    import selecter
    Poller = selecter.Poller
else:
    raise RuntimeError(select)

