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
            return self.Event(self.pop)

class BufferQueue(mapping.Mapping):
    
    fn = trellis.attr(lambda x: isinstance(x, sockbuf.SocketBuffer) and len(x.log) > 0)

    @trellis.modifier
    def add(self, item,):
        k = item.log[0].who
        if k not in self.marking:
            self.marking[k] = collections.deque()
        self.marking[k].append(item)
        
    @trellis.modifier
    def send(self, *args):
        filter = self.fn
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

#############################################################################
#############################################################################

class ToSend(operators.Multiplexer):

    sending = trellis.attr(None)
    polled = trellis.attr(None)

    def next(self, iterator=None, *args, **kwargs):
        # Input events
        itr = self.pollout.next(*args, **kwargs)
        try:
            polled = itr.next()
        except StopIteration:
            return
        itr = self.outq.next(*args, **kwargs)
        try:
            outq = itr.next()
        except StopIteration:
            return
        
        # filter sockets that are writable and have something to write
        events = polled.keywords['items']
        qs = outq.keywords['items']
        if iterator is None:
            iterator = qs
        else:
            iterator = iterator(qs)
        for sock in itertools.ifilter(lambda x: x in events and events[x] & polls.POLLOUT, 
                                      iterator):
            if sock not in qs or not qs[sock]:
                continue
            inputs = (polled.__class__(polled.func, item=sock),
                      outq.__class__(outq.func, item=sock),)
            yield inputs


class ToRecv(operators.Multiplexer):

    free = trellis.attr(None)
    received = trellis.attr(None)
    polled = trellis.attr(None)

    def next(self, iterator=None, *args, **kwargs):
        # Input events
        itr = self.pollout.next(*args, **kwargs)
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
    def recv(inputs, **kwargs):
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
            pipe = operators.Apply(fn=self.recv)
            kwargs[k] = pipe
        super(Recv, self).__init__(*args, **kwargs)

class Send(net.Transition):
    
    @staticmethod
    def send(inputs, **kwargs):
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
            pipe = operators.Apply(fn=self.send)
            kwargs[k] = pipe
        super(Send, self).__init__(*args, **kwargs)


class SocketBufferIO(sockets.Network):
    
    
    bufsize = trellis.attr(sockbuf.MTU)
    
    free = trellis.make(BufferPool)
    sending = trellis.make(BufferQueue)
    received = trellis.make(BufferQueue)
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
            setattr(transition, attr, arc)
        outputs = self.sockets, self.received, self.free
        for output in outputs:
            arc = self.Arc()
            net.link(arc, transition, output,)
        
        transition = self.send
        inputs = ('polled', self.poll.output,), ('sending', self.sending,),
        for attr, input in inputs:
            arc = self.Arc()
            net.link(arc, input, transition,)
            setattr(transition, attr, arc)
        outputs = self.sockets, self.sending, self.free
        for output in outputs:
            arc = self.Arc()
            net.link(arc, transition, output,)
    
#############################################################################
#############################################################################

Network = SocketBufferIO

#############################################################################
#############################################################################
