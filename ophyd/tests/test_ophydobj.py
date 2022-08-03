import logging
import time
from unittest.mock import Mock

import pytest

from ophyd.ophydobj import (
    OphydObject,
    register_instances_in_weakset,
    register_instances_keyed_on_name,
)
from ophyd.status import DeviceStatus, StatusBase, wait
from ophyd.utils import WaitTimeoutError

logger = logging.getLogger(__name__)


def test_status_basic():
    st = StatusBase()
    st.set_finished()


def test_status_callback_deprecated():
    "The old way, with finished_cb"
    st = StatusBase()
    cb = Mock()

    with pytest.warns(UserWarning):
        st.finished_cb = cb
    with pytest.warns(UserWarning):
        assert st.finished_cb is cb
    with pytest.raises(RuntimeError):
        st.finished_cb = None

    st.set_finished()
    st.wait(1)
    time.sleep(0.1)  # Wait for callbacks to run.
    cb.assert_called_once_with(st)


def test_status_callback():
    "The new way, with add_callback and the callbacks property"
    st = StatusBase()
    cb = Mock()

    st.add_callback(cb)
    assert st.callbacks[0] is cb

    st.set_finished()
    st.wait(1)
    time.sleep(0.1)  # Wait for callbacks to run.
    cb.assert_called_once_with(st)


def test_status_others():
    DeviceStatus(None)


def test_status_wait():
    st = StatusBase()
    st.set_finished()
    wait(st)


def test_wait_status_failed():
    st = StatusBase(timeout=0.05)
    with pytest.raises(TimeoutError):
        wait(st)


def test_status_wait_timeout():
    st = StatusBase()

    with pytest.raises(WaitTimeoutError):
        wait(st, timeout=0.05)


def test_ophydobj():
    parent = OphydObject(name="name", parent=None)
    child = OphydObject(name="name", parent=parent)
    assert child.parent is parent

    with pytest.raises(ValueError):
        child.subscribe(None, event_type=None)

    with pytest.raises(KeyError):
        child.subscribe(lambda *args: None, event_type="unknown_event_type")

    assert parent.connected


def test_self_removing_cb():
    class TestObj(OphydObject):
        SUB_TEST = "value"

    test_obj = TestObj(name="name", parent=None)

    hit_A = 0
    hit_B = 0

    def remover(obj, **kwargs):
        nonlocal hit_A
        hit_A += 1
        obj.clear_sub(remover)

    def sitter(**kwargs):
        nonlocal hit_B
        hit_B += 1

    test_obj.subscribe(remover, "value")
    test_obj.subscribe(sitter, "value")
    test_obj._run_subs(sub_type="value")

    assert hit_A == 1
    assert hit_B == 1

    test_obj._run_subs(sub_type="value")

    assert hit_A == 1
    assert hit_B == 2


def test_unsubscribe():
    class TestObj(OphydObject):
        SUB_TEST = "value"

    test_obj = TestObj(name="name", parent=None)

    hit = 0

    def increment(**kwargs):
        nonlocal hit
        hit += 1

    cid = test_obj.subscribe(increment, "value")
    test_obj._run_subs(sub_type="value")
    assert hit == 1
    test_obj.unsubscribe(cid)
    test_obj._run_subs(sub_type="value")
    assert hit == 1

    # check multi unsubscribe
    test_obj.unsubscribe(cid)
    test_obj.clear_sub(increment)
    assert hit == 1


def test_unsubscribe_all():
    class TestObj(OphydObject):
        SUB_TEST = "value"

    test_obj = TestObj(name="name", parent=None)

    hit = 0

    def increment(**kwargs):
        nonlocal hit
        hit += 1

    test_obj.subscribe(increment, "value")
    test_obj._run_subs(sub_type="value")
    assert hit == 1
    test_obj.unsubscribe_all()
    test_obj._run_subs(sub_type="value")
    assert hit == 1


def test_subscribe_warn(recwarn):
    class TestObj(OphydObject):
        SUB_TEST = "value"
        _default_sub = SUB_TEST

    test_obj = TestObj(name="name", parent=None)
    test_obj.subscribe(lambda *args, **kwargs: None)
    assert len(recwarn) == 0


def test_subscribe_no_default():
    o = OphydObject(name="name", parent=None)

    with pytest.raises(ValueError):
        o.subscribe(lambda *a, **k: None)


def test_register_instance():
    weakset = register_instances_in_weakset()
    test1 = OphydObject(name="test1")
    assert test1 in weakset
    test2 = OphydObject(name="test1")
    assert test2 in weakset

    weakdict = register_instances_keyed_on_name()
    test1 = OphydObject(name="test1")
    assert weakdict["test1"] == test1
    test2 = OphydObject(name="test2")
    assert weakdict["test2"] == test2

    assert OphydObject._OphydObject__any_instantiated is True
    with pytest.raises(RuntimeError):
        register_instances_in_weakset(fail_if_late=True)
    with pytest.raises(RuntimeError):
        register_instances_keyed_on_name(fail_if_late=True)
