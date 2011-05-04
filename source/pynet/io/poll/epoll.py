# @copyright
# @license

from __future__ import absolute_import

from .ipoll import *

import select as pyselect

##############################################################################
##############################################################################

class Poller(IPoller):
    r"""
    Uses level-triggering
    """
    
    poller = None
    
    def __init__(self):
        super(Poller, self).__init__()
        self.poller = pyselect.epoll()
        
    def __exit__(self, *args, **kwargs):
        ret = super(Poller, self).__exit__(self, *args, **kwargs)
        self.poller.close()
        return ret

    def __setitem__(self, fd, events):
        flags = 0
        if POLLIN & events:
            flags |= pyselect.EPOLLIN | pyselect.EPOLLPRI
        if POLLOUT & events:
            flags |= pyselect.EPOLLOUT
        if fd in self:
            self.poller.modify(fd, flags)
        else:
            self.poller.register(fd, flags)
        super(Poller, self).__setitem__(fd, events)
    
    def __delitem__(self, fd):
        super(Poller, self).__delitem__(fd)
        self.poller.unregister(fd)

    def poll(self, timeout=0.0):
        events = self.poll.poll(timeout)
        
        for fd, flags in events:
            if not (flags & (pyselect.EPOLLIN | pyselect.EPOLLPRI | pyselect.EPOLLOUT | pyselect.EPOLLHUP)):
                yield (fd, POLLEX,)
            else:
                if flags & (pyselect.EPOLLIN | pyselect.EPOLLPRI):
                    yield (fd, POLLIN,)
                if flags & pyselect.EPOLLOUT:
                    yield (fd, POLLOUT,)
                if flags & pyselect.EPOLLHUP:
                    yield (fd, POLLHUP,)

##############################################################################
##############################################################################
