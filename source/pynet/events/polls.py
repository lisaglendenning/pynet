# @copyright
# @license

from __future__ import absolute_import

import collections

from peak.events import trellis

from pypetri import net
from pypetri.collections import mapping, operators

from ..io.poll import *

#############################################################################
#############################################################################

class PollEvents(mapping.Mapping):

    @trellis.modifier
    def send(self, item=None, items=None, **kwargs):
        if item is not None:
            self.update((item,),)
        if items is not None:
            self.update(items)
    
    @trellis.modifier
    def update(self, iterable):
        if isinstance(iterable, collections.Mapping):
            iterable = iterable.iteritems()
        marking = self.marking
        for k,v in iterable:
            for m in marking.to_change, marking.to_add, marking:
                if k in m:
                    m[k] |= v
                    break
            else:
                marking[k] = v

    @trellis.modifier
    def pop(self, item,):
        if isinstance(item, tuple):
            k,v = item
            old = self[k]
            if v == old:
                del self[k]
            else:
                self[k] = old & ~v
        else:
            k = item
            del self[k]
        return item
    
#############################################################################
#############################################################################

class Polls(net.Transition, collections.MutableMapping,):
    
    poller = trellis.make(Poller)
    
    def __init__(self, *args, **kwargs):
        k = 'pipe'
        if k not in kwargs:
            pipe = operators.Pipeline(operators.Apply(fn=self.poll),
                                      operators.Iter(),)
            kwargs[k] = pipe
        super(Polls, self).__init__(*args, **kwargs)

    def __hash__(self):
        return object.__hash__(self)
    
    def __eq__(self, other):
        return self is other
    
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
    def poll(self, inputs, *args, **kwargs):
        # update registry
        removed = set(self.keys())
        for thunk in inputs:
            registry = thunk(*args, **kwargs)
            for k,v in registry.iteritems():
                if k in self:
                    removed.remove(k)
                    self[k] |= v
                else:
                    self[k] = v
        for k in removed:
            del self[k]
        return self.poller.poll()

#############################################################################
#############################################################################

class Polling(net.Network):

    @trellis.modifier
    def Condition(self, *args, **kwargs):
        condition = PollEvents(*args, **kwargs)
        self.conditions.add(condition)
        return condition
    
    @trellis.modifier
    def Transition(self, *args, **kwargs):
        transition = Polls(*args, **kwargs)
        self.transitions.add(transition)
        return transition
    
    poll = trellis.make(lambda self: self.Transition())

#############################################################################
#############################################################################

Network = Polling

#############################################################################
#############################################################################
