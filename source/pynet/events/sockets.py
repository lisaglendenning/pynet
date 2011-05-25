# @copyright
# @license

from __future__ import absolute_import

import itertools
import collections

from peak.events import trellis

from pypetri import net
from pypetri.collections import pool, operators

from ..io import socket
from . import polls

#############################################################################
#############################################################################

def flatten(arg, filter=None, types=(list, tuple,)):
    if filter is None:
        filter = lambda x: not isinstance(x, types)
    if filter(arg):
        yield arg
        return
    iterable = iter(arg)
    while True:
        try:
            i = iterable.next()
        except StopIteration:
            return
        if filter(i):
            yield i
        elif isinstance(i, types):
            try:
                i = iter(i)
            except TypeError:
                pass
            else:
                iterable = itertools.chain(i, iterable)

#############################################################################
#############################################################################

class FilteredPool(pool.Pool):
    
    filter = trellis.attr(None)
    
    # flattens and filters input
    def update(self, arg, **kwargs):
        filter = self.filter
        for item in flatten(arg, filter, **kwargs):
            self.add(item)

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

class SelectTransition(net.Transition):
    
    @staticmethod
    def forall(type):
        def outer(f):
            def wrapper(input, *args, **kwargs):
                if isinstance(input, type):
                    output = f(input, *args, **kwargs)
                else:
                    output = [f(i, *args, **kwargs) for i in input]
                return output
            return wrapper
        return outer

    select = trellis.attr(None)
    apply = trellis.attr(None)

    def __init__(self, *args, **kwargs):
        k = 'pipe'
        if k not in kwargs:
            pipe = operators.Pipeline(operators.Iter(),
                                      operators.Call(),
                                      operators.Apply(fn=self.apply),)
            kwargs[k] = pipe
        super(SelectTransition, self).__init__(*args, **kwargs)
    
    def next(self, select=None, *args, **kwargs):
        if select is None:
            filtered = self.select
        else:
            def filtered(m):
                for x in self.select(m):
                    for y in select(x):
                        yield y
        for event in super(SelectTransition, self).next(*args, select=filtered, **kwargs):
            yield event
        
#############################################################################
#############################################################################

class Register(SelectTransition):
    
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
    @SelectTransition.forall(socket.Socket)
    def apply(input):
        events = Register.events(input)
        return (input, events)

#############################################################################
#############################################################################

class Accept(SelectTransition):
    
    @staticmethod
    def select(marking):
        islistening = lambda (x,y): ((x.state == x.START and x.next == x.LISTENING) \
                                  or (x.state == x.LISTENING and x.next not in (x.CLOSED, x.ERROR,))) \
                                 and (y & polls.POLLIN)
        acceptable = [x[0] for x in itertools.ifilter(islistening, marking.iteritems())]
        if acceptable:
            yield acceptable
    
    @staticmethod
    @SelectTransition.forall(socket.Socket)
    def apply(input):
        try:
            accepted = input.accept()
        except IOError:
            output = input
        else:
            output = (accepted, input,)
        return output

#############################################################################
#############################################################################

class Shutdown(SelectTransition):
    
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
    @SelectTransition.forall(socket.Socket)
    def apply(sock, *args, **kwargs):
        try:
            sock.shutdown(*args, **kwargs)
        except IOError: # TODO
            pass
        return sock

#############################################################################
#############################################################################

class Close(SelectTransition):
    
    @staticmethod
    def select(marking):
        isopen = lambda x: x.CLOSED not in (x.state, x.next,)
        active = [x for x in itertools.ifilter(isopen, marking)]
        if active:
            yield active
         
    @staticmethod
    @SelectTransition.forall(socket.Socket)
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

