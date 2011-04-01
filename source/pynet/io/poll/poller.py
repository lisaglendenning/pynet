# @copyright
# @license

from ipoller import *

import select

##############################################################################
##############################################################################

class Poller(IPoller):
    
    poller = None
    
    def __enter__(self):
        self.poller = select.poll()
        return super(Poller, self).__enter__()

    def __exit__(self, *args, **kwargs):
        ret = super(Poller, self).__exit__(self, *args, **kwargs)
        self.poller = None
        return ret
    
    def register(self, obj, events):
        fd = super(Poller, self).register(obj, events)
        flags = 0
        if POLLIN & events:
            flags |= select.POLLIN | select.POLLPRI
        if POLLOUT & events:
            flags |= select.POLLOUT
        if flags:
            self.poller.register(fd, flags)
        return fd
    
    def modify(self, obj, events):
        fd = super(Poller, self).modify(obj, events)
        flags = 0
        if POLLIN & events:
            flags |= select.POLLIN | select.POLLPRI
        if POLLOUT & events:
            flags |= select.POLLOUT
        if flags:
            try:
                self.poller.modify(fd, flags)
            except IOError:
                self.poller.register(fd, flags)
        return fd
    
    def unregister(self, obj):
        fd = super(Poller, self).unregister(obj)
        self.poller.unregister(fd)
        return fd

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
