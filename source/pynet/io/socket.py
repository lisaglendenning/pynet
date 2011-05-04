
from __future__ import absolute_import

import socket
import errno
import os
import functools

from pypetri import trellis

#############################################################################
#############################################################################

class Socket(trellis.Component):
    
    NONE = ('0.0.0.0', 0)
    
    DATAGRAM = 'DATAGRAM'
    STREAM = 'STREAM'
    TRANSPORTS = [DATAGRAM, STREAM,]
    
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
    
    socket = trellis.make(None)
    state = trellis.attr(None)
    
    def __init__(self, sock=None, state=None, **options):
        if sock is None:
            family = self.SOCK_FAMILY
            transport = self.SOCK_TRANSPORTS[self.TRANSPORT]
            sock = socket.socket(family, transport)
        for k,v in options:
            level = socket.SOL_SOCKET
            sock.setsockopt(level, k, v)
        if state is None:
            state = self.START
        super(Socket, self).__init__(socket=sock, state=state)
    
    def __hash__(self):
        return hash(self.socket)
    
    def catches(self, f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            try:
                result = f(*args, **kwargs)
            except IOError:
                if self.state != self.ERROR:
                    self.state = self.ERROR
                raise
            else:
                return result
        return wrapper
    
    @trellis.maintain(initially=None)
    def local(self):
        sock = self.socket
        state = self.state
        if sock is not None and state not in (self.START, self.CLOSED, self.ERROR):
            try:
                addr = sock.getsockname()
            except IOError:
                pass
            else:
                return addr
        return None
    
    @trellis.maintain(initially=None)
    def remote(self):
        sock = self.socket
        state = self.state
        if sock is not None and state not in (self.START, self.CLOSED, self.ERROR):
            try:
                addr = sock.getpeername()
            except IOError:
                pass
            else:
                return addr
        return None
    
    @trellis.maintain(initially=None)
    def bind(self):
        if self.state != self.START:
            return None
        f = self.socket.bind
        return self.catches(f)
    
    @trellis.maintain(initially=None)
    def close(self):
        if self.state == self.CLOSED:
            return None
        f = self.socket.close
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            result = self.catches(f)(*args, **kwargs)
            self.state = self.CLOSED
            return result
        return wrapper
    
#############################################################################
#############################################################################
            
class DatagramSocket(Socket):
    
    TRANSPORT = Socket.DATAGRAM

    @trellis.maintain(initially=None)
    def bind(self):
        if self.state != self.START:
            return None
        f = self.socket.bind
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            result = self.catches(f)(*args, **kwargs)
            self.state = self.CONNECTED
            return result
        return wrapper
        
    @trellis.maintain(initially=None)
    def send(self):
        if self.state not in (self.START, self.CONNECTED, self.CLOSING,):
            return None
        f = self.socket.sendto
        def wrapper(*args, **kwargs):
            result = self.catches(f)(*args, **kwargs)
            if self.state == self.START:
                try:
                    addr = self.socket.getsockname()
                except IOError:
                    pass
                else:
                    if addr is not None and addr != self.NONE:
                        self.state = self.CONNECTED
            return result
        return wrapper
    
    @trellis.maintain(initially=None)
    def recv(self):
        if self.state not in (self.CONNECTED, self.CLOSING,):
            return None
        f = self.socket.recvfrom
        return self.catches(f)

    @trellis.maintain(initially=None)
    def recv_into(self):
        if self.state not in (self.CONNECTED, self.CLOSING,):
            return None
        f = self.socket.recvfrom_into
        return self.catches(f)
    
#############################################################################
#############################################################################

class StreamSocket(Socket):
    
    TRANSPORT = Socket.STREAM

    @trellis.maintain(initially=None)
    def listen(self):
        if self.state != self.START:
            return None
        f = self.socket.listen
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if not args and not kwargs:
                kwargs['backlog'] = 1
            result = self.catches(f)(*args, **kwargs)
            self.state = self.LISTENING
            return result
        return wrapper

    @trellis.maintain(initially=None)
    def accept(self):
        if self.state != self.LISTENING:
            return None
        f = self.socket.accept
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            try:
                result = f()
            except socket.error as why:
                if why.args[0] not in (errno.EAGAIN, errno.EWOULDBLOCK,):
                    raise
            else:
                sock = self.__class__(sock=result[0], state=self.CONNECTED)
                return sock, result[1]
            return None
        return wrapper
    
    @trellis.maintain(initially=None)
    def connect(self):
        if self.state != self.START:
            return None
        f = self.socket.connect_ex
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            err = self.catches(f)(*args, **kwargs)
            if err in (0, errno.EISCONN,):
                self.state = self.CONNECTED
            elif err == errno.EINPROGRESS:
                self.state = self.CONNECTING
            else:
                self.state = self.ERROR
                raise socket.error(err, os.strerror(err))
        return wrapper
    
    @trellis.maintain(initially=None)
    def send(self):
        if self.state not in (self.CONNECTING, self.CONNECTED, self.CLOSING,):
            return None
        f = self.socket.send
        def wrapper(*args, **kwargs):
            result = self.catches(f)(*args, **kwargs)
            if self.state == self.CONNECTING:
                try:
                    addr = self.socket.getpeername()
                except IOError:
                    pass
                else:
                    if addr is not None and addr != self.NONE:
                        self.state = self.CONNECTED
            return result
        return wrapper

    @trellis.maintain(initially=None)
    def sendall(self):
        if self.state not in (self.CONNECTING, self.CONNECTED, self.CLOSING,):
            return None
        f = self.socket.sendall
        def wrapper(*args, **kwargs):
            result = self.catches(f)(*args, **kwargs)
            if self.state == self.CONNECTING:
                try:
                    addr = self.socket.getpeername()
                except IOError:
                    pass
                else:
                    if addr is not None and addr != self.NONE:
                        self.state = self.CONNECTED
            return result
        return wrapper

    @trellis.maintain(initially=None)
    def recv(self):
        if self.state not in (self.CONNECTING, self.CONNECTED, self.CLOSING,):
            return None
        f = self.socket.recv
        def wrapper(*args, **kwargs):
            result = self.catches(f)(*args, **kwargs)
            if self.state == self.CONNECTING:
                try:
                    addr = self.socket.getpeername()
                except IOError:
                    pass
                else:
                    if addr is not None and addr != self.NONE:
                        self.state = self.CONNECTED
            return result
        return wrapper

    @trellis.maintain(initially=None)
    def recv_into(self):
        if self.state not in (self.CONNECTING, self.CONNECTED, self.CLOSING,):
            return None
        f = self.socket.recv_into
        def wrapper(*args, **kwargs):
            result = self.catches(f)(*args, **kwargs)
            if self.state == self.CONNECTING:
                try:
                    addr = self.socket.getpeername()
                except IOError:
                    pass
                else:
                    if addr is not None and addr != self.NONE:
                        self.state = self.CONNECTED
            return result
        return wrapper
    
    @trellis.maintain(initially=None)
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
                    self.state = self.ERROR
                    raise
            self.state = self.CLOSING
        return wrapper

#############################################################################
#############################################################################
