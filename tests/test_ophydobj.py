
import logging
import unittest
# import copy

from unittest.mock import Mock
from ophyd.ophydobj import OphydObject
from ophyd.status import (StatusBase, DeviceStatus, wait)

from . import main

logger = logging.getLogger(__name__)


class StatusTests(unittest.TestCase):
    def test_basic(self):
        st = StatusBase()
        st._finished()

    def test_callback(self):
        st = StatusBase()
        cb = Mock()

        st.finished_cb = cb
        self.assertIs(st.finished_cb, cb)
        self.assertRaises(RuntimeError, setattr, st, 'finished_cb', None)

        st._finished()
        cb.assert_called_once_with()

    def test_others(self):
        DeviceStatus(None)

    def test_wait(self):
        st = StatusBase()
        st._finished()
        wait(st)

    def test_wait_status_failed(self):
        st = StatusBase(timeout=0.05)
        self.assertRaises(RuntimeError, wait, st)

    def test_wait_timeout(self):
        st = StatusBase()
        self.assertRaises(TimeoutError, wait, st, timeout=0.05)


class OphydObjTests(unittest.TestCase):
    def test_ophydobj(self):
        parent = OphydObject(name='name', parent=None)
        child = OphydObject(name='name', parent=parent)
        self.assertIs(child.parent, parent)

        child._run_sub('not_a_callable', sub_type='sub')

        self.assertRaises(ValueError, child.subscribe, None,
                          event_type=None)
        self.assertRaises(KeyError, child.subscribe, None,
                          event_type='unknown_event_type')


is_main = (__name__ == '__main__')
main(is_main)
