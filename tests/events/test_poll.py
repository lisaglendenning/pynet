# @copyright
# @license

r"""

History
-------

- Apr 8, 2011 @lisa: Created

"""


import unittest
import socket

from pynet.mapping import *
from pynet.petri.poll import *

#############################################################################
#############################################################################

class TestCasePoll(unittest.TestCase):
    def test_dgram(self, HOST='127.0.0.1', PORT=9000):
        
        poller = Polling()
        
        registered = []
        poller.registry.register(MatchAny, lambda x: registered.append(x))
        events = []
        poller.events.register(MatchAny, lambda x: events.append(x))
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((HOST, PORT))
        
        input = { sock: POLLOUT, }
        poller.update(input)
        self.assertEqual(registered, [(sock, POLLOUT, poller.ADDED)])

        for x in poller.poll():
            pass
        self.assertEqual(events, [(sock, POLLOUT,)])
        
#############################################################################
#############################################################################
