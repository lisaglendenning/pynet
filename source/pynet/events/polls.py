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
    def update(self, iterable):
        if isinstance(iterable, collections.Mapping):
            iterable = iterable.iteritems()
        for k,v in iterable:
            if k in self:
                self[k] |= v
            else:
                self[k] = v

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

class Polls(collections.MutableMapping, net.Pipe):
    
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
    def send(self, inputs, *args, **kwargs):
        # update registry
        removed = set(self.keys())
        for thunk in inputs:
            registry = thunk()
            for k,v in registry.iteritems():
                if k in self:
                    removed.remove(k)
                    self[k] |= v
                else:
                    self[k] = v
        for k in removed:
            del self[k]
        super(Polls, self).send(self.poller.poll(), *args, **kwargs)

#############################################################################
#############################################################################

class Polling(net.Network):

    @trellis.modifier
    def Condition(self, *args, **kwargs):
        condition = PollEvents(*args, **kwargs)
        self.conditions.add(condition)
        return condition
    
    poll = trellis.make(None)
    
    def __init__(self, *args, **kwargs):
        if 'poll' not in kwargs:
            pipe = Polls()
            poll = self.Transition(pipe=pipe)
            kwargs['poll'] = poll
        super(Polling, self).__init__(*args, **kwargs)
    
    @trellis.compute
    def __call__(self,):
        return self.poll.__call__

#############################################################################
#############################################################################

Network = Polling

#############################################################################
#############################################################################
