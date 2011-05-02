
import operator

from pypetri import trellis

import pypetri.net

import pynet.io.poll

#############################################################################
#############################################################################

class Flags(pypetri.net.Condition):
    
    def __init__(self, marking=None, *args, **kwargs):
        if marking is None:
            marking = trellis.Dict()
        else:
            marking = trellis.Dict(marking)
        super(Flags, self).__init__(*args, marking=marking, **kwargs)
        
    @trellis.modifier
    def send(self, marking=None):
        if marking is not None:
            for fd, events in marking.iteritems():
                if fd in self.marking:
                    self.marking[fd] |= events
                else:
                    self.marking[fd] = events
        return marking
    
    @trellis.modifier
    def pop(self, marking=None):
        if marking is not None:
            for fd, events in marking.iteritems():
                if fd in self.marking:
                    events = self.marking[fd] & ~(events)
                    if events:
                        self.marking[fd] = events
                    else:
                        del self.marking[fd]
        return marking

    def next(self):
        marking = self.marking
        if marking:
            yield self.Event(operator.getitem, marking,)

#############################################################################
#############################################################################

class Poller(Flags):
    
    POLLER = 'poller'
    REGISTRY = 'marking'
    
    poller = trellis.attr(None)
    
    def __init__(self, poller=None, *args, **kwargs):
        if poller is None:
            poller = pynet.io.poll.Poller()
        super(Poller, self).__init__(*args, poller=poller, **kwargs)
    
    @trellis.maintain
    def poller_context(self):
        previous = self.poller_context
        updated = self.poller
        if updated is not previous:
            if previous is not None:
                previous.__exit__()
            if updated is not None:
                updated.__enter__()
        return updated

    @trellis.maintain
    def registry(self):
        registry = self.marking
        poller = self.poller_context
        if None not in (poller, registry,):
            for fd in registry.deleted:
                if fd in poller:
                    del poller[fd]
            for changes in registry.added, registry.changed,:
                for fd in changes:
                    poller[fd] = changes[fd]
            for fd in registry:
                if fd in registry.deleted or fd in registry.added or fd in registry.changed:
                    continue
                if fd not in poller:
                    poller[fd] = registry[fd]
        return registry

    def next(self):
        marking = self.marking
        poller = self.poller
        if marking and poller:
            yield self.Event(poller.poll,)
            
#############################################################################
#############################################################################

class Poll(pypetri.net.Transition):

    @trellis.modifier
    def send(self, thunks, outputs=None):
        if outputs is None:
            outputs = self.outputs
        events = {}
        for thunk in thunks:
            for fd, event in thunk():
                if fd not in events:
                    events[fd] = event
                else:
                    events[fd] |= event
        for output in outputs:
            output.send(events)
        return events

#############################################################################
#############################################################################

class Polling(pypetri.net.Network):

    Condition = Flags

    def __new__(cls, *args, **kwargs):
        self = super(Polling, cls).__new__(cls, *args, **kwargs)
        self.input = Poller()
        self.output = Flags()
        self.poll = Poll()
        chain = (self.input, self.poll, self.output,)
        self.vertices.update(chain)
        for arc in self.link(chain):
            pass
        return self

    def next(self, vertices=None, *args, **kwargs):
        if vertices is None:
            vertices = self.poll,
        for event in super(Polling, self).next(vertices, *args, **kwargs):
            yield event
                
#############################################################################
#############################################################################

Network = Polling

#############################################################################
#############################################################################
