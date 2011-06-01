# @copyright
# @license

r"""Extension of (IP,port) tuple.

History
-------

- Mar 9, 2010 @lisa: Created

"""

from __future__ import absolute_import


import socket
import struct
import operator


##############################################################################
##############################################################################

class IPAddress(tuple):
    """IP4 network address."""
    
    FAMILY = socket.AF_INET
    
    LOCALHOST = '127.0.0.1'

    @classmethod
    def from_string(cls, text):
        """ Converts a string representation to a network address. """
        if not isinstance(text, str):
            raise TypeError, text
        colon_index = text.find(':')
        if not (colon_index > 0 and colon_index < len(text) - 1):
            raise ValueError, text
        ip = text[:colon_index]
        try:
            port = int(text[colon_index + 1:])
        except ValueError:
            raise ValueError, text
        if not ip[0].isdigit():
            ip = cls.get_host_by_name(ip)
        return (ip, port)

    @classmethod
    def to_string(cls, addr):
        """ Converts a network address to a string representation. """
        if not isinstance(addr, tuple):
            raise TypeError(addr)
        if len(addr) != 2:
            raise ValueError(addr)
        string = ':'.join(map(str, addr))
        return string
    
    @classmethod
    def from_numeric(cls, num):
        """ Converts an integer representation to a network address. """
        # 16 lower order bits are the port
        ip = num >> 16
        ip = struct.pack('!I', ip)
        ip = socket.inet_ntop(cls.FAMILY, ip)
        port = 0xffff & num
        return (ip, port)
    
    @classmethod
    def to_numeric(cls, addr):
        """ Converts a network address to an integer representation. """
        ip = socket.inet_pton(cls.FAMILY, addr[0])
        ip, = struct.unpack_from('!I', ip)
        # We should need a maximum of 16 bits for the port
        # 32 bits for IP = 48 bits total
        packed = (ip << 16) | addr[1]
        return packed

##############################################################################
    
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        if args:
            if len(args) == 2:
                ipaddr = args
            elif len(args) == 1:
                arg = args[0]
                if isinstance(arg, tuple):
                    ipaddr = arg
                elif isinstance(arg, str):
                    ipaddr = cls.from_string(arg)
                elif isinstance(arg, (int, long)):
                    ipaddr = cls.from_numeric(arg)
                else:
                    raise ValueError(ipaddr)
            else:
                raise ValueError(args)
        elif kwargs:
            ip = kwargs.get('ip', cls.LOCALHOST)
            port = kwargs.get('port', 0)
            ipaddr = (ip, port)
        else:
            ipaddr = (cls.LOCALHOST, 0)
        if not (len(ipaddr) == 2 and isinstance(ipaddr[0], str) and isinstance(ipaddr[1], int)):
            raise TypeError(ipaddr)
        return tuple.__new__(cls, ipaddr)

    def __int__(self):
        return self.to_numeric(self)
    
    def __str__(self):
        return self.to_string(self)

##############################################################################
    
    ip = property(operator.itemgetter(0), None, None)
    port = property(operator.itemgetter(1), None, None)

##############################################################################
##############################################################################
