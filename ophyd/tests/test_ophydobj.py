import logging
import pytest

from unittest.mock import Mock
from ophyd.ophydobj import OphydObject
from ophyd.status import (StatusBase, DeviceStatus, wait)

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

    with pytest.raises(ValueError):
        child.subscribe(None, event_type=None)

    with pytest.raises(KeyError):
        child.subscribe(lambda *args: None, event_type='unknown_event_type')

    assert parent.connected


def test_self_removing_cb():
    class TestObj(OphydObject):
        SUB_TEST = 'value'

    test_obj = TestObj(name='name', parent=None)

    hit_A = 0
    hit_B = 0

    def remover(obj, **kwargs):
        nonlocal hit_A
        hit_A += 1
        obj.clear_sub(remover)

    def sitter(**kwargs):
        nonlocal hit_B
        hit_B += 1

    test_obj.subscribe(remover, 'value')
    test_obj.subscribe(sitter, 'value')
    test_obj._run_subs(sub_type='value')

    assert hit_A == 1
    assert hit_B == 1

    test_obj._run_subs(sub_type='value')

    assert hit_A == 1
    assert hit_B == 2


def test_unsubscribe():
    class TestObj(OphydObject):
        SUB_TEST = 'value'

    test_obj = TestObj(name='name', parent=None)

    hit = 0

    def increment(**kwargs):
        nonlocal hit
        hit += 1

    cid = test_obj.subscribe(increment, 'value')
    test_obj._run_subs(sub_type='value')
    assert hit == 1
    test_obj.unsubscribe(cid)
    test_obj._run_subs(sub_type='value')
    assert hit == 1

    # check multi unsubscribe
    test_obj.unsubscribe(cid)
    test_obj.clear_sub(increment)
    assert hit == 1


def test_unsubscribe_all():
    class TestObj(OphydObject):
        SUB_TEST = 'value'

    test_obj = TestObj(name='name', parent=None)

    hit = 0

    def increment(**kwargs):
        nonlocal hit
        hit += 1

    test_obj.subscribe(increment, 'value')
    test_obj._run_subs(sub_type='value')
    assert hit == 1
    test_obj.unsubscribe_all()
    test_obj._run_subs(sub_type='value')
    assert hit == 1


def test_subscribe_warn(recwarn):
    class TestObj(OphydObject):
        SUB_TEST = 'value'
        _default_sub = SUB_TEST

    test_obj = TestObj(name='name', parent=None)
    test_obj.subscribe(lambda *args, **kwargs: None)
    assert len(recwarn) == 0


def test_subscribe_no_default():
    o = OphydObject(name='name', parent=None)

    with pytest.raises(ValueError):
        o.subscribe(lambda *a, **k: None)
