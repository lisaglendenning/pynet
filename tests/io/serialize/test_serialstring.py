# @license
# @copyright

r"""

History
-------

- Mar 21, 2010 @lisa: Created

"""

from __future__ import absolute_import

import unittest, socket, time

from pynet.io.serialize import serialstring, serialpickle, serialjson

#############################################################################
#############################################################################

class TestCaseSerialString(unittest.TestCase):

    def check_object(self, dumper, loader, buf, obj):
        
        # dump
        
        next = dumper.send(obj)
        self.assertTrue(next is not None)
        packed = 0
        while next is not None:
            if packed > 0:
                b = buf[packed:]
            else:
                b = buf
            self.assertTrue(next <= len(b))
            packed += dumper.send(b)
            next = dumper.next()

        # load

        next = loader.next()
        unpacked = 0
        while True:
            self.assertTrue(next <= (packed - unpacked))
            if unpacked > 0:
                b = bytes(buf[unpacked:])
            else:
                b = bytes(buf)
            unpacked += loader.send(b)
            next = loader.next()
            if isinstance(next, tuple):
                result, next = next
                break
        
        # results
        
        self.assertEqual(packed, unpacked)
        self.assertEqual(result, obj)
    
    def check(self, dumper, loader):
        
        loader = loader()
        dumper = dumper()
        
        buf = bytearray(128)
        
        REPEATS = 4
        objs = ('hello', 0, ['foo', 2], {'x':0,'y':1})
        for repeat in xrange(REPEATS):
            for obj in objs:
                self.check_object(dumper, loader, buf, obj)
    
    def test_all(self): # the actual unit test
        for subclass in (serialpickle.SerialPickle, serialjson.SerialJSON):
            self.check(subclass.serializer, subclass.deserializer)

#############################################################################
#############################################################################
