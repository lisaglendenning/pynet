# @copyright
# @license

from __future__ import absolute_import

import abc
import collections

#############################################################################
#############################################################################

# IO event types
EVENTS = [2**i for i in xrange(4)]
POLLIN, POLLOUT, POLLHUP, POLLEX, = EVENTS

#############################################################################
#############################################################################

class IPoller(collections.MutableMapping):
    r"""
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

    @abc.abstractmethod
    def poll(self, timeout=0.0):
        r"""
        timeout: seconds (float)
        """
        pass

##############################################################################
##############################################################################
