
from __future__ import absolute_import

import collections

from peak.events import trellis

#############################################################################
#############################################################################

KEY, PREV, NEXT = range(3)

class OrderedSet(collections.MutableSet, trellis.Component):

    added = trellis.todo(list) # TODO: inefficient?
    removed = trellis.todo(list)
    to_add = added.future
    to_remove = removed.future
    
    end = trellis.make(list)

    def __init__(self, *args, **kwargs):
        end = []
        end += [None, end, end]         # sentinel node for doubly linked list
        trellis.Component.__init__(self, end=end,)
        if args or kwargs:
            self.update(*args, **kwargs)
    
    @trellis.compute
    def __len__(self):
        return self.map.__len__
    
    @trellis.compute
    def __contains__(self):
        return self.map.__contains__
    
    def __getitem__(self, index):
        if index < 0 or index >= len(self):
            raise IndexError(index)
        i = 0
        for item in self:
            if i == index:
                return item
            i += 1
        assert False
    
    def __iter__(self):
        end = self.end
        curr = end[NEXT]
        while curr is not end:
            yield curr[KEY]
            curr = curr[NEXT]
            
    def __reversed__(self):
        end = self.end
        curr = end[PREV]
        while curr is not end:
            yield curr[KEY]
            curr = curr[PREV]
    
    @trellis.modifier
    def update(self, iterable):
        for item in iterable:
            self.add(item)
            
    def pop(self, last=True):
        if not self:
            raise KeyError(self)
        key = reversed(self).next() if last else iter(self).next()
        self.discard(key)
        return key
    
    @trellis.maintain(make=dict)
    def map(self): # key --> [key, prev, next]
        map = self.map
        removed = self.removed
        added = self.added
        discard = self.__discard
        add = self.__add
        on_undo = trellis.on_undo
        for items, apply, undo in (removed, discard, add), (added, add, discard,),:
            if not items:
                continue
            trellis.mark_dirty()
            for item in items:
                apply(item)
                on_undo(undo, item)
        return map
    
    @trellis.modifier
    def add(self, item):
        return self.__change(self.to_add, item)
    
    @trellis.modifier
    def discard(self, item):
        return self.__change(self.to_remove, item)
    
    def __change(self, change, item):
        for ls in (self.to_add, self.to_remove,):
            i = 0
            while i < len(ls):
                if ls[i] == item:
                    del ls[i]
                else:
                    i += 1
        change.append(item)
    
    def __add(self, item):
        map = self.map
        if item not in map:
            end = self.end
            curr = end[PREV]
            curr[NEXT] = end[PREV] = map[item] = [item, curr, end]

    def __discard(self, item):
        map = self.map
        if item in map:
            item, prev, next = map.pop(item)
            prev[NEXT] = next
            next[PREV] = prev

#############################################################################
#############################################################################
