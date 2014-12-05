"""

Scan Utils

Utilities for help with scan routines

"""

class scan_iterator_nd(object):
    def __init__(self, nd, n, vals):
        """Create N-Dimensional Iterator

        :param nd: A tuple of length of the dimensionality.
        :param n: The dimension of the iterator
        :param vals: A 1D list, tuple or array of values along this
            dimension to use. 

        """
        self.dim = n + 1
        self._i = 0
        self.vals = vals
        self._vali = 0

        # Make the product from 0 to self.dim
        self.max_n = 1
        for n in nd[:self.dim]:
            self.max_n = self.max_n * n

    def __iter__(self):
        return self

    def next(self):
        if (self._i % self.max_n) == 0:
            if self._vali == len(self.vals):
                self._vali = 0
            self.val = self.vals[self._vali]
            self._vali += 1
        self._i += 1
        return self.val
