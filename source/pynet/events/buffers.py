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

class FreeBufferPool(sockets.FilteredPool):
    r"""Default policy is MRU."""
    
    marking = trellis.make(orderedset.OrderedSet)
    filter = trellis.attr(lambda x: isinstance(x, sockbuf.SocketBuffer) and len(x.buffer) == 0)
               
    def next(self, select=lambda m: itertools.imap(None, reversed(m))):
        marking = self.marking
        if not marking:
            return
        for selection in select(marking):
            yield self.Event(self.pull, selection)

#############################################################################
#############################################################################

class Queues(mapping.Mapping):
    
    key = trellis.attr(None)
    filter = trellis.attr(None)

    @trellis.modifier
    def add(self, item,):
        k = self.key(item)
        if k in self.marking:
            self.marking[k].append(item)
        else:
            q = collections.deque()
            q.append(item)
            self.marking[k] = q
        
    @trellis.modifier
    def send(self, *args):
        filter = self.filter
        q = list(args)
        while q:
            item = q.pop(0)
            if filter(item):
                self.add(item)
            elif isinstance(item, (tuple, list)):
                q.extend(item)
        
    @trellis.modifier
    def pop(self, item,):
        if isinstance(item, tuple):
            k = item[0]
        else:
            k = item
        if k not in self:
            raise KeyError(k)
        return self.marking[k].popleft()

class BufferQueues(Queues):

    key = trellis.attr(lambda x: (x.log[0].who[0] if isinstance(x.log[0].who, tuple) else x.log[0].who) if x.log else None)
    filter = trellis.attr(lambda x: isinstance(x, sockbuf.SocketBuffer) and len(x.log) > 0)

Callback = collections.namedtuple('Callback', ('sock', 'call', 'nbytes',))

class CallbackQueues(Queues):

    key = trellis.attr(lambda x: x.sock)
    filter = trellis.attr(lambda x: isinstance(x, Callback))


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
        buf, sock = [i()[0] for i in inputs]
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
        
        def next(self, select=lambda m: itertools.imap(None, m.iteritems()),):
            sending = self.sending
            polled = self.polled
            for input in sending.next(select=select):
                sock = input.args[0][0][0] # lols
                
                # event filter
                def filter(marking):
                    if sock in marking:
                        events = marking[sock]
                        if events & polls.POLLOUT:
                            yield (sock,)
                
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
        sock, buf = [i()[0] for i in inputs]
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
                    yield (k,)
    
        def pick_buffer(self, sock):
            # pick one buffer
            def filter(m):
                if sock in m:
                    buf = m[sock]
                    if buf.buffer.free:
                        yield ((sock, buf,),)
            receiving = self.receiving
            for buf in receiving.next(select=filter):
                return buf
            free = self.free
            for buf in free.next():
                return buf
            return None
    
        def next(self, select=None):
            polled = self.polled
            if select is None:
                select = self.select
            # for each socket with an input event, pick one buffer
            for input in polled.next(select=select):
                sock = input.args[0][0]
                buf = self.pick_buffer(sock)
                if buf is not None:
                    yield (input, buf)

#############################################################################
#############################################################################

#class ToRead(operators.Multiplexer):
#
#    received = trellis.attr(None)
#    readers = trellis.attr(None)
#
#    def next(self, iterator=None, *args, **kwargs):
#        # Input events
#        itr = self.received.next(*args, **kwargs)
#        try:
#            received = itr.next()
#        except StopIteration:
#            return
#        itr = self.readers.next(*args, **kwargs)
#        try:
#            readers = itr.next()
#        except StopIteration:
#            return
#        
#        # anything to read?
#        qs = received.keywords['items']
#        cbs = readers.keywords['items']
#        if iterator is None:
#            iterator = qs
#        else:
#            iterator = itertools.ifilter(lambda x: x in qs, iterator(qs))
#        for sock in iterator:
#            if sock in cbs:
#                cb = cbs[sock]
#                buf = qs[sock]
#                if cb.demand <= buf.log[0].nbytes:
#                    inputs = (received.__class__(received.func, item=sock),
#                              readers.__class__(readers.func, item=sock),)
#                    yield inputs
#            
#class ToWrite(operators.Multiplexer):
#
#    free = trellis.attr(None)
#    sending = trellis.attr(None)
#    writers = trellis.attr(None)
#    
#    def find_buffer(self, who, demand):
#        sending = self.sending
#        filter = lambda k: k == who
#        for event in sending.next(select=filter):
#        free = self.free
#
#    def next(self, *args, **kwargs):
#        itr = self.sending.next(*args, **kwargs)
#        try:
#            sending = itr.next()
#        except StopIteration:
#            sending = None
#        itr = self.free.next(*args, **kwargs)
#        try:
#            free = itr.next()
#        except StopIteration:
#            free = None
#        if sending is None and free is None: # no available buffers
#            return
#        writers = self.writers
#        for writer in writers.next(*args, **kwargs):
#            who = writer.args[0]
#            
#            for buf
#            
#            if sending is not None and who in sending:
#                available =  
#        # anything to read?
#        qs = received.keywords['items']
#        cbs = readers.keywords['items']
#        if iterator is None:
#            iterator = qs
#        else:
#            iterator = itertools.ifilter(lambda x: x in qs, iterator(qs))
#        for writer in iterator:
#            if sock in cbs:
#                cb = cbs[sock]
#                buf = qs[sock]
#                if cb.demand <= buf.log[0].nbytes:
#                    inputs = (received.__class__(received.func, item=sock),
#                              readers.__class__(readers.func, item=sock),)
#                    yield inputs
#                    
#class Read(net.Transition):
#
#    @staticmethod
#    def reads(inputs, **kwargs):
#        buf, reader = [i() for i in inputs]
#        result = reader.call(buf, **kwargs)
#        return result, buf
#    
#    def __init__(self, *args, **kwargs):
#        k = 'mux'
#        if k not in kwargs:
#            mux = ToRead()
#            kwargs[k] = mux
#        k = 'pipe'
#        if k not in kwargs:
#            pipe = operators.Apply(fn=self.reads)
#            kwargs[k] = pipe
#        super(Recv, self).__init__(*args, **kwargs)
        
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
    
    @trellis.maintain(make=BufferQueues)
    def sending(self):
        condition = self.Condition(self.sending)
        return condition
        
    @trellis.maintain(make=BufferQueues)
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
    
#    read = trellis.make(Read)
#    write = trellis.make(Write)
    
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
    
#        transition = self.read
#        inputs = ('received', self.received,),
#        for attr, input in inputs:
#            arc = self.Arc()
#            net.link(arc, input, transition,)
#        outputs = self.received, self.free
#        for output in outputs:
#            arc = self.Arc()
#            net.link(arc, transition, output,)
#            
#        transition = self.write
#        inputs = ('sending', self.sending,), ('free', self.free,)
#        for attr, input in inputs:
#            arc = self.Arc()
#            net.link(arc, input, transition,)
#        outputs = self.sending, self.free
#        for output in outputs:
#            arc = self.Arc()
#            net.link(arc, transition, output,)
            
#############################################################################
#############################################################################

Network = SocketBufferIO

#############################################################################
#############################################################################
