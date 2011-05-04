
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
    
    marking = trellis.make(mapping.Mapping)

    def __init__(self, marking=None, *args, **kwargs):
        pypetri.net.Condition.__init__(self, *args, **kwargs)
        if marking:
            self.marking.update(marking)
    
    @trellis.compute
    def __hash__(self):
        return self.marking.__hash__
    
    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.marking == other.marking
    
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
        
    @trellis.compute
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
        if marking:
            for k, flags in marking.iteritems():
                self.set(k, flags)
        return marking
    
    @trellis.modifier
    def pop(self, marking=None):
        if marking:
            for k, flags in marking.iteritems():
                self.unset(k, flags)
        return marking

    def next(self):
        marking = self.marking
        if marking:
            yield self.Event(self.pop, marking,)

#############################################################################
#############################################################################

class Poller(Flags):

    poller = trellis.make(None)
    
    def __init__(self, poller=None, *args, **kwargs):
        if poller is None:
            poller = poll.Poller()
        super(Poller, self).__init__(*args, poller=poller, **kwargs)
    
    @trellis.compute
    def __getitem__(self): # value read may be inconsistent during a rule
        return self.poller.__getitem__
    
    @trellis.perform
    def update(self): # reads self.marking and writes self.poller
        values = self.marking.values
        if values.added or values.changed or values.deleted:
            poller = self.poller
            for change, changes in zip((self.ADDED, self.CHANGED, self.REMOVED,), 
                                       (values.added, values.changed, values.deleted,),):
                for k in changes:
                    if change in (self.ADDED, self.CHANGED,):
                        poller[k] = changes[k]
                    else: # change == self.REMOVED
                        del poller[k]

    def next(self):
        if self.poll is not None:
            yield self.poll
            
    @trellis.compute
    def poll(self):
        if len(self) > 0:
            return self.Event(self.poller.poll)
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
    
    @trellis.compute
    def poll(self):
        polls = []
        for i in self.inputs:
            if i.input is None:
                continue
            if i.input.poll is not None:
                polls.append(i.input.poll)
        if polls:
            return self.Event(self.send, polls)
        else:
            return None
    
#############################################################################
#############################################################################

class Polling(pypetri.net.Network):

    Condition = Flags
    
    input = trellis.make(Poller)
    output = trellis.make(Flags)
    polling = trellis.make(Poll)
    
    @trellis.maintain(initially=None)
    def incoming(self): # FIXME: DRY
        incoming = self.incoming
        input = self.input
        output = self.polling
        for v in input, output,:
            if v not in self.vertices:
                self.vertices.add(v)
        links = input.outputs & output.inputs
        if links:
            if incoming is not None and input not in links:
                incoming = None
            if incoming is None:
                for link in links:
                    if link.input is input and link.output is output:
                        incoming = link
                        break
        if incoming is None:
            incoming = self.link(input, output)
        return incoming

    @trellis.maintain(initially=None)
    def outgoing(self): # FIXME: DRY
        outgoing = self.outgoing
        input = self.polling
        output = self.output
        for v in input, output,:
            if v not in self.vertices:
                self.vertices.add(v)
        links = input.outputs & output.inputs
        if links:
            if outgoing is not None and input not in links:
                outgoing = None
            if outgoing is None:
                for link in links:
                    if link.input is input and link.output is output:
                        outgoing = link
                        break
        if outgoing is None:
            outgoing = self.link(input, output)
        return outgoing
                
    @trellis.compute
    def poll(self):
        return self.polling.poll
        
                
#############################################################################
#############################################################################

Network = Polling

#############################################################################
#############################################################################
