# @copyright
# @license

#############################################################################
#############################################################################

# IO event types
EVENTS = [2**i for i in xrange(4)]
POLLIN, POLLOUT, POLLHUP, POLLEX, = EVENTS

#############################################################################
#############################################################################

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

    def poll(self, timeout=0.0):
        r"""Iterator over a set of (fd, event) pairs.
        timeout: seconds (float)
        """
        raise NotImplementedError
    
    #
    # override builtins
    #
    
    def update(self, *args, **kwargs):
        for arg in args:
            try:
                itr = arg.iteritems()
            except AttributeError:
                try:
                    itr = iter(arg)
                except AttributeError:
                    raise TypeError(arg)
            for k,v in itr:
                self[k] = v
        for k,v in kwargs.iteritems():
            self[k] = v
    
    def clear(self):
        for k in self.keys():
            del self[k]
    
    def pop(self, k, **kwargs):
        if k in self:
            v = self[k]
            del self[k]
            return v
        else:
            if 'default' in kwargs:
                return kwargs['default']
            else:
                raise KeyError(k)
    
    def popitem(self):
        if not self:
            raise KeyError(self)
        for k in self:
            break
        return k, self.pop(k)

#############################################################################
#############################################################################
