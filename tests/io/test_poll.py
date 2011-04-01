# @copyright
# @license

r"""

History
-------

- Apr 26, 2010 @lisa: Created

"""


import unittest
import socket

import pynet.io.poll

#############################################################################
#############################################################################

class TestCasePoll(unittest.TestCase):
    
    def test_dgram(self, NSOCKS=4, HOST='127.0.0.1', PORT=9000):
        
        socks = [socket.socket(socket.AF_INET, socket.SOCK_DGRAM) \
                for i in xrange(NSOCKS)]
        for i in xrange(NSOCKS):
            socks[i].bind((HOST, PORT + i))
        
        def test(poller):
            for sock in socks:
                poller.register(sock, pynet.io.poll.POLLIN | pynet.io.poll.POLLOUT)
            
            token = 'hello world'
            
            for i in xrange(NSOCKS):
                if i < NSOCKS - 1:
                    j = i + 1
                else:
                    j = 0
                    
                sent = False
                received = False
                while not (sent and received):
                    for fd, event in poller.poll():
                        if event == pynet.io.poll.POLLIN:
                            self.assertEqual(fd, socks[j].fileno())
                            data, addr = socks[j].recvfrom(len(token))
                            self.assertEqual(data, token)
                            received = True
                        elif event == pynet.io.poll.POLLOUT:
                            if fd == socks[i].fileno() and not sent:
                                socks[i].sendto(token, socks[j].getsockname())
                                sent = True
                        else:
                            self.fail('%s: %s' % (fd, event))
        
        poller = pynet.io.poll.Poller()
        with poller:
            test(poller)

#############################################################################
#############################################################################
