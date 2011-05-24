# @copyright
# @license

from __future__ import absolute_import

import itertools

from peak.events import trellis

from pypetri import net
from pypetri.collections import pool, operators

from ..io import socket
from . import polls

#############################################################################
#############################################################################

class FilteredPool(pool.Pool):
    
    filter = trellis.attr(None)
    
    # filter input
    def send(self, *args):
        filter = self.filter
        q = list(args)
        while q:
            item = q.pop(0)
            if filter(item):
                self.add(item)
            elif isinstance(item, (tuple, list)):
                q.extend(item)

#############################################################################
#############################################################################

class SocketPolling(polls.Network):
    
    input = trellis.make(lambda self: self.Condition())
    output = trellis.make(lambda self: self.Condition())
    
    def __init__(self, *args, **kwargs):
        super(SocketPolling, self).__init__(*args, **kwargs)
        for pair in ((self.input, self.poll), (self.poll, self.output,)):
            arc = self.Arc()
            net.link(arc, *pair)

#############################################################################
#############################################################################

class ItemTransition(net.Transition):

    select = trellis.attr(None)
    apply = trellis.attr(None)

    def __init__(self, *args, **kwargs):
        k = 'pipe'
        if k not in kwargs:
            pipe = operators.Pipeline(operators.Iter(),
                                      operators.Call(),
                                      operators.Iter(),
                                      operators.Apply(fn=self.apply),)
            kwargs[k] = pipe
        super(ItemTransition, self).__init__(*args, **kwargs)
    
    def next(self, *args, **kwargs):
        for event in super(ItemTransition, self).next(*args, select=self.select, **kwargs):
            yield event
        
#############################################################################
#############################################################################

class Register(ItemTransition):
    
    @staticmethod
    def events(sock):
        events = 0
        for state in sock.state, sock.next:
            if state in (sock.CLOSED, sock.ERROR,):
                break
        else:
            if sock.LISTENING in (sock.state, sock.next,):
                events = polls.POLLIN
            elif not (sock.state == sock.START and sock.next is None):
                events = polls.POLLIN | polls.POLLOUT
        return events
    
    @staticmethod
    def select(marking):
        active = []
        for sock in marking:
            events = Register.events(sock)
            if events:
                active.append(sock)
        if active:
            yield active
    
    @staticmethod
    def apply(input):
        events = Register.events(input)
        return (input, events)

#############################################################################
#############################################################################

class Accept(ItemTransition):
    
    @staticmethod
    def select(marking):
        islistening = lambda (x,y): ((x.state == x.START and x.next == x.LISTENING) \
                                  or (x.state == x.LISTENING and x.next not in (x.CLOSED, x.ERROR,))) \
                                 and (y & polls.POLLIN)
        acceptable = [x[0] for x in itertools.ifilter(islistening, marking.iteritems())]
        if acceptable:
            yield acceptable
    
    @staticmethod
    def apply(input):
        try:
            accepted = input.accept()
        except IOError:
            return input
        else:
            return accepted, input

#############################################################################
#############################################################################

class Shutdown(ItemTransition):
    
    @staticmethod
    def select(marking):
        isstream = lambda x: x.transport == socket.STREAM
        isopen = lambda x: (x.state in (x.START, x.CONNECTING, x.CONNECTED,)) \
                            and (x.next not in (x.CLOSED, x.CLOSING, x.ERROR,))
        filtered = itertools.ifilter(isopen, itertools.ifilter(isstream, marking))
        active = [x for x in filtered]
        if active:
            yield active
         
    @staticmethod   
    def apply(sock, *args, **kwargs):
        try:
            sock.shutdown(*args, **kwargs)
        except IOError: # TODO
            pass
        return sock

#############################################################################
#############################################################################

class Close(ItemTransition):
    
    @staticmethod
    def select(marking):
        isopen = lambda x: x.CLOSED not in (x.state, x.next,)
        active = [x for x in itertools.ifilter(isopen, marking)]
        if active:
            yield active
         
    @staticmethod   
    def apply(sock):
        try:
            sock.close()
        except IOError: # TODO
            pass
        return sock

#############################################################################
#############################################################################

class SocketIO(net.Network):
    
    def Transition(self, transition):
        if transition not in self.transitions:
            self.transitions.add(transition)
        return transition

    @trellis.modifier
    def Socket(self, *args, **kwargs):
        sock = socket.Socket.new(*args, **kwargs)
        self.sockets.add(sock)
        return sock
    
    @trellis.modifier
    def Sockets(self):
        condition = FilteredPool(filter=lambda x: isinstance(x, socket.Socket))
        self.conditions.add(condition)
        return condition
    
    poll = trellis.make(SocketPolling)
    sockets = trellis.make(Sockets)
    
    # FIXME: DRY
    @trellis.maintain(make=Register)
    def register(self):
        return self.Transition(self.register)
    
    @trellis.maintain(make=Accept)
    def accept(self):
        return self.Transition(self.accept)
    
    @trellis.maintain(make=Shutdown)
    def shutdown(self):
        return self.Transition(self.shutdown)
    
    @trellis.maintain(make=Close)
    def close(self):
        return self.Transition(self.close)
    
    def __init__(self, *args, **kwargs):
        super(SocketIO, self).__init__(*args, **kwargs)
        
        #
        # links
        #
        
        transition = self.register
        for pair in ((self.poll.output, transition,),
                     (self.sockets, transition,), 
                     (transition, self.poll.input,),):
            arc = self.Arc()
            net.link(arc, *pair)

        transition = self.accept
        for pair in ((self.poll.output, transition,),
                     (transition, self.sockets,),):
            arc = self.Arc()
            net.link(arc, *pair)
        
        for transition in (self.close, self.shutdown,):
            outputs = (self.sockets,)
            inputs = (self.sockets, self.poll.input, self.poll.output,)
            for input in inputs:
                arc = self.Arc()
                net.link(arc, input, transition)
            for output in outputs:
                arc = self.Arc()
                net.link(arc, transition, output)

#############################################################################
#############################################################################

Network = SocketIO

#############################################################################
#############################################################################

