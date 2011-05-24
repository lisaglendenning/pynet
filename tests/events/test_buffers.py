# @copyright
# @license

r"""

History
-------

- May 21, 2011 @lisa: Created

"""


import unittest

from pynet.events.buffers import *

#############################################################################
#############################################################################

class Message(object):
    
    def __init__(self, data):
        self.data = data
        self.buffer = None
    
    def read(self, buf):
        data = buf[:]
        self.buffer = data
        return len(data)
    
    def write(self, buf):
        data = self.data
        buf[:] = data
        return len(data)

class TestCaseSockets(unittest.TestCase):
    
    Network = Network
    
    def test_dgram(self, HOST='127.0.0.1', PORT=9000):
        
        net = self.Network()
        
        #
        # connect
        #
        
        socks = [net.Socket(socket.DATAGRAM) for i in xrange(2)]
        receiver, sender = socks
        for i,sock in enumerate(socks):
            sock.socket.settimeout(None)
            sock.bind((HOST, PORT+i))

        #
        # write
        #

        buf = net.Buffer()
        self.assertTrue(buf in net.free)
        
        data = 'hi'
        msg = Message('hi')
        buf.write(msg.write, (sender, receiver.bound), len(data))
        self.assertEqual(net.free.marking.pop(), buf)
        net.sending.add(buf)
        self.assertTrue(sender in net.sending)

        #
        # send
        #

        for i in xrange(2):
            if sender in net.poll.input:
                break
            net.register()
            
        for i in xrange(2):
            if sender in net.poll.output:
                break
            net.poll()

        net.send()
        self.assertTrue(buf in net.free)
        self.assertTrue(sender in net.sockets)

        #
        # receive
        #
        
        for i in xrange(2):
            if receiver in net.poll.input:
                break
            net.register()
        for i in xrange(2):
            if receiver in net.poll.output:
                break
            net.poll()
        
        net.recv()
        self.assertEqual(len(buf.buffer), len(data))
        self.assertTrue(receiver in net.sockets)
        self.assertTrue(receiver in net.receiving)
        
        #
        # read
        #
        
        self.assertEqual(net.receiving.pop(receiver), buf)
        result = buf.read(msg.read)
        self.assertEqual(msg.buffer, data)
        self.assertTrue(isinstance(result, sockbuf.BufferDescriptor))
        self.assertEqual(result.nbytes, 2)
        self.assertEqual(result.who, (receiver, sender.bound))
        net.free.add(buf)
        
        # it should only take up to N events to close all sockets
        for i in xrange(len(socks)):
            try:
                net.close()
            except StopIteration:
                break

    def test_stream(self,):
        
        net = self.Network()
        
        #
        # listen
        #
        
        listener = net.Socket(socket.STREAM)
        listener.listen()
        net.register()
        
        #
        #  connect
        #
        
        connector = net.Socket(socket.STREAM)
        connector.connect(listener.bound)
        
        #
        # accept
        #

        net.poll()
        net.accept()
        for acceptor in net.sockets:
            if acceptor not in (listener, connector,):
                break
        else:
            self.fail(net.sockets)
        
        #
        # write
        #

        buf = net.Buffer()
        self.assertTrue(buf in net.free)
        
        data = 'hi'
        msg = Message('hi')
        buf.write(msg.write, acceptor, len(data))
        self.assertEqual(net.free.marking.pop(), buf)
        net.sending.add(buf)
        self.assertTrue(acceptor in net.sending)

        #
        # send
        #

        for i in xrange(3):
            if acceptor in net.poll.input:
                break
            net.register()
            
        for i in xrange(3):
            if acceptor in net.poll.output:
                break
            net.poll()

        net.send()
        self.assertTrue(buf in net.free)
        self.assertTrue(acceptor in net.sockets)
        
        #
        # receive
        #
        
        for i in xrange(3):
            if connector in net.poll.input:
                break
            net.register()
        for i in xrange(3):
            if connector in net.poll.output:
                break
            net.poll()
        
        net.recv()
        self.assertEqual(len(buf.buffer), len(data))
        self.assertTrue(connector in net.sockets)
        self.assertTrue(connector in net.receiving)
        
        #
        # read
        #
        
        self.assertEqual(net.receiving.pop(connector), buf)
        result = buf.read(msg.read)
        self.assertEqual(msg.buffer, data)
        self.assertTrue(isinstance(result, sockbuf.BufferDescriptor))
        self.assertEqual(result.nbytes, 2)
        self.assertEqual(result.who, connector)
        net.free.add(buf)
        
        # it should only take up to N events to close all sockets
        for i in xrange(3):
            try:
                net.close()
            except StopIteration:
                break
        
#############################################################################
#############################################################################
