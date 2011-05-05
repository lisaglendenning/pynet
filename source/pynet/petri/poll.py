
from __future__ import absolute_import

import collections

from peak.events import trellis
from peak.events import collections as pcollections

import pypetri.net

from .. import mapping

from ..io.poll import *

#############################################################################
#############################################################################

#class Flags(pypetri.net.Condition, collections.MutableMapping,):
#
#    # FIXME: do programmatically
#    ADDED = mapping.Mapping.ADDED
#    CHANGED = mapping.Mapping.CHANGED
#    REMOVED = mapping.Mapping.REMOVED
#    CHANGES = mapping.Mapping.CHANGES
#    
#    marking = trellis.make(mapping.Mapping)
#
#    def __init__(self, marking=None, *args, **kwargs):
#        pypetri.net.Condition.__init__(self, *args, **kwargs)
#        if marking:
#            self.marking.update(marking)
#    
#    @trellis.compute
#    def __hash__(self):
#        return self.marking.__hash__
#    
#    def __eq__(self, other):
#        if not isinstance(other, self.__class__):
#            return False
#        return self.marking == other.marking
#    
#    @trellis.compute
#    def __len__(self,):
#        return self.marking.__len__
#
#    @trellis.compute
#    def __iter__(self,):
#        return self.marking.__iter__
#    
#    @trellis.compute
#    def __getitem__(self,):
#        return self.marking.__getitem__
#
#    @trellis.compute
#    def __delitem__(self,):
#        return self.marking.__delitem__
#
#    @trellis.compute
#    def __setitem__(self,):
#        return self.marking.__setitem__
#        
#    @trellis.compute
#    def changes(self):
#        return self.marking.changes
#
#    def unset(self, k, flags=None):
#        if k in self:
#            current = self[k]
#            if flags is None:
#                flags = current
#                result = 0
#            elif flags:
#                result = current & ~(flags)
#            if result:
#                self[k] = result
#            else:
#                del self[k]
#        return flags
#
#    def set(self, k, flags=0):
#        if k in self and flags:
#            flags = self[k] | flags
#        self[k] = flags
#        return flags
#
#    def isset(self, k, flags=0):
#        if flags and k in self:
#            return self[k] & flags
#        return False
#            
#    @trellis.modifier
#    def send(self, marking=None):
#        if marking:
#            for k, flags in marking.iteritems():
#                self.set(k, flags)
#        return marking
#    
#    @trellis.modifier
#    def pull(self, marking=None):
#        if marking:
#            for k, flags in marking.iteritems():
#                self.unset(k, flags)
#        return marking
#
#    def next(self):
#        marking = self.marking
#        if marking:
#            yield self.Event(self.pull, marking,)
#        
##############################################################################
##############################################################################
#
#class Polls(pypetri.net.Transition):
#
#    poller = trellis.make(None)
#    polled = trellis.make(mapping.Mapping)
#    
#    def __init__(self, poller=None, *args, **kwargs):
#        if poller is None:
#            poller = Poller()
#        super(Polls, self).__init__(*args, poller=poller, **kwargs)
#        
#    @trellis.modifier
#    def send(self, thunks, outputs=None):
#        if outputs is None:
#            outputs = self.outputs
#        events = {}
#        for thunk in thunks:
#            for fd, event in thunk():
#                if fd not in events:
#                    events[fd] = event
#                else:
#                    events[fd] |= event
#        for output in outputs:
#            output.send(events)
#        return events
#    
#    def next(self):
#        if self.poll is not None:
#            yield self.Event(self.send, (self.poll,),)
#            
#    @trellis.compute(initially=None)
#    def poll(self):
#        registry = self.registry
#        if registry:
#            poller = self.poller
#            return self.Event(poller.poll)
#        else:
#            return None
#    
#    @trellis.maintain(initially=None) # TODO: this will break if the inputs are changed
#    def registry(self): # combine incoming changes
#        registry = self.registry
#        if registry is None:
#            initial = dict()
#            for i in self.inputs:
#                input = i.input
#                if not isinstance(input, Flags):
#                    continue
#                initial.update(input.marking)
#            registry = trellis.Dict(initial)
#        for i in self.inputs:
#            input = i.input
#            if not isinstance(input, Flags):
#                continue
#            values = input.marking.values
#            if values.added:
#                registry.update(values.added)
#            if values.changed:
#                registry.update(values.changed)
#            if values.deleted:
#                for k in values.deleted:
#                    del registry[k]
#        return registry
#    
#    @trellis.perform
#    def update(self): # reads self.registry and writes self.poller
#        registry = self.registry
#        if registry.added or registry.changed or registry.deleted:
#            poller = self.poller
#            for change, changes in zip((self.ADDED, self.CHANGED, self.REMOVED,), 
#                                       (registry.added, registry.changed, registry.deleted,),):
#                for k in changes:
#                    if change in (self.ADDED, self.CHANGED,):
#                        poller[k] = changes[k]
#                    else: # change == self.REMOVED
#                        del poller[k]
#                        
##############################################################################
##############################################################################
#
#class Polling(pypetri.net.Network):
#
#    Condition = Flags
#    
#    input = trellis.make(Flags)
#    output = trellis.make(Flags)
#    polls = trellis.make(Polls)
#    
#    @trellis.maintain(initially=None)
#    def incoming(self): # FIXME: DRY
#        incoming = self.incoming
#        input = self.input
#        output = self.s
#        for v in input, output,:
#            if v not in self.vertices:
#                self.vertices.add(v)
#        links = input.outputs & output.inputs
#        if links:
#            if incoming is not None and input not in links:
#                incoming = None
#            if incoming is None:
#                for link in links:
#                    if link.input is input and link.output is output:
#                        incoming = link
#                        break
#        if incoming is None:
#            incoming = self.link(input, output)
#        return incoming
#
#    @trellis.maintain(initially=None)
#    def outgoing(self): # FIXME: DRY
#        outgoing = self.outgoing
#        input = self.s
#        output = self.output
#        for v in input, output,:
#            if v not in self.vertices:
#                self.vertices.add(v)
#        links = input.outputs & output.inputs
#        if links:
#            if outgoing is not None and input not in links:
#                outgoing = None
#            if outgoing is None:
#                for link in links:
#                    if link.input is input and link.output is output:
#                        outgoing = link
#                        break
#        if outgoing is None:
#            outgoing = self.link(input, output)
#        return outgoing
#                
#    @trellis.compute
#    def poll(self):
#        return self.polls.poll
#       
              
#############################################################################
#############################################################################
#
#Network = Polling

class Polling(collections.MutableMapping, trellis.Component):

    ADDED = 'ADDED'
    CHANGED = 'CHANGED'
    REMOVED = 'REMOVED'
    CHANGES = [ADDED, CHANGED, REMOVED,]
    
    registry = trellis.make(mapping.Dispatch)
    registered = trellis.attr(resetting_to={})
    poller = trellis.make(Poller)
    events = trellis.make(mapping.Dispatch)
    
    @trellis.compute
    def __hash__(self):
        return self.poller.__hash__
    
    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.poller == other.poller
    
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
        poller = self.poller
        if k not in poller:
            raise KeyError(k)
        v = poller[k]
        del poller[k]
        trellis.on_undo(poller.__setitem__, k, v)
        event = (k, v, self.REMOVED,)
        for value in self.registry.put(event):
            if event not in self.registered:
                self.registered[event] = []
            self.registered[event].append(value)

    @trellis.modifier
    def __setitem__(self, k, v,):
        poller = self.poller
        if k in poller:
            undo = poller.__setitem__, k, poller[k]
            change = self.CHANGED
        else:
            undo = poller.__delitem__, k,
            change = self.ADDED
        poller[k] = v
        trellis.on_undo(*undo)
        event = (k, v, change,)
        for value in self.registry.put(event):
            if event not in self.registered:
                self.registered[event] = []
            self.registered[event].append(value)

    def unset(self, k, flags=None):
        if k in self:
            current = self[k]
            if flags is None:
                flags = current
                result = 0
            elif flags:
                result = current & ~(flags)
            if result:
                self[k] = result
            else:
                del self[k]
        return flags

    def set(self, k, flags=0):
        if k in self and flags:
            flags = self[k] | flags
        self[k] = flags
        return flags

    def isset(self, k, flags=0):
        if flags and k in self:
            return self[k] & flags
        return False

    def poll(self):
        poll = self.poller.poll
        events = self.events
        for fd, event in poll():
            for v in events.put((fd, event,)):
                yield v

#############################################################################
#############################################################################
