# @license
# @copyright

import abc

##############################################################################
##############################################################################

# IO event types
EVENTS = range(4)
POLLEX, POLLIN, POLLOUT, POLLHUP = EVENTS

##############################################################################
##############################################################################

class IPoller(object):
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
        for obj in self.registered():
            self.unregister(obj)
        self.registry = None
        return False
    
    def register(self, obj, events):
        fd = self.get_fileno(obj)
        if fd in self.registry:
            raise ValueError(obj)
        self.registry[fd] = obj
        return fd
    
    def modify(self, obj, events):
        fd = self.get_fileno(obj)
        if fd not in self.registry:
            raise ValueError(obj)
        return fd
    
    def unregister(self, obj):
        fd = self.get_fileno(obj)
        if fd not in self.registry:
            raise ValueError(obj)
        del self.registry[fd]
        return fd

    def registered(self):
        return self.registry.values()
    
    @abc.abstractmethod
    def poll(self, timeout=0.0):
        r"""
        timeout: seconds
        """
        pass

##############################################################################
##############################################################################
