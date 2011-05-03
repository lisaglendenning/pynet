
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
    
    input = trellis.attr(None)
    output = trellis.attr(None)
    polling = trellis.attr(None)
    
    def __init__(self, input=None, output=None, polling=None, *args, **kwargs):
        if input is None:
            input = Poller()
        if output is None:
            output = Flags()
        if polling is None:
            polling = Poll()
        super(Polling, self).__init__(*args, input=input, output=output, polling=polling, **kwargs)

    @trellis.maintain(initially=None)
    def input_changed(self): # FIXME: DRY
        previous = self.input_changed
        updated = self.input
        if previous is not updated and previous is not None:
            if previous in self.vertices:
                self.vertices.remove(previous)
            previous.inputs.clear()
            previous.outputs.clear()
        if updated is not None:
            if updated not in self.vertices:
                self.vertices.add(updated)
        return updated
    
    @trellis.maintain(initially=None)
    def output_changed(self): # FIXME: DRY
        previous = self.output_changed
        updated = self.output
        if previous is not updated and previous is not None:
            if previous in self.vertices:
                self.vertices.remove(previous)
            previous.inputs.clear()
            previous.outputs.clear()
        if updated is not None:
            if updated not in self.vertices:
                self.vertices.add(updated)
        return updated
                
    @trellis.maintain(initially=None)
    def polling_changed(self): # FIXME: DRY
        previous = self.polling_changed
        updated = self.polling
        if previous is not updated and previous is not None:
            if previous in self.vertices:
                self.vertices.remove(previous)
            previous.inputs.clear()
            previous.outputs.clear()
        if updated is not None:
            if updated not in self.vertices:
                self.vertices.add(updated)
        return updated
    
    
    @trellis.maintain(initially=None)
    def connect(self): # FIXME: DRY
        input = self.input_changed
        polling = self.polling_changed
        output = self.output_changed
        if polling is not None:
            if input is not None:
                for i in polling.inputs:
                    if i.input is input:
                        break
                else:
                    for i in polling.inputs:
                        if i.input is None:
                            input.outputs.add(i)
                    else:
                        self.link(input, polling)
            if output is not None:
                for o in polling.outputs:
                    if o.output is output:
                        break
                else:
                    for o in polling.outputs:
                        if o.output is None:
                            output.inputs.add(o)
                    else:
                        self.link(polling, output)
        return polling
                
    @trellis.maintain(initially=None)
    def poll(self):
        polling = self.connect
        input = self.input_changed
        output = self.output_changed
        if None in (polling, input, output):
            return None
        events = [e for e in polling.next(inputs=(input,))]
        if not events:
            return None
        assert len(events) == 1
        return events[0]
        
                
#############################################################################
#############################################################################

Network = Polling

#############################################################################
#############################################################################
