# @copyright
# @license

from ipolls import IPoller, EVENTS, POLLIN, POLLOUT, POLLEX, POLLHUP

from select import poll as epoll
from select import POLLIN as EPOLLIN
from select import POLLPRI as EPOLLPRI
from select import POLLOUT as EPOLLOUT
from select import POLLHUP as EPOLLHUP

##############################################################################
##############################################################################

class Poller(IPoller):
    
    poller = None
    
    def __init__(self):
        IPoller.__init__(self)
        self.poller = epoll()
    
    def __del__(self):
        self.clear()
        try:
            IPoller.__del__(self)
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
        IPoller.__setitem__(self, fd, events)
    
    def __delitem__(self, fd):
        IPoller.__delitem__(self, fd)
        self.poller.unregister(fd)

    def poll(self, timeout=0.0):
        
        if timeout:
            timeout *= 1000.0 # poll uses milliseconds
        
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
