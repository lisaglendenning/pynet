# @copyright
# @license

from __future__ import absolute_import

import collections
import operator

from peak.events import trellis
from peak.events import collections as pcollections

#############################################################################
#############################################################################

class Mapping(collections.MutableMapping, trellis.Component):
    r"""Wrapper around a Dict for finer granularity."""
    
    ADDED = 'ADDED'
    CHANGED = 'CHANGED'
    REMOVED = 'REMOVED'
    CHANGES = set([ADDED, CHANGED, REMOVED])
    
    values = trellis.make(trellis.Dict)
    
    def __init__(self, values=None, *args, **kwargs):
        if values:
            values = trellis.Dict(values)
        else:
            values = trellis.Dict()
        trellis.Component.__init__(self, *args, values=values, **kwargs)

    def __hash__(self):
        return object.__hash__(self.values)
    
    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.values is other.values
    
    @trellis.maintain
    def __len__(self,):
        return self.values.__len__

    @trellis.maintain
    def __iter__(self,):
        return self.values.__iter__
    
    @trellis.maintain
    def __getitem__(self,):
        return self.values.__getitem__

    @trellis.maintain
    def __delitem__(self,):
        return self.values.__delitem__

    @trellis.maintain
    def __setitem__(self,):
        return self.values.__setitem__

    @trellis.maintain(initially=None)
    def changes(self):
        hub = self.changes
        if hub is None:
            hub = pcollections.Hub()
        values = self.values
        if values.added or values.changed or values.deleted:
            for change, changes in zip((self.ADDED, self.CHANGED, self.REMOVED,), 
                                       (values.added, values.changed, values.deleted,),):
                for k,v in changes.iteritems():
                    hub.put(change, v, k)
        return hub

#############################################################################
#############################################################################
        