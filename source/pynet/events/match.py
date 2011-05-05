# @copyright
# @license

from __future__ import absolute_import

import itertools

#############################################################################
#############################################################################

class Match(tuple):
    
    def __new__(cls, *values):
        self = super(Match, cls).__new__(cls, values)
        return self
    
    def __and__(self, *args):
        return True

MatchAny = Match()

class MatchOperator(tuple):
    
    def __new__(cls, operator, *matchers):
        self = super(Match, cls).__new__(cls, operator, *matchers)
        self.operator = operator
        self.matchers = self[1:]
        return self
    
    def __and__(self, value):
        operator = self.operator
        matchers = self.matchers
        return reduce(operator, itertools.imap(lambda m: m & value, matchers))
    
class MatchType(Match):
    
    def __new__(cls, type, value):
        self = super(MatchType, cls).__new__(cls, type, value)
        self.type = type
        self.value = value
        return self
    
    def __and__(self, value):
        if not isinstance(value, self.type):
            return False
        return self.value & value

class MatchPredicate(Match):

    def __new__(cls, values):
        self = super(MatchPredicate, cls).__new__(cls, *values)
        self.predicate = self[0]
        return self
    
    def __and__(self, value):
        return self.predicate(value)

#############################################################################
#############################################################################
        