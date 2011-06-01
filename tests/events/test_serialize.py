# @copyright
# @license

r"""

History
-------

- May 21, 2011 @lisa: Created

"""


import unittest

import collections

from pynet.events.serialize import *

#############################################################################
#############################################################################


class TestCaseSerializing(unittest.TestCase):
    
    @classmethod
    def Network(cls):
        return Serializing(serializer=cls.write, deserializer=cls.read)
    
    @classmethod
    def read(cls):
        def reader():
            item = next = None
            while True:
                buf = yield next
                item = buf[:]
                yield len(item)
                next = item, None
        r = reader()
        return r
    
    @classmethod
    def write(cls):
        def writer():
            nbytes = None
            while True:
                obj = yield None
                nbytes = len(obj)
                buf = yield nbytes
                buf[:] = obj
                yield nbytes
        w = writer()
        w.next()
        return w
    
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
        
        #
        # connect
        #
        
        socks = [net.io.Socket(socket.DATAGRAM) for i in xrange(NSOCKS)]
        for i,sock in enumerate(socks):
            sock.socket.settimeout(None)
            sock.bind(sock.Address(port=PORT+i))
               
        buf = net.io.Buffer()
        
        data = 'hi'
 
        for i in xrange(0, NSOCKS, 2):
            
            receiver, sender = socks[i:i+2]
            
            #
            # callbacks
            #
            
            connection = sockbuf.Connection(sender, receiver.bound)
            msg = Message(connection, data)
            net.input.send((connection, msg))
            
            self.writeread(net, sender, receiver)
            
            connection = sockbuf.Connection(receiver, sender.bound)
            print connection, net.output.items()
            self.assertTrue(connection in net.output)
            msg = net.output.pull(connection)[1]
            self.assertEqual(msg.payload, data)
        
        # it should only take up to N events to close all sockets
        for i in xrange(len(socks)):
            try:
                net.io.close()
            except StopIteration:
                break
                
    def test_stream(self, NSOCKS=2):
        
        net = self.Network()
        

        # listen
        listener = net.io.Socket(socket.STREAM)
        listener.listen()

        seen = set()
        seen.add(listener)
        
        buf = net.io.Buffer()
        
        data = 'hi'
        
        for i in xrange(0, NSOCKS, 2):

            if listener not in net.io.poll.input:
                select = self.select(listener)
                net.io.register(select=select)
            
            connector = net.io.Socket(socket.STREAM)
            seen.add(connector)
            connector.connect(listener.bound)
            
            net.io.poll()
            net.io.accept()
            new = set(net.io.sockets) - seen
            self.assertEquals(len(new), 1)
            acceptor = new.pop()
            seen.add(acceptor)
            
            #
            # callbacks
            #

            connection = acceptor
            msg = Message(connection, data)
            net.input.send((connection, msg))
            
            self.writeread(net, acceptor, connector)
            
            connection = connector
            self.assertTrue(connection in net.output)
            msg = net.output.pull(connection)[1]
            self.assertEqual(msg.payload, data)
        
        # it should only take up to N events to close all sockets
        for i in xrange(NSOCKS):
            try:
                net.io.close()
            except StopIteration:
                break
    
    def writeread(self, net, sender, receiver,):

        # write
        
        if sender.transport == socket.DATAGRAM:
            connection = sockbuf.Connection(sender, receiver.bound)
        else:
            connection = sender
        select = self.select(connection)
        if connection not in net.writing:
            net.write(select=select)
            self.assertTrue(connection in net.writing)
        net.write(select=select)
        self.assertTrue(sender in net.io.sending)
        
        self.sendrecv(net.io, sender, receiver)
        
        # read

        if sender.transport == socket.DATAGRAM:
            connection = sockbuf.Connection(receiver, sender.bound)
        else:
            connection = receiver
        select = self.select(receiver)
        self.assertTrue(receiver in net.io.receiving)
        if connection not in net.reading:
            net.read(select=select)
            self.assertTrue(connection in net.reading)
        net.read(select=select)
        
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
