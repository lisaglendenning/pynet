# @copyright
# @license

from __future__ import absolute_import

from .dict import *

from select import epoll, EPOLLIN, EPOLLPRI, EPOLLOUT, EPOLLHUP

##############################################################################
##############################################################################

class Poller(Dict):
    r"""
    Uses level-triggering
    """
    
    poller = None
    
    def __init__(self):
        super(Poller, self).__init__()
        self.poller = epoll()
        
    def __del__(self,):
        self.clear()
        self.poller.close()
        try:
            super(Poller, self).__del__()
        except AttributeError:
            pass

    def __setitem__(self, fd, events):
        flags = 0
        if POLLIN & events:
            flags |= EPOLLIN | EPOLLPRI
        if POLLOUT & events:
            flags |= EPOLLOUT
        if fd in self:
            self.poller.modify(fd, flags)
        else:
            self.poller.register(fd, flags)
        super(Poller, self).__setitem__(fd, events)
    
    def __delitem__(self, fd):
        super(Poller, self).__delitem__(fd)
        self.poller.unregister(fd)

    def poll(self, timeout=0.0):
        events = self.poller.poll(timeout)
        
        for fd, flags in events:
            if not (flags & (EPOLLIN | EPOLLPRI | EPOLLOUT | EPOLLHUP)):
                yield (fd, POLLEX,)
            else:
                if flags & (EPOLLIN | EPOLLPRI):
                    yield (fd, POLLIN,)
                if flags & EPOLLOUT:
                    yield (fd, POLLOUT,)
                if flags & EPOLLHUP:
                    yield (fd, POLLHUP,)

##############################################################################
##############################################################################
