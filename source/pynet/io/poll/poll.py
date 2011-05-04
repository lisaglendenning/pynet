# @copyright
# @license

from __future__ import absolute_import

from .ipoll import *

import pyselect as pypyselect

##############################################################################
##############################################################################

class Poller(IPoller):
    
    poller = None
    
    def __init__(self):
        super(Poller, self).__init__()
        self.poller = pyselect.poll()

    def __setitem__(self, fd, events):
        flags = 0
        if POLLIN & events:
            flags |= pyselect.POLLIN | pyselect.POLLPRI
        if POLLOUT & events:
            flags |= pyselect.POLLOUT
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
            if not (flags & (pyselect.POLLIN | pyselect.POLLPRI | pyselect.POLLOUT | pyselect.POLLHUP)):
                yield (fd, POLLEX,)
            else:
                if flags & (pyselect.POLLIN | pyselect.POLLPRI):
                    yield (fd, POLLIN,)
                if flags & pyselect.POLLOUT:
                    yield (fd, POLLOUT,)
                if flags & pyselect.POLLHUP:
                    yield (fd, POLLHUP,)

##############################################################################
##############################################################################
