# @copyright
# @license

r"""Buffered abstraction for a socket.

History
-------

- Aug 24, 2010 @lisa: Created

"""

##############################################################################
##############################################################################

import functools
import collections

import pynet.io.buffer

##############################################################################
##############################################################################

class StreamSocketBuffer(object):

    BUFSIZE = 4096 # better value??
    
    def __init__(self, sock, bufsize=None):
        self.sock = sock
        bufsize = self.BUFSIZE if bufsize is None else bufsize
        self.buffer = pynet.io.buffer.BufferStream(bufsize)
        
    local = property(lambda self: self.sock.getsockname())
    remote = property(lambda self: self.sock.getpeername())

    def send(self, nbytes=None):
        sent = self.buffer.read(self._sock_send, nbytes)
        return sent
            
    def recv(self, nbytes=None):
        if nbytes is None:
            nbytes = self.BUFSIZE
        recvd = self.buffer.write(self._sock_recv, nbytes)
        return recvd

    def _sock_send(self, buf):
        return self.sock.send(buf)
    
    def _sock_recv(self, buf):
        recvd = self.sock.recv_into(buf, len(buf))
        return recvd
    

##############################################################################
##############################################################################

def checked_headers(f):
    
    def check(self):
        buffer = self.buffer
        headers = self.headers
        if len(buffer):
            assert len(headers)
        else:
            assert not len(headers)
    
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        check(self)
        v = f(self, *args, **kwargs)
        check(self)
        return v
    return wrapper

##############################################################################
##############################################################################

class DatagramSocket(StreamSocketBuffer):

    BUFSIZE = 2**16  # should be ~ the maximum datagram size
    
    def __init__(self, *args, **kwargs):
        StreamSocketBuffer.__init__(self, *args, **kwargs)
        self.headers = collections.deque()
    
    @checked_headers
    def _sock_recv(self, buf):
        recvd = self.sock.recvfrom_into(buf, len(buf))
        if recvd is not None and recvd[0] > 0:
            self.headers.append(recvd)
            recvd = recvd[0]
        else: 
            # Not sure if zero or None is a valid return value?
            recvd = 0
        return recvd
    
    @checked_headers
    def _sock_send(self, buf):
        len, addr = self.headers[0]
        sent = self.sock.sendto(buf, addr)
        left = len - sent
        self.headers.popleft()
        if left > 0:
            self.headers.appendleft((left, addr))
        else:
            assert left == 0
        return sent

    def send(self, nbytes=None):
        len = self.headers[0][0]
        assert len > 0
        if nbytes is None:
            nbytes = len
        else:
            nbytes = min(len, nbytes)
        sent = StreamSocketBuffer.send(self, nbytes)
        return sent

##############################################################################
##############################################################################
