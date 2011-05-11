# @copyright
# @license

# TODO: this data is inefficient because every match is checked
# for every event
# However, this inefficiency could be eliminated using caching
# if matches and events are constants (immutable)

from __future__ import absolute_import

import collections
import itertools

from peak.events import trellis

#############################################################################
#############################################################################

class Dispatch(collections.MutableMapping, trellis.Component):

    keys = trellis.make(None)
    values = trellis.make(None)

    def __init__(self, Keys=None, Values=None):
        if Keys is None:
            from . import orderedset
            Keys = orderedset.OrderedSet
        if Values is None:
            Values = trellis.Dict
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
    def __contains__(self,):
        return self.keys.__contains__
    
    @trellis.compute
    def __getitem__(self,):
        return self.values.__getitem__

    @trellis.modifier
    def __delitem__(self, k,):
        if k not in self:
            raise KeyError(k)
        self.keys.remove(k)
        del self.values[k]

    @trellis.modifier
    def __setitem__(self, k, v,):
        self.keys.add(k)
        self.values[k] = v
    
    @trellis.modifier
    def send(self, value):
        for k in self.all(value):
            thunk = self[k]
            thunk(value)

    def all(self, v): # yields all matches
        return itertools.ifilter(lambda x: x & v, iter(self))
                
    def any(self, v): # returns the first match, or None
        for match in self:
            if match & v:
                return match
        return None

#############################################################################
#############################################################################
