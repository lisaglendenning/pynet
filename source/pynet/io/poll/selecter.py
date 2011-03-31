# @copyright
# @license

from ipoller import *

import select

##############################################################################
##############################################################################

class Selecter(IPoller):
    
    readables = None
    writables = None
    exceptables = None
        
    def __enter__(self):
        self.readables = set()
        self.writables = set()
        self.exceptables = set()
        return super(Selecter, self).__enter__()

    def __exit__(self, *args, **kwargs):
        ret = super(Selecter, self).__exit__(self, *args, **kwargs)
        self.readables = None
        self.writables = None
        self.exceptables = None
        return ret

    def register(self, obj, events):
        fd = super(Selecter, self).register(obj, events)
        for flag, group in ((POLLIN, self.readables), (POLLOUT, self.writables),):
            if flag & events:
                group.add(fd)
        if fd in self.readables or fd in self.writables:
            self.exceptables.add(fd)
        return fd

    def modify(self, obj, events):
        fd = super(Selecter, self).modify(obj, events)
        for flag, group in ((POLLIN, self.readables), (POLLOUT, self.writables),):
            if flag & events:
                if fd not in group:
                    group.add(fd)
            else:
                if fd in group:
                    group.remove(fd)
        if fd in self.readables or fd in self.writables:
            if fd not in self.exceptables:
                self.exceptables.add(fd)
        else:
            if fd in self.exceptables:
                self.exceptables.remove(fd)
        return fd
    
    def unregister(self, obj):
        fd = super(Selecter, self).unregister(obj)
        for group in (self.readables, self.writables, self.exceptables,):
            if fd in group:
                group.remove(fd)
        return fd
    
    def poll(self, timeout=0.0):
        # must be sequences of integers or objects with fileno()
        rs = self.readables
        ws = self.writables
        xs = self.exceptables
        
        # acceptance of three empty sequences is platform-dependent
        if not (rs or ws or xs):
            return
        
        r, w, x = select.select(rs, ws, xs, timeout)

        for event, fds in ((POLLIN, r), (POLLOUT, w), (POLLEX, x),):
            for fd in fds:
                yield (self.registry[fd], event,)

#############################################################################
#############################################################################
