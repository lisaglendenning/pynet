
from __future__ import absolute_import

import collections

from peak.events import trellis

from pypetri import net

from .match import *
from .dispatch import *
from ..io.poll import *

#############################################################################
#############################################################################

class Output(net.Arc):
    
    match = trellis.make(Match)

class Outputs(collections.MutableSet, trellis.Component):

    items = trellis.make(set)
    
    @trellis.compute
    def __iter__(self,):
        return self.items.__iter__
    
    @trellis.compute
    def __contains__(self,):
        return self.items.__contains__
    
    @trellis.compute
    def __len__(self,):
        return self.items.__contains__
    
    @trellis.modifier
    def add(self, item):
        items = self.items
        if item not in items:
            items.add(item)
            trellis.on_undo(items.remove, item)
            
    @trellis.modifier
    def discard(self, item):
        items = self.items
        if item in items:
            items.remove(item)
            trellis.on_undo(items.add, item)
    
    def __call__(self, *args, **kwargs):
        for output in self:
            output.send(*args, **kwargs)

class Polled(net.Condition):

    marking = trellis.make(trellis.Dict)
    
    @trellis.modifier
    def send(self, event):
        marking = self.marking
        fd, event = event
        if fd in marking:
            marking[fd] |= event
        else:
            marking[fd] = event
    
    @trellis.modifier
    def pull(self, marking=None):
        if marking is None:
            marking = self.marking
            marking.clear()
        else:
            pulled = self.marking
            for k in marking:
                if k in pulled:
                    v = marking[k]
                    old = pulled[k]
                    if v == old:
                        del pulled[k]
                    else:
                        pulled[k] = old & ~v
        return marking
    
    def next(self):
        if self.marking:
            yield self.Event(self.pull)

class Poll(collections.MutableMapping, net.Transition):

    poller = trellis.make(Poller)
    
    @trellis.maintain(make=Dispatch)
    def dispatch(self):
        dispatch = self.dispatch
        outputs = self.outputs
        for o in outputs.added:
            if o.match not in dispatch:
                dispatch[o.match] = Outputs(items=set([o]))
            else:
                dispatch[o.match].add(o)
        for o in outputs.removed:
            if o.match in dispatch:
                dispatch[o.match].remove(o)
                if not dispatch[o.match]:
                    del dispatch[o.match]
        return dispatch
    
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
    def __call__(self):
        for event in self.next():
            event()
            break

    @trellis.modifier
    def send(self, thunks):
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
        dispatch = self.dispatch
        for fd, event in poll():
            dispatch.send((fd, event,))

#############################################################################
#############################################################################


class Polling(net.Network):
    
    Transition = Poll
    Arc = Output
    Condition = Polled
    
    poll = trellis.make(Poll)

#############################################################################
#############################################################################
