# @copyright
# @license

r"""

History
-------

- Apr 8, 2011 @lisa: Created

"""


import unittest

from pynet.events.sockets import *

#############################################################################
#############################################################################

class TestCaseSockets(unittest.TestCase):
    
    Network = SocketIO
    
    def test_dgram(self, HOST='127.0.0.1', PORT=9000):
        
        net = self.Network()
        sock = net.Socket(socket.DATAGRAM)
        self.assertTrue(sock in net.sockets)
        
        sock.bind((HOST, PORT))
        
        net.register()
        self.assertTrue(sock not in net.sockets)
        self.assertTrue(sock in net.poll.input)
        self.assertTrue(net.poll.input[sock] & polls.POLLOUT)
        
        net.poll()
        self.assertTrue(sock not in net.poll.input)
        self.assertTrue(sock in net.poll.output)
        self.assertTrue(net.poll.output[sock] & polls.POLLOUT)

        net.close()
        self.assertTrue(sock not in net.poll.output)
        self.assertTrue(sock in net.sockets)
        self.assertEqual(sock.state, sock.CLOSED)

    def test_stream(self,):
        
        net = self.Network()
        listener = net.Socket(socket.STREAM)
        self.assertTrue(listener in net.sockets)
        
        listener.listen()
        
        net.register()
        self.assertTrue(listener not in net.sockets)
        self.assertTrue(listener in net.poll.input)
        self.assertTrue(net.poll.input[listener] & polls.POLLIN)
        
        connector = net.Socket(socket.STREAM)
        self.assertTrue(connector in net.sockets)
        
        connector.connect(listener.bound)
        
        for i in net.close.inputs:
            print "IN", i.input
        for o in net.close.outputs:
            print "OUT", o.output
        net.poll(None)
        self.assertTrue(listener not in net.poll.input)
        self.assertTrue(listener in net.poll.output)
        self.assertTrue(net.poll.output[listener] & polls.POLLIN)

        net.accept()
        self.assertTrue(listener not in net.poll.output)
        self.assertTrue(listener in net.sockets)
        self.assertEqual(len(net.sockets), 3)
        
        # it should only take up to N events to close all sockets
        for i in xrange(len(net.sockets)):
            try:
                net.close()
            except RuntimeError:
                break
        
        self.assertEqual(len(net.sockets), 3)
        for sock in net.sockets:
            self.assertEqual(sock.state, sock.CLOSED)
        
#############################################################################
#############################################################################