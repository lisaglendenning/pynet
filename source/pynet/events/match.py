# @copyright
# @license

from __future__ import absolute_import

import itertools
import operator

#############################################################################
#############################################################################

class Match(tuple):
    
    def __new__(cls, *values):
        self = super(Match, cls).__new__(cls, values)
        return self
    
    def __and__(self, *args):
        return True

MatchAny = Match()

class MatchOperator(Match):
    
    def __new__(cls, operator, *matchers):
        self = super(MatchOperator, cls).__new__(cls, operator, *matchers)
        self.operator = self[0]
        self.matchers = self[1:]
        return self
    
    def __and__(self, value):
        operator = self.operator
        matchers = self.matchers
        return reduce(operator, itertools.imap(lambda m: m & value, matchers))

And = operator.__and__
Or = operator.__or__
    
class MatchType(Match):
    
    def __new__(cls, type,):
        self = super(MatchType, cls).__new__(cls, type,)
        self.type = self[0]
        return self
    
    def __and__(self, value):
        return isinstance(value, self.type)

class MatchPredicate(Match):

    def __new__(cls, predicate):
        self = super(MatchPredicate, cls).__new__(cls, predicate,)
        self.predicate = self[0]
        return self
    
    def __and__(self, value):
        return self.predicate(value)

#############################################################################
#############################################################################
        