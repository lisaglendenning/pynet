# @copyright
# @license

from __future__ import absolute_import

import collections

from peak.events import trellis

from pypetri import net
from pypetri.collections import pool, operators

from ..io import socket
from . import polls

#############################################################################
#############################################################################

class Piped(net.Arc):
    
    pipe = trellis.attr(None)
    
    @trellis.maintain
    def _pipes(self):
        pipe = self.pipe
        if pipe is None:
            return
        if pipe.input is not self.input:
            pipe.input = self.input
        if pipe.output is not self.output:
            pipe.output = self.output
    
    @trellis.compute
    def send(self):
        output = self.pipe if self.pipe is not None else self.output
        if output is not None:
            return output.send
        else:
            return net.nada
        
    @trellis.compute
    def next(self):
        input = self.pipe if self.pipe is not None else self.input
        if input is not None:
            return input.next
        else:
            return net.nada

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
            arc.link(*pair)

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
    register = trellis.make(None)
    accept = trellis.make(None)
    close = trellis.make(None)

    def __init__(self, *args, **kwargs):
        k = 'register'
        if k not in kwargs:
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
            pipe = operators.Pipeline(operators.FilterIn(fn=filter),
                                      operators.Apply(fn=register),)
            transition = self.Transition(pipe=pipe,)
            kwargs[k] = transition
        k = 'accept'
        if k not in kwargs:
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
            def accept(input):
                try:
                    accepted = input.accept()
                except Exception as e:
                    accepted = e
                return accepted, input
            pipe = operators.Pipeline(operators.FilterIn(fn=filter),
                                      operators.Iter(),
                                      operators.Call(),
                                      operators.Iter(),
                                      operators.Apply(fn=accept),)
            transition = self.Transition(pipe=pipe,)
            kwargs[k] = transition
        k = 'close'
        if k not in kwargs:
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
            def close(sock):
                try:
                    sock.close()
                except Exception: # TODO
                    pass
                return sock
            pipe = operators.Pipeline(operators.FilterIn(fn=filter),
                                      operators.Iter(),
                                      operators.Call(),
                                      operators.Iter(),
                                      operators.Apply(fn=close),)
            transition = self.Transition(pipe=pipe,)
            kwargs[k] = transition
            
        super(SocketPool, self).__init__(*args, **kwargs)
        
        # Arcs
        for pair in ((self.sockets, self.register,), 
                     (self.register, self.poll.input,),
                     (self.poll.output, self.accept,),
                     (self.sockets, self.close,),
                     (self.poll.input, self.close,),
                     (self.poll.output, self.close,),
                     (self.close, self.sockets,),):
            arc = self.Arc()
            arc.link(*pair)
        pair = (self.accept, self.sockets,)
        def accepted(*args):
            q = list(args)
            while q:
                item = q.pop(0)
                if isinstance(item, socket.Socket):
                    yield item
                elif isinstance(item, (tuple, list)):
                    q.extend(item)
        pipe = operators.FilterOut(fn=accepted)
        arc = Piped(pipe=pipe)
        self.arcs.add(arc)
        arc.link(*pair)
    
#############################################################################
#############################################################################

Network = SocketPool

#############################################################################
#############################################################################

