# @copyright
# @license

from __future__ import absolute_import

import collections
import itertools

from peak.events import trellis

from pypetri import net
from pypetri.collections import collection, pool, mapping, operators

from ..io import buffer, socket, sockbuf

from . import polls, sockets, orderedset, dispatch, match


#############################################################################
#############################################################################

class FreeBufferPool(pool.Pool):
    r"""Default policy is MRU."""
    
    marking = trellis.make(orderedset.OrderedSet)
    filter = trellis.attr(lambda x: isinstance(x, sockbuf.SocketBuffer))
    
    # flattens and filters input
    def update(self, arg, **kwargs):
        filter = self.filter
        for item in sockets.flatten(arg, filter, **kwargs):
            if len(item.buffer) == 0:
                self.add(item)
    
    def next(self, select=lambda m: reversed(m)):
        marking = self.marking
        if not marking:
            return
        for selection in select(marking):
            yield self.Event(self.pull, selection)

#############################################################################
#############################################################################

class ItemMapping(mapping.Mapping):
    
    filter = trellis.attr(None)
    key = trellis.attr(None)
    
    # filter and flatten input
    def update(self, *args):
        filter = self.filter
        add = self.__setitem__
        key = self.key
        for arg in args:
            if filter(arg):
                add(key(arg), arg)
                continue
            if isinstance(arg, collections.Mapping):
                for k,v in arg.iteritems():
                    if filter(v):
                        add(k, v)
                continue
            if isinstance(arg, (tuple, list,)):
                for v in arg:
                    if filter(v):
                        add(key(v), v)


class BufferMapping(ItemMapping):

    key = trellis.attr(lambda x: (x.log[0].connection.local if isinstance(x.log[0].connection, sockbuf.Connection) else x.log[0].connection) if x.log else None)
    filter = trellis.attr(lambda x: isinstance(x, sockbuf.SocketBuffer) and x.log and len(x.buffer))

Demand = collections.namedtuple('Demand', ('connection', 'nbytes',))
    
class Consumer(trellis.Component):
    
    caller = trellis.make(None)
    next = trellis.attr(None)
    
    def read(self, buf):
        caller = self.caller
        demand = self.next
        nbytes = demand.nbytes if isinstance(demand, Demand) else demand
        desc = buf.read(caller.send, nbytes)
        next = caller.send(desc)
        self.next = next
        
    def write(self, buf):
        caller = self.caller
        demand = self.next
        who = demand.connection if isinstance(demand, Demand) else demand
        nbytes = demand.nbytes if isinstance(demand, Demand) else demand
        desc = buf.write(caller.send, who, nbytes)
        next = caller.send(desc)
        self.next = next

class ConsumerMapping(ItemMapping):

    key = trellis.attr(lambda x: (x.next.connection[0] if isinstance(x.next.connection, tuple) else x.next.connection) if isinstance(x.next, Demand) else x.next)
    filter = trellis.attr(lambda x: isinstance(x, Consumer) and isinstance(x.next, Demand))


#############################################################################
#############################################################################

class Muxed(net.Transition):

    apply = trellis.attr(None)

    def __init__(self, *args, **kwargs):
        k = 'mux'
        if k not in kwargs:
            mux = self.Mux(transition=self)
            kwargs[k] = mux
        k = 'pipe'
        if k not in kwargs:
            pipe = operators.Apply(fn=self.apply)
            kwargs[k] = pipe
        super(Muxed, self).__init__(*args, **kwargs)
        
#############################################################################
#############################################################################

class Send(Muxed):
    
    sending = trellis.attr(None)
    polled = trellis.attr(None)
    
    @staticmethod
    def apply(inputs, **kwargs):
        sending, polled = [i() for i in inputs]
        sock = polled[0]
        buf = sending[1]
        try:
            result = buf.send(**kwargs)
        except IOError as e:
            result = e
        return result, sock, buf

    class Mux(operators.Multiplexer):
    
        transition = trellis.attr(None)
        
        @trellis.compute
        def sending(self):
            return self.transition.sending
            
        @trellis.compute
        def polled(self):
            return self.transition.polled
        
        def next(self, select=lambda m: m.iteritems()):
            sending = self.sending
            polled = self.polled
            for input in sending.next(select=select):
                sock = input.args[0][0]
                
                # event filter
                def filter(marking):
                    if sock in marking:
                        events = marking[sock]
                        if events & polls.POLLOUT:
                            yield sock
                
                for events in polled.next(select=filter):
                    yield input, events

#############################################################################
#############################################################################

class Recv(Muxed):
    
    free = trellis.attr(None)
    receiving = trellis.attr(None)
    polled = trellis.attr(None)
    
    @staticmethod
    def apply(inputs, **kwargs):
        polled, receiving = [i() for i in inputs]
        sock = polled[0]
        if not isinstance(receiving, sockbuf.SocketBuffer):
            buf = receiving[1]
        else:
            buf = receiving
        try:
            result = buf.recv(sock, **kwargs)
        except IOError as e:
            result = e
        return result, sock, buf

    class Mux(operators.Multiplexer):
    
        transition = trellis.attr(None)
        
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
                    if buf.buffer.free:
                        return event
            return None
    
        def next(self, select=None):
            polled = self.polled
            if select is None:
                select = self.select
            # for each socket with an input event, pick one buffer
            for input in polled.next(select=select):
                sock = input.args[0]
                buf = self.pick_buffer(sock)
                if buf is not None:
                    yield input, buf

#############################################################################
#############################################################################

class Write(Muxed):
    
    sending = trellis.attr(None)
    free = trellis.attr(None)
    writing = trellis.attr(None)
    
    @staticmethod
    def apply(inputs, **kwargs):
        writing, sending = [i() for i in inputs]
        consumer = writing[1]
        if not isinstance(sending, sockbuf.SocketBuffer):
            buf = sending[1]
        else:
            buf = sending
        consumer.write(buf, **kwargs)
        return consumer, buf

    class Mux(operators.Multiplexer):
    
        transition = trellis.attr(None)
        
        @trellis.compute
        def sending(self):
            return self.transition.sending
            
        @trellis.compute
        def free(self):
            return self.transition.free
        
        @trellis.compute
        def writing(self):
            return self.transition.writing
        
        def pick_buffer(self, connection, nbytes):
            # pick one buffer
            def filter(m):
                if isinstance(connection, sockbuf.Connection):
                    sock = connection.local
                else:
                    sock = connection
                if sock in m:
                    buf = m[sock]
                    yield (sock, buf,)
            for buffers in (self.sending.next(select=filter),
                            self.free.next(),):
                for event in buffers:
                    buf = event.args[0]
                    if not isinstance(buf, sockbuf.SocketBuffer):
                        buf = buf[1]
                    if buf.buffer.free >= nbytes:
                        return event
            return None
        
        def next(self, select=lambda m: m.iteritems()):
            # iterate on waiting writers
            writing = self.writing
            for input in writing.next(select=select):
                consumer = input.args[0][1]
                if isinstance(consumer.next, Demand):
                    who = consumer.next.connection
                    nbytes = consumer.next.nbytes
                    buf = self.pick_buffer(who, nbytes)
                    if buf is not None:
                        yield (input, buf,)

#############################################################################
#############################################################################

class Read(Muxed):
    
    receiving = trellis.attr(None)
    reading = trellis.attr(None)
    
    @staticmethod
    def apply(inputs, **kwargs):
        buf, consumer = [i()[1] for i in inputs]
        consumer.read(buf, **kwargs)
        return consumer, buf

    class Mux(operators.Multiplexer):
    
        transition = trellis.attr(None)
        
        @trellis.compute
        def receiving(self):
            return self.transition.receiving
        
        @trellis.compute
        def reading(self):
            return self.transition.reading
        
        def next(self, select=lambda m: m.iteritems()):
            # iterate on readable buffers
            receiving = self.receiving
            reading = self.reading
            for received in receiving.next(select=select):
                sock, buf = received.args[0]
                def filter(m):
                    if sock in m:
                        consumer = m[sock]
                        if isinstance(consumer.next, Demand):
                            if buf.log[0].nbytes >= consumer.next.nbytes:
                                yield (sock, consumer,)
                for reader in reading.next(select=filter):
                    yield received, reader

        
#############################################################################
#############################################################################

class SocketBufferIO(sockets.Network):
    
    bufsize = trellis.attr(sockbuf.MTU)
    
    @trellis.modifier
    def Buffer(self, nbytes=None, *args, **kwargs):
        if nbytes is None:
            nbytes = self.bufsize
        buf = buffer.BufferStream(nbytes, *args, **kwargs)
        buf = sockbuf.SocketBuffer(buf)
        self.free.add(buf)
        return buf

    def Condition(self, condition):
        if condition not in self.conditions:
            self.conditions.add(condition)
        return condition
    
    @trellis.maintain(make=FreeBufferPool)
    def free(self):
        condition = self.Condition(self.free)
        return condition
    
    @trellis.maintain(make=BufferMapping)
    def sending(self):
        condition = self.Condition(self.sending)
        return condition
        
    @trellis.maintain(make=BufferMapping)
    def receiving(self):
        condition = self.Condition(self.receiving)
        return condition

    @trellis.maintain(make=ConsumerMapping)
    def writing(self):
        condition = self.Condition(self.writing)
        return condition
    
    @trellis.maintain(make=ConsumerMapping)
    def reading(self):
        condition = self.Condition(self.reading)
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
    
    @trellis.maintain(make=Write)
    def write(self):
        transition = self.Transition(self.write)
        for input in transition.inputs:
            input = input.input
            for attr, condition in (('free', self.free,),
                                    ('sending', self.sending,),
                                    ('writing', self.writing,)):
                if input is condition and input is not getattr(transition, attr):
                    setattr(transition, attr, input)
        return transition
    
    @trellis.maintain(make=Read)
    def read(self):
        transition = self.Transition(self.read)
        for input in transition.inputs:
            input = input.input
            for attr, condition in (('reading', self.reading,),
                                    ('receiving', self.receiving,),):
                if input is condition and input is not getattr(transition, attr):
                    setattr(transition, attr, input)
        return transition
    
    def __init__(self, *args, **kwargs):
        super(SocketBufferIO, self).__init__(*args, **kwargs)
                
        #
        # links
        #
        
        transition = self.recv
        inputs = self.poll.output, self.free, self.receiving,
        for input in inputs:
            arc = self.Arc()
            net.link(arc, input, transition,)
        outputs = self.sockets, self.receiving, self.free
        for output in outputs:
            arc = self.Arc()
            net.link(arc, transition, output,)
        
        transition = self.send
        inputs = self.poll.output, self.sending,
        for input in inputs:
            arc = self.Arc()
            net.link(arc, input, transition,)
        outputs = self.sockets, self.sending, self.free
        for output in outputs:
            arc = self.Arc()
            net.link(arc, transition, output,)
    
        transition = self.read
        inputs = self.receiving, self.reading,
        for input in inputs:
            arc = self.Arc()
            net.link(arc, input, transition,)
        outputs = self.receiving, self.free, self.reading,
        for output in outputs:
            arc = self.Arc()
            net.link(arc, transition, output,)
          
        transition = self.write
        inputs = self.sending, self.free, self.writing,
        for input in inputs:
            arc = self.Arc()
            net.link(arc, input, transition,)
        outputs = inputs
        for output in outputs:
            arc = self.Arc()
            net.link(arc, transition, output,)
            
#############################################################################
#############################################################################

Network = SocketBufferIO

#############################################################################
#############################################################################
