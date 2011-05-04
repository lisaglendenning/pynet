
from __future__ import absolute_import

import collections
import operator

from pypetri import trellis
import peak.events.collections

import pypetri.net

from .. import mapping

from ..io import poll

#############################################################################
#############################################################################

class Flags(pypetri.net.Condition, collections.MutableMapping,):

    # FIXME: do programmatically
    ADDED = mapping.Mapping.ADDED
    CHANGED = mapping.Mapping.CHANGED
    REMOVED = mapping.Mapping.REMOVED
    CHANGES = mapping.Mapping.CHANGES

    def __init__(self, marking=None, *args, **kwargs):
        if marking:
            marking = mapping.Mapping(marking)
        else:
            marking = mapping.Mapping()
        pypetri.net.Condition.__init__(self, *args, marking=marking, **kwargs)
    
    @trellis.maintain
    def __hash__(self):
        return self.marking.__hash__
    
    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.marking == other.marking
    
    @trellis.maintain
    def __len__(self,):
        return self.marking.__len__

    @trellis.maintain
    def __iter__(self,):
        return self.marking.__iter__
    
    @trellis.maintain
    def __getitem__(self,):
        return self.marking.__getitem__

    @trellis.maintain
    def __delitem__(self,):
        return self.marking.__delitem__

    @trellis.maintain
    def __setitem__(self,):
        return self.marking.__setitem__
        
    @trellis.maintain(initially=None)
    def changes(self):
        return self.marking.changes
    
    @trellis.modifier
    def unset(self, k, flags=None):
        if k in self:
            current = self[k]
            if flags is None:
                result = 0
            elif flags:
                result = current & ~(flags)
            if result:
                self[k] = result
            else:
                del self[k]

    @trellis.modifier
    def set(self, k, flags=0):
        if k in self and flags:
            self[k] = self[k] | flags
        else:
            self[k] = flags

    def isset(self, k, flags=0):
        if flags and k in self:
            return self[k] & flags
        return False
            
    @trellis.modifier
    def send(self, marking=None):
        if marking is not None:
            for k, flags in marking.iteritems():
                self.set(k, flags)
        return marking
    
    @trellis.modifier
    def pop(self, marking=None):
        if marking is not None:
            for k, flags in marking.iteritems():
                self.unset(k, flags)
        return marking

    def next(self):
        marking = self.marking
        if marking:
            yield self.Event(operator.getitem, marking,)

#############################################################################
#############################################################################

class Poller(Flags):

    poller = trellis.make(None)
    
    def __init__(self, poller=None, *args, **kwargs):
        if poller is None:
            poller = poll.Poller()
        super(Poller, self).__init__(*args, poller=poller, **kwargs)

    @trellis.maintain
    def registry(self):
        poller = self.poller
        values = self.marking.values
        if values.added or values.changed or values.deleted:
            for change, changes in zip((self.ADDED, self.CHANGED, self.REMOVED,), 
                                       (values.added, values.changed, values.deleted,),):
                for k in changes:
                    undo = None
                    if change in (self.ADDED, self.CHANGED,):
                        if k in poller:
                            undo = (poller.__setitem__, k, poller[k],)
                        else:
                            undo = (poller.__delitem__, k,)
                        poller[k] = changes[k]
                    else: # change == self.REMOVED:
                        if k in poller:
                            undo = (poller.__setitem__, k, poller[k],)
                        del poller[k]
                    if undo:
                        trellis.on_undo(*undo)
            trellis.mark_dirty()
        return self.poller

    def next(self):
        if self.poll is not None:
            yield self.poll
            
    @trellis.maintain
    def poll(self):
        poller = self.registry
        if poller:
            return self.Event(poller.poll)
        return None
        
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
