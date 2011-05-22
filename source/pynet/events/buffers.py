# @copyright
# @license

from __future__ import absolute_import

import collections
import itertools

from peak.events import trellis

from pypetri import net
from pypetri.collections import pool, mapping, operators

from ..io import buffer, socket, sockbuf

from . import polls, sockets, orderedset


#############################################################################
#############################################################################

class BufferPool(sockets.FilteredPool):
    
    marking = trellis.make(orderedset.OrderedSet)
    fn = trellis.attr(lambda x: isinstance(x, sockbuf.SocketBuffer) and len(x.buffer) == 0)
                
    def next(self):
        r"""For lack of a better policy, return the MRU buffer."""
        if len(self):
            yield self.Event(self.pop)
    
    @trellis.compute
    def pop(self,):
        return self.marking.pop

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

    key = trellis.attr(lambda x: x.log[0].who[0] if isinstance(x.log[0].who, tuple) else x.log[0].who)
    filter = trellis.attr(lambda x: isinstance(x, sockbuf.SocketBuffer) and len(x.log) > 0)

#############################################################################
#############################################################################

class ToSend(operators.Multiplexer):

    sending = trellis.attr(None)
    polled = trellis.attr(None)

    def next(self, iterator=None, *args, **kwargs):
        # Input events
        itr = self.polled.next(*args, **kwargs)
        try:
            polled = itr.next()
        except StopIteration:
            return
        itr = self.sending.next(*args, **kwargs)
        try:
            sending = itr.next()
        except StopIteration:
            return
        
        # filter sockets that are writable and have something to write
        events = polled.keywords['items']
        qs = sending.keywords['items']
        if iterator is None:
            iterator = qs
        else:
            iterator = iterator(qs)
        for sock in itertools.ifilter(lambda x: x in events and events[x] & polls.POLLOUT, 
                                      iterator):
            if sock not in qs or not qs[sock]:
                continue
            inputs = (polled.__class__(polled.func, item=sock),
                      sending.__class__(sending.func, item=sock),)
            yield inputs


class ToRecv(operators.Multiplexer):

    free = trellis.attr(None)
    received = trellis.attr(None)
    polled = trellis.attr(None)

    def next(self, iterator=None, *args, **kwargs):
        # Input events
        itr = self.polled.next(*args, **kwargs)
        try:
            polled = itr.next()
        except StopIteration:
            return
        itr = self.free.next(*args, **kwargs)
        try:
            free = itr.next()
        except StopIteration:
            free = None
        itr = self.received.next(*args, **kwargs)
        try:
            received = itr.next()
        except StopIteration:
            received = None
        if received is None and free is None:
            return
        
        # filter sockets that are readable
        events = polled.keywords['items']
        if received is not None:
            bufs = received.keywords['items']
        else:
            bufs = {}
        if iterator is None:
            iterator = events
        else:
            iterator = itertools.ifilter(lambda x: x in events, iterator(events))
        for sock in itertools.ifilter(lambda x: events[x] & polls.POLLIN, iterator):
            if sock in bufs:
                buf = received.__class__(received.self.pop, item=sock)
            else:
                buf = free
            inputs = (polled.__class__(polled.func, item=sock),
                      buf,)
            yield inputs

class Recv(net.Transition):
    
    @staticmethod
    def recvs(inputs, **kwargs):
        sock, buf = [i() for i in inputs]
        try:
            result = buf.recv(sock, **kwargs)
        except IOError as e:
            result = e
        return result, sock, buf
    
    def __init__(self, *args, **kwargs):
        k = 'mux'
        if k not in kwargs:
            mux = ToRecv()
            kwargs[k] = mux
        k = 'pipe'
        if k not in kwargs:
            pipe = operators.Apply(fn=self.recvs)
            kwargs[k] = pipe
        super(Recv, self).__init__(*args, **kwargs)

class Send(net.Transition):
    
    @staticmethod
    def sends(inputs, **kwargs):
        sock, buf = [i() for i in inputs]
        try:
            result = buf.send(**kwargs)
        except IOError as e:
            result = e
        return result, sock, buf
    
    def __init__(self, *args, **kwargs):
        k = 'mux'
        if k not in kwargs:
            mux = ToSend()
            kwargs[k] = mux
        k = 'pipe'
        if k not in kwargs:
            pipe = operators.Apply(fn=self.sends)
            kwargs[k] = pipe
        super(Send, self).__init__(*args, **kwargs)


class SocketBufferIO(sockets.Network):
    
    
    bufsize = trellis.attr(sockbuf.MTU)
    
    free = trellis.make(BufferPool)
    sending = trellis.make(BufferQueues)
    received = trellis.make(BufferQueues)
    recv = trellis.make(Recv)
    send = trellis.make(Send)
    
    @trellis.modifier
    def Buffer(self, nbytes=None, *args, **kwargs):
        if nbytes is None:
            nbytes = self.bufsize
        buf = buffer.BufferStream(nbytes, *args, **kwargs)
        buf = sockbuf.SocketBuffer(buf)
        self.free.add(buf)
        return buf

    def __init__(self, *args, **kwargs):
        super(SocketBufferIO, self).__init__(*args, **kwargs)
        for condition in self.free, self.sending, self.received,:
            if condition not in self.conditions:
                self.conditions.add(condition)
        for transition in self.recv, self.send,:
            if transition not in self.transitions:
                self.transitions.add(transition)
                
        #
        # links
        #
        
        transition = self.recv
        inputs = ('polled', self.poll.output,), ('free', self.free,), ('received', self.received,),
        for attr, input in inputs:
            arc = self.Arc()
            net.link(arc, input, transition,)
            setattr(transition.mux, attr, arc)
        outputs = self.sockets, self.received, self.free
        for output in outputs:
            arc = self.Arc()
            net.link(arc, transition, output,)
        
        transition = self.send
        inputs = ('polled', self.poll.output,), ('sending', self.sending,),
        for attr, input in inputs:
            arc = self.Arc()
            net.link(arc, input, transition,)
            setattr(transition.mux, attr, arc)
        outputs = self.sockets, self.sending, self.free
        for output in outputs:
            arc = self.Arc()
            net.link(arc, transition, output,)
    
#############################################################################
#############################################################################

Network = SocketBufferIO

#############################################################################
#############################################################################
