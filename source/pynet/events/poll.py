
from __future__ import absolute_import

import collections
import functools

from peak.events import trellis

from .dispatch import *

from ..io.poll import *

#############################################################################
#############################################################################

class Polling(collections.MutableMapping, trellis.Component):

    ADDED = 'ADDED'
    CHANGED = 'CHANGED'
    REMOVED = 'REMOVED'
    CHANGES = [ADDED, CHANGED, REMOVED,]
    
    registry = trellis.make(Dispatch)
    outputs = trellis.attr(resetting_to={})
    poller = trellis.make(Poller)
    events = trellis.make(Dispatch)
    
    def cache_output(self, k, fn, *args):
        output = [o for o in fn(*args)]
        outputs = self.outputs
        if k not in outputs:
            outputs[k] = output
        else:
            outputs[k].extend(output)
        return output
    
    @trellis.compute
    def __hash__(self):
        return self.poller.__hash__
    
    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.poller == other.poller
    
    @trellis.compute
    def __len__(self,):
        return self.poller.__len__

    @trellis.compute
    def __iter__(self,):
        return self.poller.__iter__
    
    @trellis.compute
    def __getitem__(self,):
        return self.poller.__getitem__

    @trellis.modifier
    def __delitem__(self, k,):
        poller = self.poller
        if k not in poller:
            raise KeyError(k)
        v = poller[k]
        del poller[k]
        trellis.on_undo(poller.__setitem__, k, v)
        event = (k, v, self.REMOVED,)
        self.cache_output(event, self.registry.forall, event)

    @trellis.modifier
    def __setitem__(self, k, v,):
        poller = self.poller
        if k in poller:
            undo = poller.__setitem__, k, poller[k]
            change = self.CHANGED
        else:
            undo = poller.__delitem__, k,
            change = self.ADDED
        poller[k] = v
        trellis.on_undo(*undo)
        event = (k, v, change,)
        self.cache_output(event, self.registry.forall, event)

    def unset(self, k, flags=None):
        if k in self:
            current = self[k]
            if flags is None:
                flags = current
                result = 0
            elif flags:
                result = current & ~(flags)
            if result:
                self[k] = result
            else:
                del self[k]
        return flags

    def set(self, k, flags=0):
        if k in self and flags:
            flags = self[k] | flags
        self[k] = flags
        return flags

    def isset(self, k, flags=0):
        if flags and k in self:
            return self[k] & flags
        return False

    def poll(self):
        poll = self.poller.poll
        events = self.events
        for fd, event in poll():
            for v in events.forall((fd, event,)):
                yield v

#############################################################################
#############################################################################
