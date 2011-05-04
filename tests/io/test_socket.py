# @copyright
# @license

r"""

History
-------

- Apr 26, 2010 @lisa: Created

"""

from __future__ import absolute_import

import unittest

from pynet.io import socket

#############################################################################
#############################################################################

class TestCaseSocket(unittest.TestCase):
    
    def test_dgram(self, NSOCKS=2, HOST='0.0.0.0', PORT=9000):
        timeout = 0.001
        
        socks = [socket.DatagramSocket() for i in xrange(NSOCKS)]
        for i in xrange(NSOCKS):
            sock = socks[i]
            self.assertEqual(sock.state, sock.START)
            sock.bind((HOST, PORT + i))
            self.assertEqual(sock.state, sock.CONNECTED)
            self.assertEqual(sock.local, (HOST, PORT + i))
        
        data = 'hello world!'
        for i in xrange(NSOCKS):
            j = i+1 if i < NSOCKS-1 else 0
            socks[i].socket.settimeout(timeout)
            socks[j].socket.settimeout(None)
            sent = socks[i].send(data, socks[j].local)
            self.assertEqual(len(data), sent)
            recvd = socks[j].recv(sent)
            self.assertEqual(data, recvd[0])

        for i in xrange(NSOCKS):
            sock = socks[i]
            sock.socket.settimeout(None)
            sock.close()
            self.assertEqual(sock.state, sock.CLOSED)
            
    def test_stream(self, NSOCKS=2,):
        timeout = 0.001
        
        listener = socket.StreamSocket()
        listener.socket.settimeout(None)
        self.assertEqual(listener.state, listener.START)
        listener.listen(NSOCKS)
        self.assertEqual(listener.state, listener.LISTENING)
        
        connectors = [socket.StreamSocket() for i in xrange(NSOCKS/2)]
        acceptors = []
        for sock in connectors:
            sock.socket.settimeout(timeout)
            self.assertEqual(sock.state, sock.START)
            sock.connect(listener.local)
            self.assertTrue(sock.state in (sock.CONNECTING, sock.CONNECTED,))
            result = listener.accept()
            self.assertTrue(result)
            acceptor, addr = result
            self.assertEqual(addr, sock.local)
            self.assertTrue(acceptor.state in (sock.CONNECTING, sock.CONNECTED,))
            acceptors.append(acceptor)
        
        data = 'hello world!'
        for sender, recver in zip(connectors, acceptors):
            sender.socket.settimeout(timeout)
            recver.socket.settimeout(None)
            sender.sendall(data)
            self.assertEqual(sender.state, sender.CONNECTED)
            recvd = recver.recv(len(data))
            self.assertEqual(data, recvd)
            self.assertEqual(recver.state, recver.CONNECTED)

        for connector, acceptor in zip(connectors, acceptors):
            for sock in acceptor, connector:
                sock.socket.settimeout(timeout)
                sock.shutdown()
                self.assertTrue(sock.state in (recver.CLOSING, recver.CLOSED,))

        for connector, acceptor in zip(connectors, acceptors):
            for sock in acceptor, connector:
                sock.socket.settimeout(None)
                sock.close()
                self.assertEqual(sock.state, recver.CLOSED)
            
#############################################################################
#############################################################################
