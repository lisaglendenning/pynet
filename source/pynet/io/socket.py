
from __future__ import absolute_import

import socket
import errno
import os
import functools
import weakref

from peak.events import trellis

#############################################################################
#############################################################################

DATAGRAM = 'DATAGRAM'
STREAM = 'STREAM'
TRANSPORTS = [DATAGRAM, STREAM,]

#############################################################################
#############################################################################

class Socket(trellis.Component):
    """Wraps a socket with a simple state machine."""
    
    NONE = ('0.0.0.0', 0)
    
    SOCK_FAMILY = socket.AF_INET
    SOCK_TRANSPORTS = { DATAGRAM: socket.SOCK_DGRAM, 
                        STREAM: socket.SOCK_STREAM,
                       }
    
    START = 'START'
    CONNECTING = 'CONNECTING'
    CONNECTED = 'CONNECTED'
    LISTENING = 'LISTENING'
    CLOSING = 'CLOSING'
    CLOSED = 'CLOSED'
    ERROR = 'ERROR'
    STATES = [START, CONNECTING, CONNECTED, LISTENING, CLOSING, CLOSED, ERROR,]
    
    # Subclass factory
    Factory = weakref.WeakValueDictionary()
    
    transport = trellis.make(None)
    socket = trellis.make(socket.socket)
    next = trellis.attr(resetting_to=None)
    error = trellis.attr(None)
    
    # for peak.util.decorators.classy
    def __class_new__(meta, name, bases, cdict, supr):
        cls = supr()(meta, name, bases, cdict, supr)
        if hasattr(cls, 'TRANSPORT',):
            transport = getattr(cls, 'TRANSPORT',)
            Socket.Factory[transport] = cls
        return cls
    
    @classmethod
    def new(cls, transport, *args, **kwargs):
        return cls.Factory[transport](*args, **kwargs)

    def __init__(self, sock=None, state=None, **kwargs):
        if sock is None:
            if 'transport' not in kwargs:
                kwargs['transport'] = self.TRANSPORT
            transport = kwargs['transport']
            transport = self.SOCK_TRANSPORTS[transport]
            family = self.SOCK_FAMILY
            sock = socket.socket(family, transport)
        else:
            if 'transport' not in kwargs:
                for k,v in self.SOCK_TRANSPORTS.iteritems():
                    if v == sock.type:
                        kwargs['transport'] = k
                        break
        if state is None:
            state = self.START
        super(Socket, self).__init__(socket=sock, state=state, **kwargs)
    
    @trellis.maintain
    def state(self):
        prev = self.state
        next = self.next
        if next is not None and next != prev:
            return next
        return prev
    
    @trellis.compute
    def __hash__(self):
        return self.socket.__hash__
    
    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.socket == other.socket
    
    @trellis.compute
    def fileno(self):
        return self.socket.fileno
    
    def performs(self, f):
        @functools.wraps(f)
        @trellis.modifier
        def wrapper(*args, **kwargs):
            try:
                result = f(*args, **kwargs)
            except IOError as e:
                if self.state != self.ERROR:
                    self.next = self.ERROR
                self.error = e
                raise
            else:
                return result
        return wrapper
    
    def _bound(self,):
        try:
            return self.socket.getsockname()
        except IOError:
            return None
        
    @trellis.compute
    def bound(self):
        if self.state not in (self.START, self.CLOSED, self.ERROR,):
            return self._bound()
        return None
    
    @trellis.compute
    def bind(self):
        if self.state != self.START:
            return None
        f = self.socket.bind
        performs = self.performs(f)
        @functools.wraps(f)
        @trellis.modifier
        def wrapper(*args, **kwargs):
            result = performs(*args, **kwargs)
            if self.next is None:
                self.next = self.CONNECTING
            return result
        return wrapper
    
    @trellis.compute
    def close(self):
        if self.state == self.CLOSED:
            return None
        f = self.socket.close
        performs = self.performs(f)
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            result = performs(*args, **kwargs)
            if self.next is None:
                self.next = self.CLOSED
            return result
        return wrapper
    
#############################################################################
#############################################################################
            
class DatagramSocket(Socket):
    
    TRANSPORT = DATAGRAM
    
    @trellis.compute
    def performs(self,):
        outer = super(DatagramSocket, self).performs
        if self.state in (self.START, self.CONNECTING,):
            def wrapper(f):
                @functools.wraps(f)
                @trellis.modifier
                def inner(*args, **kwargs):
                    result = f(*args, **kwargs)
                    if self._bound() is not None:
                        if self.next is None:
                            self.next = self.CONNECTED
                    return result
                return outer(inner)
            return wrapper
        else:
            return outer
        
    @trellis.compute
    def send(self):
        if self.state not in (self.START, self.CONNECTED, self.CLOSING,):
            return None
        f = self.socket.sendto
        return self.performs(f)
    
    @trellis.compute
    def recv(self):
        if self.state not in (self.CONNECTED, self.CLOSING,):
            return None
        f = self.socket.recvfrom
        return self.performs(f)

    @trellis.compute
    def recv_into(self):
        if self.state not in (self.CONNECTED, self.CLOSING,):
            return None
        f = self.socket.recvfrom_into
        return self.performs(f)
    
#############################################################################
#############################################################################

class StreamSocket(Socket):
    
    TRANSPORT = STREAM

    @trellis.compute
    def performs(self,):
        outer = super(StreamSocket, self).performs
        if self.state in (self.CONNECTING,):
            def wrapper(f):
                @functools.wraps(f)
                def inner(*args, **kwargs):
                    result = f(*args, **kwargs)
                    if self._connected() is not None:
                        if self.next is None:
                            self.next = self.CONNECTED
                    return result
                return outer(inner)
            return wrapper
        else:
            return outer
        
    def _connected(self):
        try:
            return self.socket.getpeername()
        except IOError:
            return None
    
    @trellis.compute
    def connected(self):
        if self.state not in (self.START, self.CLOSED, self.ERROR,):
            return self._connected()
        return None
    
    @trellis.compute
    def listen(self):
        if self.state != self.START:
            return None
        f = self.socket.listen
        performs = self.performs(f)
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if not args:
                args = (1,)
            result = performs(*args, **kwargs)
            if self.next is None:
                self.next = self.LISTENING
            return result
        return wrapper

    @trellis.compute
    def accept(self):
        if self.state != self.LISTENING:
            return None
        f = self.socket.accept
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            try:
                result = f(*args, **kwargs)
            except socket.error as why:
                if why.args[0] not in (errno.EAGAIN, errno.EWOULDBLOCK,):
                    raise
            else:
                sock = self.__class__(sock=result[0], state=self.CONNECTED)
                return sock, result[1]
            return None
        return self.performs(wrapper)
    
    @trellis.compute
    def connect(self):
        if self.state != self.START:
            return None
        f = self.socket.connect_ex
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            err = f(*args, **kwargs)
            if err in (0, errno.EISCONN,):
                if not self.next:
                    self.next = self.CONNECTED
            elif err == errno.EINPROGRESS:
                if not self.next:
                    self.next = self.CONNECTING
            else:
                raise socket.error(err, os.strerror(err))
        return self.performs(wrapper)
    
    @trellis.compute
    def send(self):
        if self.state not in (self.CONNECTING, self.CONNECTED, self.CLOSING,):
            return None
        f = self.socket.send
        return self.performs(f)

    @trellis.compute
    def sendall(self):
        if self.state not in (self.CONNECTING, self.CONNECTED, self.CLOSING,):
            return None
        f = self.socket.sendall
        return self.performs(f)

    @trellis.compute
    def recv(self):
        if self.state not in (self.CONNECTING, self.CONNECTED, self.CLOSING,):
            return None
        f = self.socket.recv
        return self.performs(f)

    @trellis.compute
    def recv_into(self):
        if self.state not in (self.CONNECTING, self.CONNECTED, self.CLOSING,):
            return None
        f = self.socket.recv_into
        return self.performs(f)
    
    @trellis.compute
    def shutdown(self):
        if self.state in (self.CLOSED, self.CLOSING, self.ERROR):
            return None
        f = self.socket.shutdown
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if not args:
                args = (socket.SHUT_RDWR,)
            try:
                f(*args, **kwargs)
            except socket.error as e:
                if e.errno != errno.ENOTCONN:
                    raise
            self.next = self.CLOSING
        return self.performs(wrapper)

#############################################################################
#############################################################################
