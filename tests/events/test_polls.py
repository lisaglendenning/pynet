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

class Simple(Network):
    
    input = trellis.make(lambda self: self.Condition())
    output = trellis.make(lambda self: self.Condition())
    
    def __init__(self, *args, **kwargs):
        super(Simple, self).__init__(*args, **kwargs)
        for pair in ((self.input, self.poll), (self.poll, self.output,)):
            arc = self.Arc()
            net.link(arc, *pair)
    
        
class TestCasePolls(unittest.TestCase):

    def test_dgram(self, HOST='127.0.0.1', PORT=9000):
        
        net = Simple()
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((HOST, PORT))
        
        net.input.send((sock, POLLOUT))
        self.assertTrue(sock in net.input)
        self.assertTrue(net.input[sock] & POLLOUT)
        self.assertFalse(net.output)

        net()

        self.assertFalse(net.input)
        self.assertTrue(sock in net.output)
        self.assertTrue(net.output[sock] & POLLOUT)
        
#############################################################################
#############################################################################
