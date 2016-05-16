# vi: ts=4 sw=4 sts=4 expandtab
'''
:mod:`ophyd.utils` - Miscellaneous utility functions
====================================================

.. module:: ophyd.utils
   :synopsis:
'''

import logging
from collections import OrderedDict

from .errors import *
from .epics_pvs import *
from .paths import makedirs, make_dir_tree


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def enum(**enums):
    '''Create an enum from the keyword arguments'''
    return type('Enum', (object,), enums)


class OrderedDefaultDict(OrderedDict):
    """
    a combination of defaultdict and OrderedDict

    source: http://stackoverflow.com/a/6190500/1221924
    """
    def __init__(self, default_factory=None, *a, **kw):
        if (default_factory is not None and not callable(default_factory)):
            raise TypeError('first argument must be callable')
        super().__init__(*a, **kw)
        self.default_factory = default_factory

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            return self.__missing__(key)

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        self[key] = value = self.default_factory()
        return value

    def __reduce__(self):
        if self.default_factory is None:
            args = tuple()
        else:
            args = self.default_factory,
        return type(self), args, None, None, self.items()

    def copy(self):
        return self.__copy__()

    def __copy__(self):
        return type(self)(self.default_factory, self)

    def __deepcopy__(self, memo):
        import copy
        return type(self)(self.default_factory,
                          copy.deepcopy(self.items()))

    def __repr__(self):
        return '%s(%s, %s)' % (self.__class__.__name__, self.default_factory,
                               super().__repr__())
