import logging
import unittest
import pytest

from unittest.mock import Mock
from ophyd.ophydobj import OphydObject
from ophyd.status import (StatusBase, DeviceStatus, wait)

from . import main

logger = logging.getLogger(__name__)


def test_status_basic():
    st = StatusBase()
    st._finished()


def test_status_callback():
    st = StatusBase()
    cb = Mock()

    st.finished_cb = cb
    assert st.finished_cb is cb
    with pytest.raises(RuntimeError):
        st.finished_cb = None

    st._finished()
    cb.assert_called_once_with()


def test_status_others():
    DeviceStatus(None)


def test_status_wait():
    st = StatusBase()
    st._finished()
    wait(st)


def test_wait_status_failed():
    st = StatusBase(timeout=0.05)
    with pytest.raises(RuntimeError):
        wait(st)


def test_status_wait_timeout():
    st = StatusBase()

    with pytest.raises(TimeoutError):
        wait(st, timeout=0.05)


def test_ophydobj():
    parent = OphydObject(name='name', parent=None)
    child = OphydObject(name='name', parent=parent)
    assert child.parent is parent

    child._run_sub('not_a_callable', sub_type='sub')

    with pytest.raises(ValueError):
        child.subscribe(None, event_type=None)

    with pytest.raises(KeyError):
        child.subscribe(None, event_type='unknown_event_type')

    assert parent.connected


is_main = (__name__ == '__main__')
main(is_main)
