# @copyright
# @license

r"""

History
-------

- Apr 8, 2011 @lisa: Created

"""


import unittest
import socket

from pynet.events.match import *
from pynet.events.poll import *

#############################################################################
#############################################################################

class TestCasePoll(unittest.TestCase):
    def test_dgram(self, HOST='127.0.0.1', PORT=9000):
        
        poller = Polling()
        
        registered = []
        poller.registry[MatchAny] = lambda x: registered.append(x)
        events = []
        poller.events[MatchAny] = lambda x: events.append(x)
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((HOST, PORT))
        
        poller[sock] = POLLOUT
        self.assertEqual(registered, [(sock, POLLOUT, poller.ADDED)])

        poller.poll()
        self.assertEqual(events, [(sock, POLLOUT,)])
        
#############################################################################
#############################################################################
