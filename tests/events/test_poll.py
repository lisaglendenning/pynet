# @copyright
# @license

r"""

History
-------

- Apr 8, 2011 @lisa: Created

"""


import unittest
import socket

from peak.events import trellis
from pynet.events.poll import *

#############################################################################
#############################################################################

class Simple(Polling):

    @trellis.maintain(initially=None)
    def pollin(self):
        pollin = self.pollin
        if pollin is None:
            pollin = self.Condition()
        if pollin not in self.vertices:
            self.vertices.add(pollin)
            self.link(pollin, self.poll)
        return pollin
    
    @trellis.maintain(initially=None)
    def pollout(self):
        pollout = self.pollout
        if pollout is None:
            pollout = self.Condition()
        if pollout not in self.vertices:
            self.vertices.add(pollout)
            self.link(self.poll, pollout)
        return pollout
    
    
        
class TestCasePoll(unittest.TestCase):

    def test_dgram(self, HOST='127.0.0.1', PORT=9000):
        
        net = Simple()
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((HOST, PORT))
        
        net.pollin.send((sock, POLLOUT))
        self.assertTrue(sock in net.pollin)
        self.assertFalse(net.pollout)
        
        net.poll()

        self.assertFalse(net.pollin)
        self.assertTrue(sock in net.pollout)
        self.assertTrue(net.pollout[sock] & POLLOUT)
        
#############################################################################
#############################################################################
