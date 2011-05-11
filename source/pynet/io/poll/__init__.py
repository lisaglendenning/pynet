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

import sys

if sys.version_info[0] != 2:
    raise RuntimeError("Python version %d unsupported" % sys.version_info[0])


if sys.version_info[1] < 4 or sys.version_info[1] > 6:
    raise RuntimeError("Python version 2.%d unsupported" % sys.version_info[1])

# relative imports are not available until 2.5
if sys.version_info[1] == 4:
    from py24 import *
else: # untested for 2.5
    from .py26 import *
