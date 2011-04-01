# @copyright
# @license

import abc

##############################################################################
##############################################################################

# IO event types
EVENTS = range(4)
POLLEX, POLLIN, POLLOUT, POLLHUP = EVENTS

##############################################################################
##############################################################################

class IPoller(object):
    r"""
    Registered objects must either be integer file descriptors, or
    be hashable objects with a fileno() method that returns a file descriptor.
    """
    __metaclass__ = abc.ABCMeta

    registry = None

    @classmethod
    def get_fileno(cls, obj):
        if isinstance(obj, int):
            return obj
        fd = obj.fileno()
        if not isinstance(fd, int):
            raise TypeError(obj)
        return fd

    def __enter__(self):
        self.registry = {}
        return self

    def __exit__(self, *args, **kwargs):
        for fd in self.registry.values():
            self.unregister(fd)
        self.registry = None
        return False
    
    def register(self, fd, events):
        if fd in self.registry:
            raise ValueError(fd)
        self.registry[fd] = events
    
    def modify(self, fd, events):
        if fd not in self.registry:
            raise ValueError(fd)
        if events != self.registry[fd]:
            self.registry[fd] = events
    
    def unregister(self, fd):
        if fd not in self.registry:
            raise ValueError(fd)
        del self.registry[fd]
    
    @abc.abstractmethod
    def poll(self, timeout=0.0):
        r"""
        timeout: seconds (float)
        """
        pass

##############################################################################
##############################################################################
