# @copyright
# @license

from ipoller import *

import select

##############################################################################
##############################################################################

class Poller(IPoller):
    
    poller = None
    
    def __init__(self):
        super(Poller, self).__init__()
        self.poller = select.poll()

    def __setitem__(self, fd, events):
        flags = 0
        if POLLIN & events:
            flags |= select.POLLIN | select.POLLPRI
        if POLLOUT & events:
            flags |= select.POLLOUT
        if fd in self:
            self.poller.modify(fd, flags)
        else:
            self.poller.register(fd, flags)
        super(Poller, self).__setitem__(fd, events)
    
    def __delitem__(self, fd):
        super(Poller, self).__delitem__(fd)
        self.poller.unregister(fd)

    def poll(self, timeout=0.0):
        
        if timeout:
            timeout *= 1000.0 # poll uses milliseconds
        
        events = self.poller.poll(timeout)
        
        for fd, flags in events:
            if not (flags & (select.POLLIN | select.POLLPRI | select.POLLOUT | select.POLLHUP)):
                yield (fd, POLLEX,)
            else:
                if flags & (select.POLLIN | select.POLLPRI):
                    yield (fd, POLLIN,)
                if flags & select.POLLOUT:
                    yield (fd, POLLOUT,)
                if flags & select.POLLHUP:
                    yield (fd, POLLHUP,)

##############################################################################
##############################################################################
