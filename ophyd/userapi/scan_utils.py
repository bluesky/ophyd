"""

Scan Utils

Utilities for help with scan routines

"""

from itertools import tee

class scan_iterator_nd(object):
    def __init__(self, nd, n, vals):
        """Create N-Dimensional Iterator

        :param nd: A tuple of length of the dimensionality.
        :param n: The dimension of the iterator

        """
        self.dim = n + 1
        self.n = 0
        self.vals = vals
        self._valn = 0
        self.max_n = 1
        for n in nd[:self.dim]:
            self.max_n = self.max_n * n

    def __iter__(self):
        return self

    def next(self):
        if (self.n % self.max_n) == 0:
            if self._valn == len(self.vals):
                self._valn = 0
            self.val = self.vals[self._valn]
            self._valn += 1
        self.n += 1
        return self.val
