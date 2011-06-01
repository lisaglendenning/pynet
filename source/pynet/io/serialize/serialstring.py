r"""Serializers convert complex objects to sequences of bits.

History
-------

- Mar 21, 2010 @lisa: Created

"""

import abc
import struct


##############################################################################
##############################################################################

class SerialString(object):
    """Abstract string Serializer base class.
    
    Delegates string<-->object serialization implementation to subclass.
    Provides common logic for iteratively serializing / deserializing
    and the overall encoding.
    
    Uses the strategy of prefixing the message with a length header.
    """
    __metaclass__ = abc.ABCMeta

    ENCODING = 'utf8'
    BYTE_ORDER = '!'
    HEADER_STRUCT = struct.Struct('%sI' % BYTE_ORDER)

    @classmethod
    @abc.abstractmethod
    def dumps(cls, obj):
        pass

    @classmethod
    @abc.abstractmethod
    def loads(cls, buf):
        pass    

    @classmethod
    def serializer(cls):
        def dumper(byte_order, header):
            nbytes = None
            while True:
                obj = yield
                data = cls.dumps(obj)
                payload_size = len(data) # TODO: assert maximum size
                assert payload_size > 0
                payload_fmt = '%s%ds' % (byte_order, payload_size)
                payload = struct.Struct(payload_fmt)
                nbytes = header.size + payload.size # buffer needs to be at least this size
                buf = yield nbytes
                assert len(buf) >= nbytes
                header.pack_into(buf, 0, payload_size)
                payload.pack_into(buf, header.size, data)
                yield nbytes
        coroutine = dumper(cls.BYTE_ORDER, cls.HEADER_STRUCT)
        coroutine.next()
        return coroutine

    @classmethod
    def deserializer(cls):
        def loader(byte_order, header):
            buf = None
            while True:
                next = header.size
                while buf is None:
                    buf = yield next
                assert len(buf) >= header.size
                payload_size, = header.unpack_from(buf)
                yield header.size
                buf = None
                payload_fmt = '%s%ds' % (byte_order, payload_size)
                payload = struct.Struct(payload_fmt)
                next = payload.size
                while buf is None:
                    buf = yield next
                assert len(buf) >= payload.size
                data, = payload.unpack_from(buf)
                yield payload.size
                obj = cls.loads(data)
                next = obj, header.size
                buf = yield next
        coroutine = loader(cls.BYTE_ORDER, cls.HEADER_STRUCT)
        coroutine.next()
        return coroutine

##############################################################################
##############################################################################
