# @copyright
# @license

from __future__ import absolute_import

from peak.events import trellis

from pypetri import net
from pypetri.collections import pool, operators

from ..io import socket
from . import polls

#############################################################################
#############################################################################

class FilteredPool(pool.Pool):
    
    fn = trellis.attr(None)
    
    # filter out non-typed input
    def send(self, *args):
        filter = self.fn
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

class Register(net.Transition):
    
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
    def filter(inputs):
        outputs = []
        for input in inputs:
            active = []
            for sock in input.keywords['items']:
                events = Register.events(sock)
                if events:
                    active.append(sock)
            if active:
                outputs.append(input.__class__(input.func, items=active))
        if outputs:
            yield outputs
    
    @staticmethod
    def register(inputs):
        registry = {}
        for input in inputs:
            for sock in input():
                events = Register.events(sock)
                registry[sock] = events
        return registry
    
    def __init__(self, *args, **kwargs):
        k = 'pipe'
        if k not in kwargs:
            pipe = operators.Pipeline(operators.FilterIn(fn=self.filter),
                                      operators.Apply(fn=self.register),)
            kwargs[k] = pipe
        super(Register, self).__init__(*args, **kwargs)

#############################################################################
#############################################################################

class Accept(net.Transition):
    
    @staticmethod
    def filter(inputs):
        outputs = []
        for input in inputs:
            active = {}
            for sock, events in input.keywords['items'].iteritems():
                if sock.state == sock.LISTENING and events & polls.POLLIN:
                    active[sock] = events
            if active:
                outputs.append(input.__class__(input.func, items=active))
        if outputs:
            yield outputs
    
    @staticmethod
    def accept(input):
        try:
            accepted = input.accept()
        except Exception as e:
            accepted = e
        return accepted, input

    def __init__(self, *args, **kwargs):
        k = 'pipe'
        if k not in kwargs:
            pipe = operators.Pipeline(operators.FilterIn(fn=self.filter),
                                      operators.Iter(),
                                      operators.Call(),
                                      operators.Iter(),
                                      operators.Apply(fn=self.accept),)
            kwargs[k] = pipe
        super(Accept, self).__init__(*args, **kwargs)

#############################################################################
#############################################################################

class Close(net.Transition):
    
    @staticmethod
    def filter(inputs):
        outputs = []
        for input in inputs:
            active = []
            socks = input.keywords['items']
            for sock in socks:
                if sock.CLOSED in (sock.state, sock.next,):
                    continue
                active.append(sock)
            if active:
                outputs.append(input.__class__(input.func, items=active))
        if outputs:
            yield outputs
         
    @staticmethod   
    def close(sock):
        try:
            sock.close()
        except Exception: # TODO
            pass
        return sock

    def __init__(self, *args, **kwargs):
        k = 'pipe'
        if k not in kwargs:
            pipe = operators.Pipeline(operators.FilterIn(fn=self.filter),
                                      operators.Iter(),
                                      operators.Call(),
                                      operators.Iter(),
                                      operators.Apply(fn=self.close),)
            kwargs[k] = pipe
        super(Close, self).__init__(*args, **kwargs)

#############################################################################
#############################################################################

class SocketIO(net.Network):

    @trellis.modifier
    def Socket(self, *args, **kwargs):
        sock = socket.Socket.new(*args, **kwargs)
        self.sockets.add(sock)
        return sock
    
    poll = trellis.make(SocketPolling)
    sockets = trellis.make(lambda self: FilteredPool(fn=lambda x: isinstance(x, socket.Socket)))
    register = trellis.make(Register)
    accept = trellis.make(Accept)
    close = trellis.make(Close)
    
    def __init__(self, *args, **kwargs):
        super(SocketIO, self).__init__(*args, **kwargs)
        for condition in self.sockets,:
            if condition not in self.conditions:
                self.conditions.add(condition)
        for transition in self.register, self.accept, self.close:
            if transition not in self.transitions:
                self.transitions.add(transition)
        
        #
        # links
        #
        
        transition = self.register
        input = self.sockets
        output = self.poll.input
        for pair in ((input, transition), (transition, output),):
            arc = self.Arc()
            net.link(arc, *pair)

        transition = self.accept
        input = self.poll.output
        arc = self.Arc()
        net.link(arc, input, transition)
        output = self.sockets
        arc = self.Arc()
        net.link(arc, transition, output)
        
        transition = self.close
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

