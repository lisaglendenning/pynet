# @copyright
# @license

from __future__ import absolute_import

import collections

from peak.events import trellis

from pypetri import net
from pypetri.collections import collection, pool, mapping

from ..io import buffer, socket, sockbuf

from . import polls, sockets, orderedset


#############################################################################
#############################################################################

class FreeBufferPool(pool.Pool, collections.Sequence):
    r"""Default policy is MRU."""
    
    marking = trellis.make(orderedset.OrderedSet)
    filter = trellis.attr(lambda x: isinstance(x, sockbuf.SocketBuffer) and len(x.buffer) == 0)
    
    @trellis.compute
    def __getitem__(self):
        return self.marking.__getitem__
    
    @trellis.compute
    def __reversed__(self):
        return self.marking.__reversed__
    
    def Input(self):
        filter = self.filter
        def fn(m):
            for item in sockets.flatten(m, filter=filter):
                yield item
        arc = net.FilterOut(fn=fn)
        return arc
    
    def next(self, select=lambda m: reversed(m)):
        for event in super(FreeBufferPool, self).next(select):
            yield event

#############################################################################
#############################################################################

class MappedPool(mapping.Mapping):
    
    key = trellis.attr(None)
    filter = trellis.attr(None)

    @staticmethod
    def get(event, index, *args, **kwargs):
        return event(*args, **kwargs)[index]
    
    def Input(self):
        key = self.key
        filter = self.filter
        def fn(m):
            for item in sockets.flatten(m, filter=filter):
                k = key(item)
                yield k, item
        arc = net.FilterOut(fn=fn)
        return arc

#############################################################################
#############################################################################

class Muxed(net.Transition):

    def __init__(self, *args, **kwargs):
        k = 'mux'
        if k not in kwargs:
            mux = self.Mux(transition=self)
            kwargs[k] = mux
        k = 'pipe'
        if k not in kwargs:
            pipe = self.Pipe()
            kwargs[k] = pipe
        super(Muxed, self).__init__(*args, **kwargs)
        
#############################################################################
#############################################################################

class Send(Muxed):
    
    sending = trellis.attr(None)
    polled = trellis.attr(None)

    class Pipe(net.Pipe):
        
        def send(self, sock, buf, **kwargs):
            try:
                result = buf.send(**kwargs)
            except IOError as e:
                result = e
            output = result, sock, buf
            self.output.send(output, **kwargs)

    class Mux(net.Multiplexer):
    
        transition = trellis.attr(None)
        
        @trellis.compute
        def sending(self):
            return self.transition.sending
            
        @trellis.compute
        def polled(self):
            return self.transition.polled
        
        @trellis.compute
        def Event(self):
            return self.transition.Event
        
        def next(self, select=lambda m: m.iteritems()):
            for sending in self.sending.next(select=select):
                sock = sending.args[0][0]
                sending = self.Event(MappedPool.get, sending, 1)
                
                # event filter
                def filter(m):
                    if sock in m:
                        events = m[sock]
                        if events & polls.POLLOUT:
                            yield sock
                
                for polled in self.polled.next(select=filter):
                    polled = self.Event(MappedPool.get, polled, 0)
                    yield polled, sending
        
        def send(self, inputs, **kwargs):
            inputs = [i() for i in inputs]
            self.output.send(*inputs, **kwargs)

#############################################################################
#############################################################################

class Recv(Muxed):
    
    free = trellis.attr(None)
    receiving = trellis.attr(None)
    polled = trellis.attr(None)
    
    class Pipe(net.Pipe):

        def send(self, sock, buf, **kwargs):
            try:
                result = buf.recv(sock, **kwargs)
            except IOError as e:
                result = e
            output = result, sock, buf
            self.output.send(output, **kwargs)

    class Mux(net.Multiplexer):
    
        transition = trellis.attr(None)
        
        @trellis.compute
        def Event(self):
            return self.transition.Event
        
        @trellis.compute
        def receiving(self):
            return self.transition.receiving
            
        @trellis.compute
        def polled(self):
            return self.transition.polled
        
        @trellis.compute
        def free(self):
            return self.transition.free
        
        @staticmethod
        def select(marking):
            for k,v in marking.iteritems():
                if v & polls.POLLOUT:
                    yield k
    
        def pick_buffer(self, sock):
            # pick one buffer
            def filter(m):
                if sock in m:
                    buf = m[sock]
                    if buf.buffer.free:
                        yield (sock, buf,)
            for buffers in (self.receiving.next(select=filter),
                            self.free.next(),):
                for event in buffers:
                    buf = event.args[0]
                    if not isinstance(buf, sockbuf.SocketBuffer):
                        buf = buf[1]
                        event = self.Event(MappedPool.get, event, 1)
                    if buf.buffer.free:
                        return event
            return None
    
        def next(self, select=None):
            if select is None:
                select = self.select
            # for each socket with an input event, pick one buffer
            for polled in self.polled.next(select=select):
                sock = polled.args[0]
                polled = self.Event(MappedPool.get, polled, 0)
                buf = self.pick_buffer(sock)
                if buf is not None:
                    yield polled, buf

        def send(self, inputs, **kwargs):
            inputs = [i() for i in inputs]
            self.output.send(*inputs, **kwargs)
            
#############################################################################
#############################################################################

class BufferedSockets(sockets.Network):
    
    bufsize = trellis.attr(sockbuf.MTU)
    
    @trellis.modifier
    def Arc(self, source, sink, arc=None):
        if arc is None:
            if sink is self.free or sink is self.receiving or sink is self.sending:
                arc = sink.Input()
        return super(BufferedSockets, self).Arc(source, sink, arc)
    
    @trellis.modifier
    def Buffer(self, nbytes=None, *args, **kwargs):
        if nbytes is None:
            nbytes = self.bufsize
        buf = buffer.BufferStream(nbytes, *args, **kwargs)
        buf = sockbuf.SocketBuffer(buf)
        self.free.add(buf)
        return buf
    
    def Buffers(self):
        key = lambda x: (x.log[0].connection.local if isinstance(x.log[0].connection, sockbuf.Connection) else x.log[0].connection) if x.log else None
        filter = lambda x: isinstance(x, sockbuf.SocketBuffer) and x.log and len(x.buffer)
        return MappedPool(key=key, filter=filter)
    
    @trellis.maintain(make=FreeBufferPool)
    def free(self):
        condition = self.Condition(self.free)
        return condition
    
    @trellis.maintain(make=lambda self: self.Buffers())
    def sending(self):
        condition = self.Condition(self.sending)
        return condition
        
    @trellis.maintain(make=lambda self: self.Buffers())
    def receiving(self):
        condition = self.Condition(self.receiving)
        return condition

    @trellis.maintain(make=Send)
    def send(self):
        transition = self.Transition(self.send)
        for input in transition.inputs:
            input = input.input
            for attr, condition in (('sending', self.sending,),
                                    ('polled', self.poll.output,)):
                if input is condition and input is not getattr(transition, attr):
                    setattr(transition, attr, input)
        return transition
    
    @trellis.maintain(make=Recv)
    def recv(self):
        transition = self.Transition(self.recv)
        for input in transition.inputs:
            input = input.input
            for attr, condition in (('receiving', self.receiving,),
                                    ('free', self.free,),
                                    ('polled', self.poll.output,)):
                if input is condition and input is not getattr(transition, attr):
                    setattr(transition, attr, input)
        return transition
    
    def __init__(self, *args, **kwargs):
        super(BufferedSockets, self).__init__(*args, **kwargs)
                
        #
        # links
        #
        
        transition = self.recv
        inputs = self.poll.output, self.free, self.receiving,
        for input in inputs:
            self.Arc(input, transition)
        outputs = self.sockets, self.receiving, self.free
        for output in outputs:
            self.Arc(transition, output)
        
        transition = self.send
        inputs = self.poll.output, self.sending,
        for input in inputs:
            self.Arc(input, transition)
        outputs = self.sockets, self.sending, self.free
        for output in outputs:
            self.Arc(transition, output)
    
            
#############################################################################
#############################################################################

Network = BufferedSockets

#############################################################################
#############################################################################
