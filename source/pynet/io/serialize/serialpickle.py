# @license
# @copyright

r"""short

History
-------

- Mar 18, 2010 @lisa: Refactored out

"""

from __future__ import absolute_import

import cPickle

from .serialstring import *

##############################################################################
##############################################################################

class SerialPickle(SerialString):

    PICKLE_PROTOCOL = 2

    @classmethod
    def dumps(cls, obj):
        pickled = cPickle.dumps(obj, cls.PICKLE_PROTOCOL)
        return pickled

    @classmethod
    def loads(cls, buffer):
        unpickled = cPickle.loads(buffer)
        return unpickled

##############################################################################
##############################################################################
