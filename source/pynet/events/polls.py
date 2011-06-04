# @copyright
# @license

from __future__ import absolute_import

import collections

from peak.events import trellis

from pypetri import net
from pypetri.collections import mapping

from ..io.poll import *

#############################################################################
#############################################################################

class PollEvents(mapping.Mapping):

    @trellis.modifier
    def update(self, arg):
        if isinstance(arg, tuple) and len(arg) == 2:
            for i in arg:
                if not isinstance(i, tuple):
                    arg = (arg,)
                    break
        if isinstance(arg, collections.Mapping):
            arg = arg.iteritems()
        marking = self.marking
        for k,v in arg:
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
            v = self[item]
            del self[item]
        return v
    
#############################################################################
#############################################################################

class Polls(net.Transition, collections.MutableMapping,):
    
    poller = trellis.make(Poller)
    
    def __init__(self, *args, **kwargs):
        k = 'pipe'
        if k not in kwargs:
            pipe = net.Pipeline(net.Apply(fn=self.poll),
                                      net.Iter(),)
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
            if isinstance(registry, collections.Mapping):
                items = registry.iteritems()
            elif isinstance(registry, tuple) and len(registry) == 2:
                items = (registry,)
            else:
                items = registry
            for k,v in items:
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
