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
from pypetri import net
from pynet.events.polls import *

#############################################################################
#############################################################################

class Simple(Polling):

    @trellis.maintain(initially=None)
    def pollin(self):
        pollin = self.pollin
        if pollin is None:
            pollin = self.Condition()
        for output in pollin.outputs:
            if output.output is self.poll:
                break
        else:
            arc = self.Arc()
            net.link(arc, pollin, self.poll)
        return pollin
    
    @trellis.maintain(initially=None)
    def pollout(self):
        pollout = self.pollout
        if pollout is None:
            pollout = self.Condition()
        for input in pollout.inputs:
            if input.input is self.poll:
                break
        else:
            arc = self.Arc()
            net.link(arc, self.poll, pollout)
        return pollout
    
    
        
class TestCasePolls(unittest.TestCase):

    def test_dgram(self, HOST='127.0.0.1', PORT=9000):
        
        net = Simple()
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((HOST, PORT))
        
        net.pollin[sock] = POLLOUT
        self.assertTrue(sock in net.pollin)
        self.assertTrue(net.pollin[sock] & POLLOUT)
        self.assertFalse(net.pollout)
        
        net()

        self.assertFalse(net.pollin)
        self.assertTrue(sock in net.pollout)
        self.assertTrue(net.pollout[sock] & POLLOUT)
        
#############################################################################
#############################################################################
