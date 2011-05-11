# @copyright
# @license

import sys

#############################################################################
#############################################################################

# IO event types
EVENTS = [2**i for i in xrange(4)]
POLLIN, POLLOUT, POLLHUP, POLLEX, = EVENTS

#############################################################################
#############################################################################

if sys.version_info[1] < 6:
    
    import UserDict
    
    class IPoller(dict):
        """
        Registered objects must either be integer file descriptors, or
        be hashable objects with a fileno() method that returns a file descriptor.
        """
    
        @classmethod
        def get_fileno(cls, obj):
            if isinstance(obj, int):
                return obj
            fd = obj.fileno()
            if not isinstance(fd, int):
                raise TypeError(obj)
            return fd
        
#        def __init__(self):
#            self.registry = {}
#    
#        def __getitem__(self, fd):
#            return self.registry[fd]
#    
#        def __setitem__(self, fd, events):
#            self.registry[fd] = events
#            
#        def __delitem__(self, fd):
#            if fd not in self:
#                raise KeyError(fd)
#            del self.registry[fd]
#        
#        def __len__(self):
#            return len(self.registry)
#        
#        def __iter__(self):
#            for k in self.registry:
#                yield k
#        
#        def keys(self):
#            return self.registry.keys()

        def poll(self, timeout=0.0):
            r"""
            timeout: seconds (float)
            """
            pass
else:
    import abc
    import collections
    
    class IPoller(collections.MutableMapping):
        r"""
        Registered objects must either be integer file descriptors, or
        be hashable objects with a fileno() method that returns a file descriptor.
        """
        __metaclass__ = abc.ABCMeta
    
        @classmethod
        def get_fileno(cls, obj):
            if isinstance(obj, int):
                return obj
            fd = obj.fileno()
            if not isinstance(fd, int):
                raise TypeError(obj)
            return fd
        
        def __init__(self):
            self.registry = {}
    
        def __getitem__(self, fd):
            return self.registry[fd]
    
        def __setitem__(self, fd, events):
            self.registry[fd] = events
            
        def __delitem__(self, fd):
            if fd not in self:
                raise KeyError(fd)
            del self.registry[fd]
        
        def __len__(self):
            return len(self.registry)
        
        def __iter__(self):
            for k in self.registry:
                yield k
    
        @abc.abstractmethod
        def poll(self, timeout=0.0):
            r"""
            timeout: seconds (float)
            """
            pass

##############################################################################
##############################################################################
