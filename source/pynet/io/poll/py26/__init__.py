
from __future__ import absolute_import

import select

if hasattr(select, 'epoll'): # only in 2.6 or higher
    from .epolls import *
elif hasattr(select, 'poll'):
    from .polls import *
elif hasattr(select, 'select'):
    from .selects import *
else:
    raise RuntimeError(select)
