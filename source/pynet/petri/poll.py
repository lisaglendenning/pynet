
import collections

import pypetri.trellis as trellis

import pypetri.net

import pynet.io.poll

#############################################################################
#############################################################################

class NamesMarking(collections.MutableMapping, pypetri.net.Marking):

    def __init__(self, names=None, *args, **kwargs):
        super(NamesMarking, self).__init__(*args, **kwargs)
        self.names = trellis.Dict(names) if names else trellis.Dict()

    def __getitem__(self, name):
        return self.names[name]

    def __setitem__(self, name, value):
        self.names[name] = value
        
    def __delitem__(self, name):
        del self.names[name]
    
    def __len__(self):
        return len(self.names)
    
    def __iter__(self):
        for k in self.names:
            yield k
    
    def __add__(self, other):
        return self.update(other)
    
    def __radd__(self, other):
        if other:
            return other + self
        return self
    
    def __sub__(self, other):
        if other:
            for k in other:
                if k in self:
                    del self[k]
        return self

    def __rsub__(self, other):
        if other:
            return other - self
        return self
        
    def __nonzero__(self):
        return len(self) > 0

#############################################################################
#############################################################################

class NamesCondition(pypetri.net.Condition):
    
    Marking = NamesMarking
    
    def __init__(self, marking=None, *args, **kwargs):
        if marking is None:
            marking = self.Marking()
        super(NamesCondition, self).__init__(*args, marking=marking, **kwargs)
        
#############################################################################
#############################################################################

class PollInput(NamesCondition):
    
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
        names = self.marking.names
        k = self.POLLER
        if k in names.added:
            updated = names.added[k]
        elif k in names.changed:
            updated = names.changed[k]
        elif k not in names.deleted:
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
        names = self.marking.names
        k = self.REGISTRY
        if k not in names:
            return None
        registry = names[k]
        poller = self.poller
        if poller is not None:
            for fd in registry.deleted:
                del poller[fd]
            for changes in registry.added, registry.changed,:
                for fd in changes:
                    poller[fd] = changes[fd]
        return registry

    def __rshift__(self, other):
        return other

#############################################################################
#############################################################################

class PollOutput(NamesCondition):
        
    def __lshift__(self, other):
        for fd, events in other.marking.iteritems():
            if fd in self.marking:
                self.marking[fd] |= events
            else:
                self.marking[fd] = events
        return other
    
    def __rshift__(self, other):
        for fd, events in other.marking.iteritems():
            if fd in self.marking:
                events = self.marking[fd] & ~(events)
                if events:
                    self.marking[fd] = events
                else:
                    del self.marking[fd]
    
#############################################################################
#############################################################################

class PollTransition(pypetri.net.Transition):
    
    Marking = NamesMarking
    
    def enabled(self, event):
        poller = PollInput.POLLER
        for flow in event.flows:
            if poller not in flow.marking \
              or flow.marking[poller] is None:
                return False
        return True

    def __call__(self, event):
        outputs = self.Event(transition=self,)
        events = {}
        for flow in event.flows:
            poller = flow.marking[PollInput.POLLER]
            for fd, event in poller.poll():
                if fd not in events:
                    events[fd] = event
                else:
                    events[fd] |= event
        marking = self.Marking(names=events)
        outgoing = [o.output.output for o in self.outputs if o.connected]
        for arc in outgoing:
            output = self.Flow(arc=arc, marking=marking)
            outputs.add(output)
        return outputs

#############################################################################
#############################################################################

class PollChain(pypetri.net.Network):
    
    CONDITIONS = ('input', 'output',)
    TRANSITIONS = ('poll',)
    
    @classmethod
    def create(cls, *args, **kwargs):
        self = cls(*args, **kwargs)
        self.zip(self.CONDITIONS, self.TRANSITIONS)
        return self
    
    def __init__(self, *args, **kwargs):
        super(PollChain, self).__init__(*args, **kwargs)
        for name, type in zip(self.CONDITIONS, (PollInput, PollOutput,),):
            condition = type(name=name)
            self.add(condition)
        for name, type in zip(self.TRANSITIONS, (PollTransition,),):
            transition = type(name=name)
            self.add(transition)
    
    # any way to do this programmatically?
    input = property(lambda self: self[self.CONDITIONS[0]])
    output = property(lambda self: self[self.CONDITIONS[-1]])
    poll = property(lambda self: self[self.TRANSITIONS[0]])
    
#############################################################################
#############################################################################
