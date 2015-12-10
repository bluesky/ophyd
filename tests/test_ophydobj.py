from __future__ import print_function
import logging
import unittest
# import copy

from unittest.mock import Mock
from ophyd.controls.ophydobj import (OphydObject, StatusBase)

from . import main

logger = logging.getLogger(__name__)


class StatusTests(unittest.TestCase):
    def test_basic(self):
        st = StatusBase()
        st._finished()

    def test_callback(self):
        st = StatusBase()
        cb = Mock()
        print(cb)
        st.finished_cb = cb
        self.assertIs(st.finished_cb, cb)
        self.assertRaises(RuntimeError, setattr, st, 'finished_cb', None)

        st._finished()
        cb.assert_called_once_with()


is_main = (__name__ == '__main__')
main(is_main)
