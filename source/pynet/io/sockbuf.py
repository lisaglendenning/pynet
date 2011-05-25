# @copyright
# @license

from __future__ import absolute_import

import collections


#############################################################################
#############################################################################

MTU = 2**16 # TODO

#############################################################################
#############################################################################

Connection = collections.namedtuple('Connection', ('local', 'remote',),)
BufferDescriptor = collections.namedtuple('BufferDescriptor', ('nbytes', 'connection',),)

#############################################################################
#############################################################################

class SocketBuffer(collections.namedtuple('SocketBuffer', ('buffer', 'log',),)):
    __slots__ = ()
    
    @staticmethod
    def reader(sock, *args, **kwargs):
        def coroutine(sock, flags=0):
            buf = yield
            result = sock.recv_into(buf, flags)
            if isinstance(result, tuple):
                for x in result:
                    yield x
            else:
                yield result
        reader = coroutine(sock, *args, **kwargs)
        reader.next()
        return reader
    
    @staticmethod
    def writer(sock, *args, **kwargs):
        def coroutine(sock, address=None, flags=0):
            buf = yield
            if address is None:
                args = (buf, flags,)
            else:
                args = (buf, flags, address,)
            nbytes = sock.send(*args)
            yield nbytes
        writer = coroutine(sock, *args, **kwargs)
        writer.next()
        return writer

    def __new__(cls, buffer, log=None):
        if log is None:
            log = collections.deque()
        return super(SocketBuffer, cls).__new__(cls, buffer, log)
    
    def __hash__(self):
        return hash(self.buffer)
    
    def __eq__(self, other):
        return self.buffer is other.buffer
    
    def append(self, desc):
        if not isinstance(desc, BufferDescriptor):
            raise TypeError(desc)
        if desc.nbytes < 0:
            raise ValueError(desc)
        # combine adjacent entries with the same connection
        if self.log:
            last = self.log[-1]
            if last.connection == desc.connection:
                self.log[-1] = last._replace(nbytes=(last.nbytes + desc.nbytes))
                return
        self.log.append(desc)
    
    def read(self, reader, nbytes=None):
        log = self.log
        if log:
            first = self.log[0]
        else:
            first = None
        if nbytes is not None and first is not None:
            if nbytes > first.nbytes:
                nbytes = first.nbytes
        nbytes = self.buffer.read(reader, nbytes)
        if first is not None:
            if nbytes == first.nbytes:
                return log.popleft()
            else:
                assert nbytes < first.nbytes
                log[0] = first._replace(nbytes=(first.nbytes-nbytes))
            return first._replace(nbytes=nbytes)
        else:
            return nbytes
    
    def write(self, writer, who=None, nbytes=None,):
        nbytes = self.buffer.write(writer, nbytes)
        desc = BufferDescriptor(nbytes, who)
        self.append(desc)
        return desc
    
    def recv(self, connection, nbytes=None, **kwargs):
        coroutine = self.reader(connection, **kwargs)
        nbytes = self.buffer.write(coroutine.send, nbytes)
        try:
            addr = coroutine.next()
        except StopIteration:
            pass
        else:
            connection = Connection(connection, addr)
        desc = BufferDescriptor(nbytes, connection)
        self.append(desc)
        return desc
    
    def send(self, connection=None, nbytes=None, **kwargs):
        log = self.log
        if log:
            first = log[0]
        else:
            first = None
        if connection is None:
            if first is None or first.connection is None:
                raise ValueError(connection)
            connection = first.connection
        else: # sanity check?
            if first is not None\
             and first.connection is not None \
             and connection != first.connection:
                raise ValueError(connection)
        if nbytes is None:
            if first is not None:
                nbytes = first.nbytes
        else:
            if first is not None and nbytes > first.nbytes:
                nbytes = first.nbytes
        if isinstance(connection, Connection):
            connection, addr = connection
            kwargs['address'] = addr
        coroutine = self.writer(connection, **kwargs)
        nbytes = self.buffer.read(coroutine.send, nbytes)
        if first is not None:
            if nbytes == first.nbytes:
                return self.log.popleft()
            else:
                assert nbytes < first.nbytes
                log[0] = first._replace(nbytes=(first.nbytes - nbytes))
                return first._replace(nbytes=nbytes)
        else:
            return nbytes

#############################################################################
#############################################################################
