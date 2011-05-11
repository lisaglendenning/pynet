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

#############################################################################
#############################################################################
