# @copyright
# @license

r"""

History
-------

- May 21, 2011 @lisa: Created

"""


import unittest

import collections

from pynet.events.buffered import *

#############################################################################
#############################################################################

class Message(object):
    
    def __init__(self,):
        self.reading = None
    
    def read(self, who=None, nbytes=None):
        def reader(who=None, nbytes=None):
            next = Demand(who, nbytes)
            while True:
                buf = yield next
                reading = buf[:]
                self.reading = reading
                desc = yield len(reading)
        r = reader(who, nbytes)
        return r
    
    def write(self, writing, who=None):
        def writer(writing, who=None):
            nbytes = len(writing)
            next = Demand(who, nbytes)
            while True:
                buf = yield next
                buf[:] = writing
                desc = yield nbytes
        w = writer(writing, who)
        return w

class TestCaseSockets(unittest.TestCase):
    
    Network = Network
    
    @staticmethod
    def select(k):
        def fn(m):
            if isinstance(m, collections.Mapping):
                if k in m:
                    yield (k, m[k])
            elif isinstance(m, tuple) and len(m) == 2:
                if k is m[0]:
                    yield m
            else:
                output = [x for x in m if (isinstance(x, tuple) and k is x[0]) or (k is x)]
                if output:
                    if len(output) == 1:
                        output = output[0]
                    yield output
        return fn
    
    def test_dgram(self, NSOCKS=2, PORT=9000):
        
        net = self.Network()
        
        buf = net.Buffer()
        self.assertTrue(buf in net.free)
        
        data = 'hi'

        #
        # connect
        #
        
        socks = [net.Socket(socket.DATAGRAM) for i in xrange(NSOCKS)]
        for i,sock in enumerate(socks):
            sock.socket.settimeout(None)
            sock.bind(sock.Address(port=PORT+i))
                
        for i in xrange(0, NSOCKS, 2):
            
            receiver, sender = socks[i:i+2]
            
            # write
            connection = sockbuf.Connection(sender, receiver.bound)
            buf = net.free.pull(buf)
            nbytes = len(data)
            def writer(buf):
                buf[:nbytes] = data
                return nbytes
            buf.write(writer, connection, nbytes)
            net.sending.send((sender, buf))
            self.assertTrue(sender in net.sending)

            self.sendrecv(net, sender, receiver)
            
            # read
            self.assertTrue(receiver in net.receiving)
            buf = net.receiving.pull(receiver)[1]
            def reader(buf):
                self.assertEqual(buf[:nbytes], data)
                return nbytes
            buf.read(reader, nbytes)
            net.free.send(buf)
        
        # it should only take up to N events to close all sockets
        for i in xrange(len(socks)):
            try:
                net.close()
            except StopIteration:
                break
                
    def test_stream(self, NSOCKS=2):
        
        net = self.Network()
        
        buf = net.Buffer()
        self.assertTrue(buf in net.free)
        
        data = 'hi'

        # listen
        listener = net.Socket(socket.STREAM)
        listener.listen()

        seen = set()
        seen.add(listener)
        for i in xrange(0, NSOCKS, 2):

            if listener not in net.poll.input:
                select = self.select(listener)
                net.register(select=select)
            
            connector = net.Socket(socket.STREAM)
            seen.add(connector)
            connector.connect(listener.bound)
            
            net.poll()
            net.accept()
            new = set(net.sockets) - seen
            self.assertEquals(len(new), 1)
            acceptor = new.pop()
            seen.add(acceptor)
            
            #
            # callbacks
            #

            # write
            connection = acceptor
            buf = net.free.pull(buf)
            nbytes = len(data)
            def writer(buf):
                buf[:nbytes] = data
                return nbytes
            buf.write(writer, connection, nbytes)
            net.sending.send((connection, buf))
            self.assertTrue(connection in net.sending)
            
            self.sendrecv(net, acceptor, connector)
            
            # read
            connection = connector
            self.assertTrue(connection in net.receiving)
            buf = net.receiving.pull(connection)[1]
            def reader(buf):
                self.assertEqual(buf[:nbytes], data)
                return nbytes
            buf.read(reader, nbytes)
            net.free.send(buf)
        
        # it should only take up to N events to close all sockets
        for i in xrange(NSOCKS):
            try:
                net.close()
            except StopIteration:
                break

    def sendrecv(self, net, sender, receiver,):

        # send

        select = self.select(sender)
        if sender not in net.poll.input:
            net.register(select=select)
        net.poll(select=select)
        net.send(select=select)

        # receive

        select = self.select(receiver)
        if receiver not in net.poll.input:
            net.register(select=select)
        net.poll(select=select)
        net.recv(select=select)
        
#############################################################################
#############################################################################
