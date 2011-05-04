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

from __future__ import absolute_import

import select as pyselect

from .ipoll import *

if hasattr(pyselect, 'epoll'):
    from .epoll import *
elif hasattr(pyselect, 'poll'):
    from .poll import *
elif hasattr(pyselect, 'select'):
    from .select import *
else:
    raise RuntimeError(pyselect)

