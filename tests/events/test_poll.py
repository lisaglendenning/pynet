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

class Listener(trellis.Component):
    
    def __init__(self, polled):
        self.polled = polled
    
    @trellis.maintain(initially=0)
    def events(self):
        events = self.events
        polled = self.polled
        if polled.events:
            events |= polled.events
        return events

class TestCasePoll(unittest.TestCase):
    def test_dgram(self, HOST='127.0.0.1', PORT=9000):
        
        polling = Polling()
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((HOST, PORT))
        
        polling[sock] = POLLOUT
        self.assertTrue(sock in polling)
        polled = polling[sock]
        self.assertEqual(polled.registry, POLLOUT)
        
        listener = Listener(polled)

        self.assertEqual(listener.events, 0)
        polling.poll()
        self.assertEqual(listener.events, POLLOUT)
        
#############################################################################
#############################################################################
