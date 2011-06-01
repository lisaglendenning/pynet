# @copyright
# @license

from __future__ import absolute_import

import collections

from peak.events import trellis

from pypetri import net
from pypetri.collections import operators

from ..io import sockbuf, socket
from . import buffered

#############################################################################
#############################################################################

class Message(collections.namedtuple('Message', ('header', 'payload'))):
    __slots__ = ()

#############################################################################
#############################################################################

class MappedQueues(buffered.MappedPool):

    Queue = collections.deque
    
    def __contains__(self, k):
        return collections.Mapping.__contains__(self, k)
    
    def __getitem__(self, k):
        q = self.marking[k]
        if not q:
            raise KeyError(k)
        return q[0]
    
    def __setitem__(self, k, v):
        if k not in self:
            q = self.Queue()
            self.marking[k] = q
        else:
            q = self.marking[k]
        q.append(v)
    
    def pop(self, k):
        q = self.marking[k]
        return q.popleft()

#############################################################################
#############################################################################

class Consumer(collections.namedtuple('Consumer', ('connection', 'caller', 'nbytes'))):
    __slots__ = ()

    def read(self, buf):
        caller = self.caller
        nbytes = self.nbytes
        desc = buf.read(caller.send, nbytes)
        next = caller.next()
        if isinstance(next, tuple):
            item, next = next
            next = self._replace(nbytes=next)
            item = Message(desc.connection, item)
            next = item, next
        else:
            next = self._replace(nbytes=next)
        return next
        
    def write(self, buf):
        caller = self.caller
        nbytes = self.nbytes
        connection = self.connection
        buf.write(caller.send, connection, nbytes)
        next = caller.next()
        next = self._replace(nbytes=next)
        return next
    
    def send(self, item):
        caller = self.caller
        connection, item = item
        next = caller.send(item)
        next = self._replace(connection=connection, nbytes=next)
        return next
    
    def next(self):
        caller = self.caller
        next = caller.next()
        if next != self.nbytes:
            next = self._replace(nbytes=next)
        else:
            next = self
        return next
        

#############################################################################
#############################################################################

class Write(buffered.Muxed):
    
    factory = trellis.attr(None)
    
    sending = trellis.attr(None)
    free = trellis.attr(None)
    writing = trellis.attr(None)
    input = trellis.attr(None)
    
    def new(self, connection):
        caller = self.factory()
        consumer = Consumer(caller=caller, connection=connection, nbytes=None)
        return consumer
        
    class Pipe(operators.Pipe):
        def send(self, consumer, output, **kwargs):
            if isinstance(output, sockbuf.SocketBuffer):
                next = consumer.write(output)
                output = next, output
            else:
                output = consumer.send(output)
            self.output.send(output, **kwargs)

    class Mux(operators.Multiplexer):
    
        transition = trellis.attr(None)
        
        @trellis.compute
        def Event(self):
            return self.transition.Event
        
        @trellis.compute
        def new(self):
            return self.transition.new
        
        @trellis.compute
        def sending(self):
            return self.transition.sending
            
        @trellis.compute
        def free(self):
            return self.transition.free
        
        @trellis.compute
        def writing(self):
            return self.transition.writing
        
        @trellis.compute
        def input(self):
            return self.transition.input
        
        def pick_buffer(self, connection, nbytes):
            def filter(m):
                if isinstance(connection, sockbuf.Connection):
                    sock = connection.local
                else:
                    sock = connection
                if sock in m:
                    buf = m[sock]
                    yield (sock, buf,)
            # pick one buffer
            for buffers in (self.sending.next(select=filter),
                            self.free.next(),):
                for event in buffers:
                    buf = event.args[0]
                    if not isinstance(buf, sockbuf.SocketBuffer):
                        buf = buf[1]
                        event = self.Event(buffered.MappedPool.get, event, 1)
                    if buf.buffer.free >= nbytes:
                        return event
            return None
        
        def next(self, select=lambda m: m.iteritems()):
            # iterate on waiting writers
            for writer in self.writing.next(select=select):
                connection, consumer = writer.args[0]
                writer = self.Event(buffered.MappedPool.get, writer, 1)
                nbytes = consumer.nbytes
                if nbytes is not None:
                    buf = self.pick_buffer(connection, nbytes)
                    if buf is not None:
                        yield writer, buf
            
            # iterate on input queues
            for input in self.input.next(select=select):
                connection = input.args[0][0]
                input = self.Event(buffered.MappedPool.get, input, 1)
                def filter(m):
                    if connection in m:
                        consumer = m[connection]
                        if consumer.nbytes is None:
                                yield connection, consumer
                matches = [e for e in self.writing.next(select=filter)]
                if matches:
                    assert len(matches) == 1
                    match = matches[0]
                else:
                    match = self.Event(self.new, connection)
                yield match, input
        
        def send(self, inputs, **kwargs):
            inputs = [i() for i in inputs]
            self.output.send(*inputs, **kwargs)

#############################################################################
#############################################################################

class Read(buffered.Muxed):
    
    factory = trellis.attr(None)
    
    receiving = trellis.attr(None)
    reading = trellis.attr(None)
    
    def new(self, connection):
        caller = self.factory()
        consumer = Consumer(connection=connection, caller=caller, nbytes=None)
        return consumer
        
    class Pipe(operators.Pipe):
        def send(self, consumer, buf=None, **kwargs):
            if buf is None:
                output = consumer.next()
            else:
                next = consumer.read(buf, **kwargs)
                output = next, buf
            self.output.send(output, **kwargs)
    
    class Mux(operators.Multiplexer):
    
        transition = trellis.attr(None)
        
        @trellis.compute
        def Event(self):
            return self.transition.Event
        
        @trellis.compute
        def receiving(self):
            return self.transition.receiving
        
        @trellis.compute
        def reading(self):
            return self.transition.reading
        
        @trellis.compute
        def new(self):
            return self.transition.new
        
        def next(self, select=lambda m: m.iteritems()):
            # iterate on readable buffers
            for receiving in self.receiving.next(select=select):
                buf = receiving.args[0][1]
                connection = buf.log[0].connection
                def filter(m):
                    if connection in m:
                        consumer = m[connection]
                        if consumer.nbytes is None \
                            or buf.log[0].nbytes >= consumer.nbytes:
                                yield (connection, consumer,)
                matches = [e for e in self.reading.next(select=filter)]
                if matches:
                    assert len(matches) == 1
                    match = self.Event(buffered.MappedPool.get, matches[0], 1)
                    receiving = self.Event(buffered.MappedPool.get, receiving, 1)
                    yield match, receiving
                else:
                    match = self.Event(self.new, connection)
                    yield match,

        def send(self, inputs, **kwargs):
            inputs = [i() for i in inputs]
            self.output.send(*inputs, **kwargs)
        
#############################################################################
#############################################################################

class Serializing(net.Network):
    
    serializer = trellis.attr(None)
    deserializer = trellis.attr(None)
    
    @trellis.modifier
    def Arc(self, source, sink, arc=None):
        if arc is None:
            if sink is self.reading \
                or sink is self.writing \
                or sink is self.input \
                or sink is self.output \
                or sink is self.io.receiving \
                or sink is self.io.sending \
                or sink is self.io.free:
                arc = sink.Input()
            else:
                arc = super(Serializing, self).Arc()
        if arc not in self.arcs:
            self.arcs.add(arc)
        net.link(arc, source, sink)
        return arc
    
    @trellis.modifier
    def Transition(self, transition):
        if transition not in self.transitions:
            self.transitions.add(transition)
        return transition

    @trellis.modifier
    def Condition(self, condition):
        if condition not in self.conditions:
            self.conditions.add(condition)
        return condition
    
    def Consumers(self):
        key = lambda x: x.connection
        filter = lambda x: isinstance(x, Consumer)
        return buffered.MappedPool(key=key, filter=filter)

    def Messages(self):
        key = lambda x: x.header
        filter = lambda x: isinstance(x, Message)
        return MappedQueues(key=key, filter=filter)

    @trellis.maintain(make=lambda self: self.Messages())
    def input(self):
        return self.Condition(self.input)
    
    @trellis.maintain(make=lambda self: self.Messages())
    def output(self):
        return self.Condition(self.output)
    
    @trellis.maintain(make=lambda self: self.Consumers())
    def writing(self):
        condition = self.Condition(self.writing)
        return condition
    
    @trellis.maintain(make=lambda self: self.Consumers())
    def reading(self):
        condition = self.Condition(self.reading)
        return condition
    
    @trellis.maintain(make=Write)
    def write(self):
        transition = self.Transition(self.write)
        if transition.factory != self.serializer:
            transition.factory = self.serializer
        for input in transition.inputs:
            input = input.input
            for attr, condition in (('free', self.io.free,),
                                    ('sending', self.io.sending,),
                                    ('writing', self.writing,),
                                    ('input', self.input,),):
                if input is condition and input is not getattr(transition, attr):
                    setattr(transition, attr, input)
        return transition
    
    @trellis.maintain(make=Read)
    def read(self):
        transition = self.Transition(self.read)
        if transition.factory != self.deserializer:
            transition.factory = self.deserializer
        for input in transition.inputs:
            input = input.input
            for attr, condition in (('reading', self.reading,),
                                    ('receiving', self.io.receiving,),):
                if input is condition and input is not getattr(transition, attr):
                    setattr(transition, attr, input)
        return transition
    
    @trellis.maintain(make=buffered.Network)
    def io(self):
        io = self.io
        return io

    def __init__(self, *args, **kwargs):
        super(Serializing, self).__init__(*args, **kwargs)
                
        transition = self.read
        inputs = self.io.receiving, self.reading,
        for input in inputs:
            self.Arc(input, transition)
        outputs = self.io.receiving, self.io.free, self.reading, self.output,
        for output in outputs:
            self.Arc(transition, output)
          
        transition = self.write
        inputs = self.io.sending, self.io.free, self.writing, self.input,
        for input in inputs:
            self.Arc(input, transition)
        outputs = self.io.sending, self.io.free, self.writing,
        for output in outputs:
            self.Arc(transition, output)

#############################################################################
#############################################################################

Network = Serializing

#############################################################################
#############################################################################
