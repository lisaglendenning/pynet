
import operator

from pypetri import trellis

import pypetri.net

import pynet.io.poll

#############################################################################
#############################################################################

class Assignment(pypetri.net.Condition):
    
    def __init__(self, marking=None, *args, **kwargs):
        if marking is None:
            marking = trellis.Dict()
        else:
            marking = trellis.Dict(marking)
        super(Assignment, self).__init__(*args, marking=marking, **kwargs)
        
    @trellis.modifier
    def send(self, marking=None):
        if marking is not None:
            self.marking.update(marking)
        return marking

    @trellis.modifier
    def pop(self, marking=None):
        if marking is not None:
            for k in marking:
                if k in self.marking:
                    del self.marking[k]
        return marking

    def next(self):
        marking = self.marking
        if marking:
            yield self.Event(operator.getitem, marking,)

#############################################################################
#############################################################################

class PollInput(Assignment):
    
    POLLER = 'poller'
    REGISTRY = 'registry'
    
    def __init__(self, poller=None, *args, **kwargs):
        super(PollInput, self).__init__(*args, **kwargs)
        if poller is None:
            poller = pynet.io.poll.Poller()
        self.marking[self.POLLER] = poller
        self.marking[self.REGISTRY] = trellis.Dict()
    
    @trellis.maintain
    def poller(self):
        if self.marking is None:
            return None
        updated = None
        previous = self.poller
        marking = self.marking
        k = self.POLLER
        if k in marking.added:
            updated = marking.added[k]
        elif k in marking.changed:
            updated = marking.changed[k]
        elif k not in marking.deleted:
            updated = previous
        if updated is not previous:
            if previous is not None:
                previous.__exit__()
            if updated is not None:
                updated.__enter__()
        return updated

    @trellis.maintain
    def registry(self):
        if self.marking is None:
            return None
        marking = self.marking
        k = self.REGISTRY
        if k not in marking:
            return None
        registry = marking[k]
        poller = self.poller
        if poller is not None:
            for fd in registry.deleted:
                del poller[fd]
            for changes in registry.added, registry.changed,:
                for fd in changes:
                    poller[fd] = changes[fd]
        return registry

#############################################################################
#############################################################################

class PollOutput(Assignment):
        
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
            yield self.Event(self.pop,)

#############################################################################
#############################################################################

class PollTransition(pypetri.net.Transition):

    @trellis.modifier
    def send(self, thunks, outputs=None):
        if outputs is None:
            outputs = self.outputs
        events = {}
        for thunk in thunks:
            poller = thunk(PollInput.POLLER)
            for fd, event in poller.poll():
                if fd not in events:
                    events[fd] = event
                else:
                    events[fd] |= event
        for output in outputs:
            output.send(events)
        return events

#############################################################################
#############################################################################

class PollChain(pypetri.net.Network):

    def __new__(cls, *args, **kwargs):
        self = super(PollChain, cls).__new__(cls, *args, **kwargs)
        self.input = PollInput()
        self.output = PollOutput()
        self.poll = PollTransition()
        chain = (self.input, self.poll, self.output,)
        self.vertices.update(chain)
        for arc in self.link(chain):
            pass
        return self

    def next(self, vertices=None, *args, **kwargs):
        if vertices is None:
            vertices = self.poll,
        for event in super(PollChain, self).next(vertices, *args, **kwargs):
            yield event
                
#############################################################################
#############################################################################

Network = PollChain

#############################################################################
#############################################################################
