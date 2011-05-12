# @copyright
# @license

r"""

History
-------

- Apr 8, 2011 @lisa: Created

"""


import unittest

from pynet.events.socket import *

#############################################################################
#############################################################################

class TestCaseSocket(unittest.TestCase):
    def test_dgram(self, HOST='127.0.0.1', PORT=9000):
        
        net = SocketPool()
        sock = net.Socket(socket.DATAGRAM)
        self.assertTrue(sock in net.sockets)
        
        sock.bind((HOST, PORT))
        
        net.register()
        self.assertTrue(sock not in net.sockets)
        self.assertTrue(sock in net.poll.input)
        self.assertTrue(net.poll.input[sock] & poll.POLLOUT)
        
        net.poll()
        self.assertTrue(sock not in net.poll.input)
        self.assertTrue(sock in net.poll.output)
        self.assertTrue(net.poll.output[sock] & poll.POLLOUT)

        net.close()
        self.assertTrue(sock not in net.poll.output)
        self.assertTrue(sock.state == sock.CLOSED)
        self.assertTrue(sock in net.sockets)

    def test_stream(self,):
        
        net = SocketPool()
        listener = net.Socket(socket.STREAM)
        self.assertTrue(listener in net.sockets)
        
        listener.listen()
        
        net.register()
        self.assertTrue(listener not in net.sockets)
        self.assertTrue(listener in net.poll.input)
        self.assertTrue(net.poll.input[listener] & poll.POLLIN)
        
        connector = net.Socket(socket.STREAM)
        self.assertTrue(connector in net.sockets)
        
        connector.connect(listener.bound)
        
        net.poll(None)
        self.assertTrue(listener not in net.poll.input)
        self.assertTrue(listener in net.poll.output)
        self.assertTrue(net.poll.output[listener] & poll.POLLIN)
        
        net.accept()
        self.assertTrue(listener not in net.poll.output)
        self.assertTrue(listener in net.sockets)
        self.assertEqual(len(net.sockets), 3)
        
#############################################################################
#############################################################################
