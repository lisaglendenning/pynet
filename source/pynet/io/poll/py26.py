
from __future__ import absolute_import

import select as pyselect

if hasattr(pyselect, 'epoll'):
    from .epoll import *
elif hasattr(pyselect, 'poll'):
    from .poll import *
elif hasattr(pyselect, 'select'):
    from .select import *
else:
    raise RuntimeError(pyselect)
