# @copyright
# @license

r"""

History
-------

- Aug 25, 2010 @lisa: Created

"""

import unittest
import random

import io.buffer

#############################################################################
#############################################################################

class TestCaseBuffer(unittest.TestCase):
    
    @classmethod
    def make_data(cls, k, max=256):
        return bytes(bytearray(random.sample(xrange(max), k)))
    
    
    def test_buffer(self):
        for n in [1,2,4]:
            buf = io.buffer.Buffer(n)
            self.assertEqual(len(buf), n)
            for i in [n, n+1]:
                self.assertRaises(IndexError, buf.__getitem__, i)
            data = self.make_data(n)
            buf[:] = data
            self.assertEqual(buf[:], data)
            for i in xrange(-1, -(n-1), -1):
                self.assertEqual(buf[i], data[i])
                
    
    def test_window(self):
        n = 4
        buf = io.buffer.Buffer(n)
        zeros = b'0' * n
        
        buf[:] = zeros
        win = io.buffer.Window(buf)
        self.assertEqual(len(win), 0)
        self.assertRaises(IndexError, win.__getitem__, 0)
        start = 1
        stop = 2
        self.assertRaises(IndexError, win.__lshift__, start)
        self.assertRaises(IndexError, win.__rshift__, n+1)
        win >> start + stop
        win << -start
        self.assertRaises(IndexError, win.__rshift__, -(stop+1))
        data = self.make_data(len(win))
        win[:] = data
        self.assertEqual(win[:], data)
        self.assertEqual(buf[win.start:win.stop], data)
        self.assertEqual(buf[:win.start], zeros[:win.start])
        self.assertEqual(buf[win.stop:], zeros[win.stop:])
        
        buf[:] = zeros
        win << start
        win >> -start
        win[:] = data
        self.assertEqual(win[:], data)
        self.assertEqual(win[:], data)
        self.assertEqual(buf[win.start:win.stop], data)
        self.assertEqual(buf[:win.start], zeros[:win.start])
        self.assertEqual(buf[win.stop:], zeros[win.stop:])
        
        win.clear()
        self.assertEqual(len(win), 0)
    
    
    def test_bufferstream(self):
        n = 1
        buf = io.buffer.BufferStream(n)
        
        self.assertEqual(len(buf), 0)
        buf.clear()
        self.assertEqual(len(buf), 0)
        for i in [-1, 0, 1]:
            self.assertRaises(IndexError, buf.__getitem__, i)
        self.assertEqual(buf >> None, None)
        
        for j in [n, n*2]:
            data = self.make_data(j)
            self.assertEqual(buf << data, j)
            self.assertEqual(len(buf), j)
            self.assertEqual(buf[:], data)
            self.assertEqual(buf >> j, data)
            self.assertEqual(len(buf), 0)
        
            for i in xrange(j):
                def writer(b):
                    b[0] = data[i]
                    return 1
                self.assertEqual(buf.write(writer, 1), 1)
                self.assertEqual(len(buf), i+1)
                self.assertEqual(buf[i], data[i])
                
            for i in xrange(j):
                def reader(b):
                    assert b[0] == data[i]
                    return 1
                self.assertEqual(buf.read(reader, 1), 1)
                self.assertEqual(len(buf), j-i-1)


#############################################################################
#############################################################################
