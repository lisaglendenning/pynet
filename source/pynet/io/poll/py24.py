
import select

if hasattr(select, 'epoll'):
    from epolls import *
elif hasattr(select, 'poll'):
    from polls import *
elif hasattr(select, 'select'):
    from selects import *
else:
    raise RuntimeError(select)
