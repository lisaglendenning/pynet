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

class SocketPolling(polls.Network):
    
    input = trellis.make(None)
    output = trellis.make(None)
    
    def __init__(self, *args, **kwargs):
        for k in 'input', 'output':
            if k not in kwargs:
                kwargs[k] = self.Condition()
        super(SocketPolling, self).__init__(*args, **kwargs)
        for pair in ((self.input, self.poll), (self.poll, self.output,)):
            arc = self.Arc()
            net.link(arc, *pair)

#############################################################################
#############################################################################

class Register(net.Transition):
    
    @staticmethod
    def filter(inputs):
        outputs = []
        for input in inputs:
            active = []
            for sock in input.keywords['items']:
                for state in sock.state, sock.next:
                    if state in (sock.CLOSED, sock.ERROR,):
                        break
                else:
                    if not (sock.state == sock.START and sock.next is None):
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
                events = 0
                for state in sock.state, sock.next:
                    if state in (sock.CLOSED, sock.ERROR,):
                        break
                else:
                    if sock.LISTENING in (sock.state, sock.next,):
                        events = polls.POLLIN
                    elif not (sock.state == sock.START and sock.next is None):
                        events = polls.POLLIN | polls.POLLOUT
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

class SocketPool(net.Network):

    @trellis.modifier
    def Condition(self, *args, **kwargs):
        condition = pool.Pool(*args, **kwargs)
        self.conditions.add(condition)
        return condition
    
    @trellis.modifier
    def Socket(self, *args, **kwargs):
        sock = socket.Socket.new(*args, **kwargs)
        self.sockets.add(sock)
        return sock
    
    poll = trellis.make(SocketPolling)
    sockets = trellis.make(Condition)
    register = trellis.make(Register)
    accept = trellis.make(Accept)
    close = trellis.make(Close)
    
    def __init__(self, *args, **kwargs):
        super(SocketPool, self).__init__(*args, **kwargs)
        
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
        def accepted(*args):
            q = list(args)
            while q:
                item = q.pop(0)
                if isinstance(item, socket.Socket):
                    yield item
                elif isinstance(item, (tuple, list)):
                    q.extend(item)
        arc = operators.FilterOut(fn=accepted)
        self.arcs.add(arc)
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

Network = SocketPool

#############################################################################
#############################################################################

