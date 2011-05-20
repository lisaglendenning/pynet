# @copyright
# @license

r"""Low-level byte buffer.

History
-------

- Feb 24, 2010 @lisa: Created

"""

##############################################################################
##############################################################################

import ctypes
import functools

##############################################################################
##############################################################################

class Bounded(object):
    
    start = None
    stop = None
    
    def __len__(self):
        return self.stop - self.start
    
    def translate(self, index):
        start = self.start
        stop = self.stop
        if isinstance(index, slice):
            if index.start is not None:
                if index.start < 0:
                    start = self.stop + index.start
                else:
                    start = self.start + index.start
            if index.stop is not None:
                if index.stop < 0:
                    stop = self.stop + index.stop
                else:
                    stop = self.start + index.stop
            return start, stop
        elif isinstance(index, int):
            start = stop + index if index < 0 else start + index
            return start
        raise TypeError(index)
            
##############################################################################
##############################################################################

class Buffer(Bounded):
    
    array = staticmethod(ctypes.create_string_buffer)

    def __init__(self, bufsize=None):
        """
        **Parameters**
        
        `bufsize` : int
            initial buffer size
        """
        if bufsize is None:
            bufsize = 0
        self.buffer = self.array(bufsize)
    
    start = property(lambda self: 0)
    stop = property(lambda self: len(self.buffer))

    def translate(self, index):
        if isinstance(index, slice):
            start, stop = Bounded.translate(self, index)
            if start >= self.start and start <= stop and stop <= self.stop:
                return start, stop
        else:
            start = Bounded.translate(self, index)
            if start >= self.start and start < self.stop:
                return start
        raise IndexError(index)
        
    def __getitem__(self, index):
        return self.buffer[index]

    def __setitem__(self, index, val):
        if isinstance(index, slice):
            start, stop = self.translate(index)
            if index.stop is None:
                stop = min(stop, start + len(val))
            length = stop - start
            if length == 0:
                return
            ctypes.memmove(ctypes.byref(self.buffer, start), 
                           ctypes.c_char_p(val), length)
        else:
            self.buffer[index] = val

    def view(self, index=None, readonly=True):
        """Return an in-memory reference to some slice of the buffer."""
        start = self.start
        stop = self.stop
        if index is not None:
            if not isinstance(index, slice):
                raise TypeError(index)
            start, stop = self.translate(index)
        length = stop - start
        if readonly:
            buf = buffer(self.buffer, start, length)
        else:
            buf = (self.buffer._type_*length).from_buffer(self.buffer, start)
        return buf

##############################################################################
##############################################################################

class Window(Buffer):
    """Controls access to a fixed range of a buffer.
    """
    
    start = 0
    stop = 0

    def __init__(self, buffer):
        self.buffer = buffer
    
    def __getitem__(self, index):
        if isinstance(index, slice):
            start, stop = self.translate(index)
            return self.buffer[slice(start,stop)]
        else:
            if index < 0:
                start = self.stop + index
            else:
                start = self.start + index
            if start < self.start or start >= self.stop:
                raise IndexError(index) 
            return self.buffer[start]
    
    def __setitem__(self, index, val):
        if isinstance(index, slice):
            start, stop = self.translate(index)
            self.buffer[start:stop] = val
        else:
            if index < 0:
                start = self.stop + index
            else:
                start = self.start + index
            if start < self.start or start >= self.stop:
                raise IndexError(index) 
            self.buffer[start] = val
    
    def __rshift__(self, n):
        if not isinstance(n, int):
            raise TypeError(n)
        stop = self.stop + n
        if stop < self.start or stop > len(self.buffer):
            raise IndexError(n)
        self.stop = stop
        return self

    def __lshift__(self, n):
        if not isinstance(n, int):
            raise TypeError(n)
        start = self.start - n
        if start < 0 or start > self.stop:
            raise IndexError(n)
        self.start = start
        return self
    
    def clear(self):
        self.start = self.stop = 0

    def view(self, index=None, *args, **kwargs):
        if index is not None:
            if not isinstance(index, slice):
                raise TypeError(index)
            start, stop = self.translate(index)
        else:
            start = self.start
            stop = self.stop
        return self.buffer.view(slice(start,stop), *args, **kwargs)
        
##############################################################################
##############################################################################

def checked_bounds(f):
    
    def check(self):
        assert self.start >= 0
        assert self.stop <= len(self.buffer)
        assert self.start <= self.stop
    
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        check(self)
        v = f(self, *args, **kwargs)
        check(self)
        return v
    return wrapper


class BufferStream(Bounded):
    """Dynamically sized R/W buffer.
    
    Bytes are read from the beginning, and written to the end.
    """
    
    def __init__(self, bufsize=None):
        self.buffer = Buffer(bufsize)
        self.window = Window(self.buffer)
        
    start = property(lambda self: 0)
    stop = property(lambda self: len(self.window))
    free = property(lambda self: len(self.buffer) - self.window.stop)
    
    def __getitem__(self, index):
        return self.window[index]
        
    @checked_bounds
    def __setitem__(self, index, val):
        self.window[index] = val
    
    @checked_bounds
    def __rshift__(self, n):
        if n is None:
            n = len(self)
        elif not isinstance(n, int):
            raise TypeError(n)
        elif n < 0 or n > len(self):
            raise IndexError(n)
        if n == 0:
            return None
        val = self.window[:n]
        self.window << -n
        if len(self.window) == 0:
            self.window.clear()
        return val

    @checked_bounds
    def __lshift__(self, val):
        n = len(val)
        if n > self.free:
            self.resize((len(self) + n) * 2)
        start = len(self.window)
        stop = start + n
        self.window >> n
        self.window[start:stop] = val
        return n
        
    @checked_bounds
    def clear(self):
        self.window.clear()
    
    @checked_bounds
    def resize(self, size=None):
        """
        **Parameters**
        
        `size` : int
            new buffer size
        """
        oldbuf = self.buffer
        if size is None:
            size = len(oldbuf)*2
        newbuf = Buffer(size)
        window = self.window
        stop = min(len(window), size)
        if stop:
            newbuf[:stop] = window[:stop]
        window.buffer = newbuf
        window.clear()
        window >> stop
        self.buffer = newbuf
        return size
    
    @checked_bounds
    def read(self, reader, nbytes=None):
        if nbytes is None:
            index = None
        elif not isinstance(nbytes, int):
            raise TypeError(nbytes)
        elif nbytes < 0:
            raise ValueError(nbytes)
        else:
            index = slice(None, nbytes)
        buf = self.window.view(index=index, readonly=True)
        nbytes = reader(buf)
        if nbytes:
            if nbytes < 0 or nbytes > len(self):
                raise IndexError(nbytes)
            self.window << -nbytes
            if len(self.window) == 0:
                self.window.clear()
        return nbytes
    
    @checked_bounds
    def write(self, writer, nbytes=None):
        if nbytes is None:
            stop = None
            nbytes = self.free
        elif not isinstance(nbytes, int):
            raise TypeError(nbytes)
        elif nbytes < 0:
            raise ValueError(nbytes)
        else:
            if nbytes > self.free:
                self.resize(stop * 2)
        window = Window(self.buffer)
        window.start = self.window.stop
        window.stop = window.start + nbytes
        buf = window.view(readonly=False)
        nbytes = writer(buf)
        if nbytes:
            if nbytes < 0 or nbytes > len(buf):
                raise IndexError(nbytes)
            self.window >> nbytes
        return nbytes

##############################################################################
##############################################################################
