# @copyright
# @license

from __future__ import absolute_import

import collections
import itertools

from peak.events import trellis

#############################################################################
#############################################################################

class Dispatch(collections.MutableMapping, trellis.Component):

    keys = trellis.make(None)
    values = trellis.make(None)
    cache = trellis.attr(resetting_to={}) # TODO: inefficient?

    def __init__(self, Keys=None, Values=dict):
        if Keys is None:
            from oset import oset
            Keys = oset
        keys = Keys()
        values = Values()
        trellis.Component.__init__(self, keys=keys, values=values)

    @trellis.compute
    def __len__(self,):
        return self.keys.__len__

    @trellis.compute
    def __iter__(self,):
        return self.keys.__iter__
    
    @trellis.compute
    def __getitem__(self,):
        return self.values.__getitem__

    def __delitem__(self, k,):
        self.keys.remove(k)
        del self.values[k]

    def __setitem__(self, k, v,):
        self.keys.add(k)
        self.values[k] = v
    
    @trellis.modifier
    def put(self, value):
        cache = self.cache
        for k in self.all(value):
            thunk = self[k]
            if value not in cache:
                cache[value] = []
            cache[value].append((thunk, thunk(value)))

    def all(self, v): # yields all matches
        return itertools.ifilter(lambda x: x & v, iter(self))
                
    def any(self, v): # returns the first match, or None
        for match in self:
            if match & v:
                return match
        return None

#############################################################################
#############################################################################
