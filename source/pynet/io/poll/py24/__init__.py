
import select

if hasattr(select, 'poll'):
    from polls import *
elif hasattr(select, 'select'):
    from selects import *
else:
    raise RuntimeError(select)
