# @license
# @copyright

r"""short

History
-------

- Mar 21, 2010 @lisa: Created

"""

from __future__ import absolute_import

import json

from .serialstring import *

##############################################################################
##############################################################################

class SerialJSON(SerialString):
    
    SEPARATORS = (',',':') 

    @classmethod
    def dumps(cls, obj):
        uni = json.dumps(obj, 
                         ensure_ascii=False,
                         encoding=cls.ENCODING,
                         separators=cls.SEPARATORS)
        return uni.encode(cls.ENCODING)
        
    @classmethod
    def loads(cls, buffer):
        uni = unicode(buffer, cls.ENCODING)
        return json.loads(uni,
                          encoding=cls.ENCODING)

##############################################################################
##############################################################################
