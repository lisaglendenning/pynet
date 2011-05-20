# @copyright
# @license

from __future__ import absolute_import

import collections


#############################################################################
#############################################################################

MTU = 2**16 # TODO

#############################################################################
#############################################################################

BufferDescriptor = collections.namedtuple('BufferDescriptor', ('nbytes', 'who',),)

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
            result = sock.send(*args)
            if isinstance(result, tuple):
                for x in result:
                    yield x
            else:
                yield result
        writer = coroutine(sock, *args, **kwargs)
        writer.next()
        return writer

    def __new__(cls, buffer, log=None):
        if log is None:
            log = collections.deque()
        super(SocketBuffer, cls).__new__(cls, buffer, log)
    
    def append(self, desc):
        # combine adjacent entries with the same who
        if self.log:
            last = self.log[-1]
            if last.who == desc.who:
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
    
    def recv(self, who, nbytes=None, **kwargs):
        coroutine = self.reader(who, **kwargs)
        nbytes = self.buffer.write(coroutine.send, nbytes)
        try:
            addr = coroutine.next()
        except StopIteration:
            pass
        else:
            who = (who, addr)
        desc = BufferDescriptor(nbytes, who)
        self.append(desc)
        return desc
    
    def send(self, who=None, nbytes=None, **kwargs):
        log = self.log
        if log:
            first = log[0]
        else:
            first = None
        if who is None:
            if first is None or first.who is None:
                raise ValueError(who)
            who = first.who
        else: # sanity check?
            if first is not None and first.who is not None and who != first.who:
                raise ValueError(who)
        if nbytes is None:
            if first is not None:
                nbytes = first.nbytes
        else:
            if first is not None and nbytes > first.nbytes:
                nbytes = first.nbytes
        if isinstance(who, tuple):
            who, addr = who
            kwargs['address'] = addr
        coroutine = self.writer(who, **kwargs)
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
