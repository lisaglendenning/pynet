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
    def dumper(cls):
        BYTE_ORDER = cls.BYTE_ORDER
        header = cls.HEADER_STRUCT
        nbytes = None
        while True:
            obj = yield None
            data = cls.dumps(obj)
            payload_size = len(data) # TODO: assert maximum size
            assert payload_size > 0
            payload_fmt = '%s%ds' % (BYTE_ORDER, payload_size)
            payload = struct.Struct(payload_fmt)
            nbytes = header.size + payload.size # buffer needs to be at least this size
            buf = yield nbytes
            assert len(buf) >= nbytes
            header.pack_into(buf, 0, payload_size)
            payload.pack_into(buf, payload_size, data)
            yield nbytes

    @classmethod
    def loader(cls):
        BYTE_ORDER = cls.BYTE_ORDER
        header = cls.HEADER_STRUCT
        next = header.size
        while True:
            buf = yield next
            assert len(buf) >= header.size
            payload_size, = header.unpack_from(buf)
            yield header.size
            payload_fmt = '%s%ds' % (BYTE_ORDER, payload_size)
            payload = struct.Struct(payload_fmt)
            next = payload.size
            buf = yield next
            assert len(buf) >= payload.size
            data, = payload.unpack_from(buf)
            yield payload.size
            obj = cls.loads(data)
            next = obj, header.size

##############################################################################
##############################################################################
