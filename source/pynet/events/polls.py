
from __future__ import absolute_import

import collections

from peak.events import trellis

from pypetri import net

from ..io.poll import *

#############################################################################
#############################################################################

class Registry(collections.MutableMapping, net.Condition):

    marking = trellis.make(trellis.Dict)

    def __hash__(self):
        return object.__hash__(self)
    
    def __eq__(self, other):
        return self is other
    
    def __nonzero__(self):
        return len(self) > 0
    
    @trellis.compute
    def __len__(self,):
        return self.marking.__len__

    @trellis.compute
    def __iter__(self,):
        return self.marking.__iter__
    
    @trellis.compute
    def __getitem__(self,):
        return self.marking.__getitem__

    @trellis.compute
    def __delitem__(self,):
        return self.marking.__delitem__

    @trellis.compute
    def __setitem__(self,):
        return self.marking.__setitem__
        
    @trellis.modifier
    def send(self, *args):
        itr = iter(args)
        marking = self.marking
        for item in itr:
            fd, event = item
            if fd in marking:
                marking[fd] |= event
            else:
                marking[fd] = event
    
    @trellis.modifier
    def pull(self, args):
        marking = self.marking
        if args is marking:
            args = marking.copy()
            marking.clear()
        elif args == marking:
            marking.clear()
        else:
            try:
                itr = args.iteritems()
            except AttributeError:
                try:
                    itr = iter(args)
                except AttributeError:
                    raise TypeError(args)
            for k,v in itr:
                if k in marking:
                    old = marking[k]
                    if v == old:
                        del marking[k]
                    else:
                        marking[k] = old & ~v
        return args
    
    def next(self):
        if self.marking:
            yield self.Event(self.pull, self.marking)

#############################################################################
#############################################################################

class Poll(collections.MutableMapping, net.Transition):

    poller = trellis.make(Poller)
    
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
        registry = self.poller
        if k not in registry:
            raise KeyError(k)
        v = registry[k]
        del registry[k]
        trellis.on_undo(registry.__setitem__, k, v,)

    @trellis.modifier
    def __setitem__(self, k, v,):
        registry = self.poller
        if k in registry:
            v = registry[k]
            undo = registry.__setitem__, k, v,
        else:
            undo = registry.__delitem__, k,
        registry[k] = v
        trellis.on_undo(*undo)

    @trellis.modifier
    def send(self, thunks, outputs=None):
        # update registry
        removed = set(self.keys())
        for thunk in thunks:
            registry = thunk()
            for k,v in registry.iteritems():
                if k in self:
                    removed.remove(k)
                    self[k] |= v
                else:
                    self[k] = v
        for k in removed:
            del self[k]
            
        # dispatch events
        poll = self.poller.poll
        if outputs is None:
            outputs = self.outputs
        for fd, event in poll():
            for output in outputs:
                output.send((fd, event,))

#############################################################################
#############################################################################


class Polling(net.Network):
    
    Transition = Poll
    Condition = Registry
    
    poll = trellis.make(Poll)
    
    @trellis.compute
    def __call__(self,):
        return self.poll.__call__

#############################################################################
#############################################################################
