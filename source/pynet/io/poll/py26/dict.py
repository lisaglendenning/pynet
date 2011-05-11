# @copyright
# @license

from __future__ import absolute_import

from .ipolls import IPoller, EVENTS, POLLIN, POLLOUT, POLLEX, POLLHUP

#############################################################################
#############################################################################

class Dict(dict, IPoller,):

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
