# @copyright
# @license

from ipoller import *

import select

##############################################################################
##############################################################################

class EPoller(IPoller):
    r"""
    Uses level-triggering
    """
    
    poller = None
    
    def __enter__(self):
        self.poller = select.epoll()
        return super(EPoller, self).__enter__()
        
    def __exit__(self, *args, **kwargs):
        ret = super(EPoller, self).__exit__(self, *args, **kwargs)
        self.poller.close()
        self.poller = None
        return ret
    
    def register(self, obj, events):
        fd = super(EPoller, self).register(obj, events)
        flags = 0
        if POLLIN & events:
            flags |= select.EPOLLIN | select.EPOLLPRI
        if POLLOUT & events:
            flags |= select.EPOLLOUT
        if flags:
            self.poller.register(fd, flags)
        return fd
    
    def modify(self, obj, events):
        fd = super(EPoller, self).modify(obj, events)
        flags = 0
        if POLLIN & events:
            flags |= select.EPOLLIN | select.EPOLLPRI
        if POLLOUT & events:
            flags |= select.EPOLLOUT
        if flags:
            try:
                self.poller.modify(fd, flags)
            except IOError:
                self.poller.register(fd, flags)
        return fd
    
    def unregister(self, obj):
        fd = super(EPoller, self).unregister(obj)
        self.poller.unregister(fd)
        return fd

    def poll(self, timeout=0.0):
        events = self.poll.poll(timeout)
        
        for fd, flags in events:
            obj = self.registry[fd]
            if not (flags & (select.EPOLLIN | select.EPOLLPRI | select.EPOLLOUT | select.EPOLLHUP)):
                yield (obj, POLLEX,)
            else:
                if flags & (select.EPOLLIN | select.EPOLLPRI):
                    yield (obj, POLLIN,)
                if flags & select.EPOLLOUT:
                    yield (obj, POLLOUT,)
                if flags & select.EPOLLHUP:
                    yield (obj, POLLHUP,)

##############################################################################
##############################################################################
