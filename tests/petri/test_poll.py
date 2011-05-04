# @copyright
# @license

r"""

History
-------

- Apr 8, 2011 @lisa: Created

"""


import unittest
import socket

import pynet.io.poll
import pynet.petri.poll

#############################################################################
#############################################################################

class TestCasePoll(unittest.TestCase):
    def test_dgram(self, HOST='127.0.0.1', PORT=9000):
        
        net = pynet.petri.poll.Network()
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((HOST, PORT))
        
        net.input[sock] = pynet.io.poll.POLLOUT
        events = [e for e in net.polling.next()]
        self.assertEqual(len(events), 1)
        self.assertTrue(net.poll is not None)
        
        self.assertFalse(net.output)
        output = net.poll()
        self.assertTrue(net.output)
        self.assertTrue(sock in net.output)
        self.assertTrue(net.output[sock] & pynet.io.poll.POLLOUT)
        self.assertEqual(dict(net.output), dict(output))
        
#############################################################################
#############################################################################
