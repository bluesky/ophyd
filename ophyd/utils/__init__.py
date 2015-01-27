# vi: ts=4 sw=4 sts=4 expandtab
'''
:mod:`ophyd.utils` - Miscellaneous utility functions
====================================================

.. module:: ophyd.utils
   :synopsis:
'''

import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

from .errors import *


def enum(**enums):
    '''Create an enum from the keyword arguments'''
    return type('Enum', (object,), enums)
