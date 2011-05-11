# @copyright
# @license

from __future__ import absolute_import

from .ipoll import IPoller, EVENTS, POLLIN, POLLOUT, POLLEX, POLLHUP

import select as pyselect

##############################################################################
##############################################################################

class Poller(IPoller):
    
    readables = None
    writables = None
    exceptables = None
        
    def __init__(self):
        super(Poller, self).__init__()
        self.readables = set()
        self.writables = set()
        self.exceptables = set()

    def __setitem__(self, fd, events):
        if fd in self:
            old = self[fd]
            added = events & ~old
            removed = old & ~events
        else:
            added = events
            removed = 0
        for flag, group in ((POLLIN, self.readables), (POLLOUT, self.writables),):
            if flag & added:
                group.add(fd)
            elif flag & removed:
                group.remove(fd)
        if fd in self.readables or fd in self.writables:
            if fd not in self.exceptables:
                self.exceptables.add(fd)
        else:
            if fd in self.exceptables:
                self.exceptables.remove(fd)
        super(Poller, self).__setitem__(fd, events)
    
    def __delitem__(self, fd):
        if fd not in self:
            raise KeyError(fd)
        old = self[fd]
        if old:
            for flag, group in ((POLLIN, self.readables), (POLLOUT, self.writables),):
                if flag & old:
                    group.remove(fd)
            self.exceptables.remove(fd)
        super(Poller, self).__delitem__(fd)
    
    def poll(self, timeout=0.0):
        # must be sequences of integers or objects with fileno()
        rs = self.readables
        ws = self.writables
        xs = self.exceptables
    
        # acceptance of three empty sequences is platform-dependent
        if not (rs or ws or xs):
            return
        
        r, w, x = pyselect.select(rs, ws, xs, timeout)

        for event, fds in ((POLLIN, r), (POLLOUT, w), (POLLEX, x),):
            for fd in fds:
                yield (fd, event,)

#############################################################################
#############################################################################
