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
        
        net = pynet.petri.poll.PollChain.create()
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((HOST, PORT))
        
        net.input.registry[sock] = pynet.io.poll.POLLOUT
        enabled = [e for e in net.search()]
        self.assertTrue(len(enabled) == 1)
        self.assertFalse(net.output.marking)
        output = net(enabled[0])
        self.assertTrue(net.output.marking)
        self.assertTrue(sock in net.output.marking)
        self.assertTrue(net.output.marking[sock] & pynet.io.poll.POLLOUT)
        
#############################################################################
#############################################################################
