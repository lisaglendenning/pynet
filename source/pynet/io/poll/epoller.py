# @copyright
# @license

from ipoller import *

import select

##############################################################################
##############################################################################

class Poller(IPoller):
    r"""
    Uses level-triggering
    """
    
    poller = None
    
    def __init__(self):
        super(Poller, self).__init__()
        self.poller = select.epoll()
        
    def __exit__(self, *args, **kwargs):
        ret = super(Poller, self).__exit__(self, *args, **kwargs)
        self.poller.close()
        return ret

    def __setitem__(self, fd, events):
        flags = 0
        if POLLIN & events:
            flags |= select.EPOLLIN | select.EPOLLPRI
        if POLLOUT & events:
            flags |= select.EPOLLOUT
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
            if not (flags & (select.EPOLLIN | select.EPOLLPRI | select.EPOLLOUT | select.EPOLLHUP)):
                yield (fd, POLLEX,)
            else:
                if flags & (select.EPOLLIN | select.EPOLLPRI):
                    yield (fd, POLLIN,)
                if flags & select.EPOLLOUT:
                    yield (fd, POLLOUT,)
                if flags & select.EPOLLHUP:
                    yield (fd, POLLHUP,)

##############################################################################
##############################################################################
