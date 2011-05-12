
from __future__ import absolute_import

import collections

from peak.events import trellis

from pypetri import net

from ..io import socket
from . import poll

#############################################################################
#############################################################################

# TODO: refactor set and mapping conditions out
class Pool(collections.MutableSet, net.Condition):
    
    marking = trellis.make(trellis.Set)
    
    def __hash__(self):
        return object.__hash__(self)
    
    def __eq__(self, other):
        return self is other
    
    @trellis.compute
    def add(self):
        return self.marking.add

    @trellis.compute
    def discard(self):
        return self.marking.discard
    
    @trellis.compute
    def __len__(self):
        return self.marking.__len__
    
    @trellis.compute
    def __iter__(self):
        return self.marking.__iter__
    
    @trellis.compute
    def __contains__(self):
        return self.marking.__contains__
    
    def pull(self, i):
        self.discard(i)
        return i

    def send(self, *args):
        for item in args:
            self.add(item)

    def next(self, iterator=None):
        if iterator is None:
            iterator=iter
        for i in iterator(self):
            yield self.Event(self.pull, i)

class Register(net.Transition):

    # TODO: register for POLLOUT only if there's something to write?
    def send(self, thunks, outputs=None):
        if outputs is None:
            outputs = self.outputs
        for thunk in thunks:
            sock = thunk()
            events = 0
            for state in sock.state, sock.next:
                if state in (sock.CLOSED, sock.ERROR,):
                    break
            else:
                if sock.LISTENING in (sock.state, sock.next,):
                    events = poll.POLLIN
                elif not(sock.state == sock.START and sock.next is None):
                    events = poll.POLLIN | poll.POLLOUT
            out = (sock, events)
            for output in outputs:
                output.send(out)

class Accept(net.Transition):

    def send(self, thunks, outputs=None):
        if outputs is None:
            outputs = self.outputs
        for thunk in thunks:
            polled = thunk()
            for sock in polled:
                try:
                    accepted = sock.accept()
                except Exception as e:
                    accepted = e
                for output in outputs:
                    output.send(accepted, sock,)

class Close(net.Transition):
    
    def send(self, thunks, outputs=None):
        if outputs is None:
            outputs = self.outputs
        for thunk in thunks:
            socks = thunk()
            for sock in socks:
                try:
                    sock.close()
                except Exception: # FIXME
                    pass
                for output in outputs:
                    output.send(sock)

class Filter(net.Arc):
    
    filter = trellis.make(None)
    
    def next(self, *args, **kwargs):
        for event in super(Filter, self).next(*args, **kwargs):
            for filtered in self.filter(event):
                yield filtered
            
            
class Split(net.Arc):
    
    split = trellis.make(None)
    
    def send(self, *args, **kwargs):
        for filtered in self.split(*args, **kwargs):
            super(Split, self).send(filtered)

class SocketPolling(poll.Polling):

    @trellis.maintain(make=poll.Polling.Condition)
    def input(self):
        input = self.input
        if input not in self.vertices:
            self.vertices.add(input)
        poll = self.poll
        for o in input.outputs:
            if o.output is poll:
                break
        else:
            self.link(input, poll,)
        return input
    
    @trellis.maintain(make=poll.Polling.Condition)
    def output(self):
        output = self.output
        if output not in self.vertices:
            self.vertices.add(output)
        poll = self.poll
        for i in output.inputs:
            if i.input is poll:
                break
        else:
            self.link(poll, output)
        return output

class SocketPool(net.Network):

    @trellis.modifier
    def Socket(self, *args, **kwargs):
        sock = socket.Socket.new(*args, **kwargs)
        self.sockets.add(sock)
        return sock
    
    @trellis.maintain(make=SocketPolling)
    def poll(self):
        poll = self.poll
        self.vertices.add(poll)
        return poll
        
    @trellis.maintain(make=Pool)
    def sockets(self):
        sockets = self.sockets
        self.vertices.add(sockets)
        return sockets
    
    @trellis.maintain(make=Register)
    def register(self):
        register = self.register
        if register not in self.vertices:
            self.vertices.add(register)
        input = self.sockets
        for i in register.inputs:
            if i.input is input:
                break
        else:
            self.link(input, register,)
        output = self.poll.input
        for o in register.outputs:
            if o.output is output:
                break
        else:
            self.link(register, output,)
        return register
    
    @trellis.maintain(initially=None)
    def accept(self):
        accept = self.accept
        if accept is None:
            accept = Accept()
            self.vertices.add(accept)
            def input(event):
                listeners = []
                registry = event.args[0]
                for sock in registry:
                    if sock.state == sock.LISTENING:
                        polled = registry[sock]
                        if polled & poll.POLLIN:
                            listeners.append((sock, polled))
                if listeners:
                    if event.keywords:
                        event = event.__class__(event.func, listeners, **event.keywords)
                    else:
                        event.__class__(event.func, listeners,)
                    yield event
            self.link(self.poll.output, accept, Arc=Filter, filter=input)
            def output(*args, **kwargs): # FIXME: clunky
                for arg in args:
                    if isinstance(arg, socket.Socket):
                        yield arg
                    elif isinstance(arg, tuple):
                        for item in arg:
                            if isinstance(item, socket.Socket):
                                yield item
            self.link(accept, self.sockets, Arc=Split, split=output)
        return accept

    @trellis.maintain(initially=None)
    def close(self):
        def input(event):
            inputs = event.args[0]
            try:
                inputs = inputs.keys()
            except AttributeError:
                pass
            if inputs:
                if event.keywords:
                    event = event.__class__(event.func, inputs, **event.keywords)
                else:
                    event.__class__(event.func, inputs,)
                yield event
        close = self.close
        if close is None:
            close = Close()
            self.vertices.add(close)
            self.link(close, self.sockets,)
        # sockets can be closed at any time
        for v in self.poll.input, self.poll.output, self.sockets:
            for o in v.outputs:
                if o.output is close:
                    break
            else:
                self.link(v, close, Arc=Filter, filter=input)
        return close
    
#############################################################################
#############################################################################
