import time
from unittest.mock import Mock

import pytest

from ophyd import Device
from ophyd.status import (
    MoveStatus,
    StableSubscriptionStatus,
    StatusBase,
    SubscriptionStatus,
    UseNewProperty,
)
from ophyd.utils import (
    InvalidState,
    StatusTimeoutError,
    UnknownStatusFailure,
    WaitTimeoutError,
)


def _setup_state_and_cb(new_signature=True):
    state = {}

    if new_signature:

        def cb(status):
            state["done"] = True

    else:

        def cb():
            state["done"] = True

    return state, cb


def test_status_post():
    st = StatusBase()
    state, cb = _setup_state_and_cb()

    assert "done" not in state
    st.add_callback(cb)
    assert "done" not in state
    st.set_finished()
    st.wait(1)
    time.sleep(0.1)  # Wait for callbacks to run.
    assert "done" in state
    assert state["done"]


def test_status_legacy_finished_cb():
    st = StatusBase()
    state1, cb1 = _setup_state_and_cb()
    state2, cb2 = _setup_state_and_cb()

    # The old setter works for adding one callback.
    with pytest.warns(UserWarning):
        st.finished_cb = cb1
    # The new getter works.
    st.callbacks == set([cb1])
    # And the old getter works so long as there is just one callback set.
    with pytest.warns(UserWarning):
        assert st.finished_cb is cb1
    # As before, the old setter cannot be updated once set.
    with pytest.raises(UseNewProperty):
        st.finished_cb = cb2
    # But, using the new method, we can add another callback.
    st.add_callback(cb2)
    # Once we have two callbacks, the getter does not work.
    with pytest.raises(UseNewProperty):
        st.finished_cb
    # But the new getter does.
    st.callbacks == set([cb1, cb2])

    assert "done" not in state1
    assert "done" not in state2
    st.set_finished()
    st.wait(1)
    time.sleep(0.1)  # Wait for callbacks to run.
    assert "done" in state1
    assert "done" in state2


def test_status_pre():
    st = StatusBase()
    state, cb = _setup_state_and_cb()

    st.set_finished()
    st.wait(1)
    time.sleep(0.1)  # Wait for callbacks to run.

    assert "done" not in state
    st.add_callback(cb)
    assert "done" in state
    assert state["done"]


def test_direct_done_setting():
    st = StatusBase()
    state, cb = _setup_state_and_cb()

    with pytest.raises(RuntimeError):
        st.done = True  # changing isn't allowed
    with pytest.warns(UserWarning):
        st.done = False  # but for now no-ops warn

    st.set_finished()
    st.wait(1)
    time.sleep(0.1)  # Wait for callbacks to run.

    with pytest.raises(RuntimeError):
        st.done = False  # changing isn't allowed
    with pytest.warns(UserWarning):
        st.done = True  # but for now no-ops warn


def test_subscription_status():
    # Arbitrary device
    d = Device("Tst:Prefix", name="test")
    # Mock callback
    m = Mock()

    # Full fake callback signature
    def cb(*args, done=False, **kwargs):
        # Run mock callback
        m()
        # Return finished or not
        return done

    status = SubscriptionStatus(d, cb, event_type=d.SUB_ACQ_DONE)

    # Run callbacks but do not mark as complete
    d._run_subs(sub_type=d.SUB_ACQ_DONE, done=False)
    time.sleep(0.1)  # Wait for callbacks to run.
    assert m.called
    assert not status.done and not status.success

    # Run callbacks and mark as complete
    d._run_subs(sub_type=d.SUB_ACQ_DONE, done=True)
    time.sleep(0.1)  # Wait for callbacks to run.
    assert status.done and status.success


def test_given_stability_time_greater_than_timeout_then_exception_on_initialisation():
    # Arbitrary device
    d = Device("Tst:Prefix", name="test")

    with pytest.raises(ValueError):
        StableSubscriptionStatus(
            d, Mock(), stability_time=2, timeout=1, event_type=d.SUB_ACQ_DONE
        )


def test_given_callback_stays_stable_then_stable_status_eventual_returns_done():
    # Arbitrary device
    d = Device("Tst:Prefix", name="test")
    # Mock callback
    m = Mock()

    # Full fake callback signature
    def cb(*args, done=False, **kwargs):
        # Run mock callback
        m()
        # Return finished or not
        return done

    status = StableSubscriptionStatus(d, cb, 0.2, event_type=d.SUB_ACQ_DONE)

    # Run callbacks that return complete but status waits until stable
    d._run_subs(sub_type=d.SUB_ACQ_DONE, done=True)
    time.sleep(0.1)  # Wait for callbacks to run.
    assert m.called
    assert not status.done and not status.success

    time.sleep(0.15)
    assert status.done and status.success


def test_given_callback_fluctuates_and_stabalises_then_stable_status_eventual_returns_done():
    # Arbitrary device
    d = Device("Tst:Prefix", name="test")
    # Mock callback
    m = Mock()

    # Full fake callback signature
    def cb(*args, done=False, **kwargs):
        # Run mock callback
        m()
        # Return finished or not
        return done

    status = StableSubscriptionStatus(d, cb, 0.2, event_type=d.SUB_ACQ_DONE)

    # First start as looking stable
    d._run_subs(sub_type=d.SUB_ACQ_DONE, done=True)
    time.sleep(0.1)  # Wait for callbacks to run.
    assert m.called
    assert not status.done and not status.success

    # Then become unstable
    d._run_subs(sub_type=d.SUB_ACQ_DONE, done=False)
    time.sleep(0.1)  # Wait for callbacks to run.
    assert m.called
    assert not status.done and not status.success

    # Still not successful
    time.sleep(0.15)
    assert not status.done and not status.success

    # Now test properly stable
    d._run_subs(sub_type=d.SUB_ACQ_DONE, done=True)
    time.sleep(0.1)  # Wait for callbacks to run.
    assert m.called
    assert not status.done and not status.success

    time.sleep(0.15)
    assert status.done and status.success


def test_and():
    st1 = StatusBase()
    st2 = StatusBase()
    st3 = st1 & st2
    # make sure deep recursion works
    st4 = st1 & st3
    st5 = st3 & st4

    assert st1 in st3
    assert st1 in st4
    assert st1 in st5
    assert st2 in st4
    assert st2 in st5

    unused_status = StatusBase()
    assert unused_status not in st3
    unused_status.set_finished()

    state1, cb1 = _setup_state_and_cb()
    state2, cb2 = _setup_state_and_cb()
    state3, cb3 = _setup_state_and_cb()
    state4, cb4 = _setup_state_and_cb()
    state5, cb5 = _setup_state_and_cb()
    st1.add_callback(cb1)
    st2.add_callback(cb2)
    st3.add_callback(cb3)
    st4.add_callback(cb4)
    st5.add_callback(cb5)
    st1.set_finished()
    st1.wait(1)
    time.sleep(0.1)  # Wait for callbacks to run.
    assert "done" in state1
    assert "done" not in state2
    assert "done" not in state3
    assert "done" not in state4
    assert "done" not in state5
    st2.set_finished()
    st3.wait(1)
    st4.wait(1)
    st5.wait(1)
    time.sleep(0.1)  # Wait for callbacks to run.
    assert "done" in state3
    assert "done" in state4
    assert "done" in state5
    assert st3.left is st1
    assert st3.right is st2
    assert st4.left is st1
    assert st4.right is st3
    assert st5.left is st3
    assert st5.right is st4


def test_notify_watchers():
    from ophyd.sim import hw

    hw = hw()
    mst = MoveStatus(hw.motor, 10)

    def callback(*args, **kwargs):
        ...

    mst.watch(callback)
    mst.target = 0
    mst.start_pos = 0
    mst._notify_watchers(0)


def test_old_signature():
    st = StatusBase()
    state, cb = _setup_state_and_cb(new_signature=False)
    with pytest.warns(DeprecationWarning, match="signature"):
        st.add_callback(cb)
    assert not state
    st.set_finished()
    st.wait(1)
    time.sleep(0.1)  # Wait for callbacks to run.
    assert state


def test_old_signature_on_finished_status():
    st = StatusBase()
    state, cb = _setup_state_and_cb(new_signature=False)
    st.set_finished()
    st.wait(1)
    with pytest.warns(DeprecationWarning, match="signature"):
        st.add_callback(cb)
    assert state


def test_old_finished_method_success():
    st = StatusBase()
    state, cb = _setup_state_and_cb()
    st.add_callback(cb)
    assert not state
    st._finished()
    st.wait(1)
    time.sleep(0.1)  # Wait for callbacks to run.
    assert state
    assert st.done
    assert st.success


def test_old_finished_method_failure():
    st = StatusBase()
    state, cb = _setup_state_and_cb()
    st.add_callback(cb)
    assert not state
    st._finished(success=False)
    with pytest.raises(UnknownStatusFailure):
        st.wait(1)
    time.sleep(0.1)  # Wait for callbacks to run.
    assert state
    assert st.done
    assert not st.success


def test_set_finished_twice():
    st = StatusBase()
    st.set_finished()
    with pytest.raises(InvalidState):
        st.set_finished()


def test_set_exception_twice():
    st = StatusBase()
    exc = Exception()
    st.set_exception(exc)
    with pytest.raises(InvalidState):
        st.set_exception(exc)


def test_set_exception_wrong_type():
    st = StatusBase()
    NOT_AN_EXCEPTION = object()
    with pytest.raises(ValueError):
        st.set_exception(NOT_AN_EXCEPTION)


def test_set_exception_special_banned_exceptions():
    """
    Exceptions with special significant to StatusBase are banned. See comments
    in set_exception.
    """
    st = StatusBase()
    # Test the class and the instance of each.
    with pytest.raises(ValueError):
        st.set_exception(StatusTimeoutError)
    with pytest.raises(ValueError):
        st.set_exception(StatusTimeoutError())
    with pytest.raises(ValueError):
        st.set_exception(WaitTimeoutError)
    with pytest.raises(ValueError):
        st.set_exception(WaitTimeoutError())


def test_exception_fail_path():
    st = StatusBase()

    class LocalException(Exception):
        ...

    exc = LocalException()
    st.set_exception(exc)
    assert exc is st.exception()
    with pytest.raises(LocalException):
        st.wait(1)


def test_exception_fail_path_with_class():
    """
    Python allows `raise Exception` and `raise Exception()` so we do as well.
    """
    st = StatusBase()

    class LocalException(Exception):
        ...

    st.set_exception(LocalException)
    assert LocalException is st.exception()
    with pytest.raises(LocalException):
        st.wait(1)


def test_exception_success_path():
    st = StatusBase()
    st.set_finished()
    assert st.wait(1) is None
    assert st.exception() is None


def test_wait_timeout():
    """
    A WaitTimeoutError is raised when we block on wait(TIMEOUT) or
    exception(TIMEOUT) and the Status has not finished.
    """
    st = StatusBase()
    with pytest.raises(WaitTimeoutError):
        st.wait(0.01)
    with pytest.raises(WaitTimeoutError):
        st.exception(0.01)


def test_status_timeout():
    """
    A StatusTimeoutError is raised when the timeout set in __init__ has
    expired.
    """
    st = StatusBase(timeout=0)
    with pytest.raises(StatusTimeoutError):
        st.wait(1)
    assert isinstance(st.exception(), StatusTimeoutError)


def test_status_timeout_with_settle_time():
    """
    A StatusTimeoutError is raised when the timeout set in __init__ plus the
    settle_time has expired.
    """
    st = StatusBase(timeout=0, settle_time=1)
    # Not dead yet.
    with pytest.raises(WaitTimeoutError):
        st.exception(0.01)
    # But now we are.
    with pytest.raises(StatusTimeoutError):
        st.wait(2)


def test_external_timeout():
    """
    A TimeoutError is raised, not StatusTimeoutError or WaitTimeoutError,
    when set_exception(TimeoutError) has been set.
    """
    st = StatusBase(timeout=1)
    st.set_exception(TimeoutError())
    with pytest.raises(TimeoutError) as exc:
        st.wait(1)
    assert not isinstance(exc, WaitTimeoutError)
    assert not isinstance(exc, StatusTimeoutError)


def test_race_settle_time_and_timeout():
    """
    A StatusTimeoutError should NOT occur here because that is only invoked
    after (timeout + settle_time) has elapsed.
    """
    st = StatusBase(timeout=1, settle_time=3)
    st.set_finished()  # starts a threading.Timer with the settle_time
    time.sleep(1.5)
    # We should still be settling....
    with pytest.raises(WaitTimeoutError):
        st.wait(1)
    # Now we should be done successfully.
    st.wait(3)


def test_set_finished_after_timeout():
    """
    If an external callback (e.g. pyepics) calls set_finished after the status
    has timed out, ignore it.
    """
    st = StatusBase(timeout=0)
    time.sleep(0.1)
    assert isinstance(st.exception(), StatusTimeoutError)
    # External callback fires, too late.
    st.set_finished()
    assert isinstance(st.exception(), StatusTimeoutError)


def test_set_exception_after_timeout():
    """
    If an external callback (e.g. pyepics) calls set_exception after the status
    has timed out, ignore it.
    """
    st = StatusBase(timeout=0)
    time.sleep(0.1)
    assert isinstance(st.exception(), StatusTimeoutError)

    class LocalException(Exception):
        ...

    # External callback reports failure, too late.
    st.set_exception(LocalException())
    assert isinstance(st.exception(), StatusTimeoutError)


def test_nonsensical_init():
    with pytest.raises(ValueError):
        StatusBase(success=True, done=False)
    with pytest.raises(ValueError):
        StatusBase(success=True, done=None)


def test_deprecated_init():
    with pytest.warns(DeprecationWarning, match="set_finished"):
        StatusBase(success=True, done=True)
    with pytest.warns(DeprecationWarning, match="set_finished"):
        StatusBase(success=False, done=True)
    with pytest.warns(DeprecationWarning, match="set_finished"):
        StatusBase(success=False, done=False)
    with pytest.warns(DeprecationWarning, match="set_finished"):
        StatusBase(success=False, done=None)
    with pytest.warns(DeprecationWarning, match="set_finished"):
        StatusBase(success=None, done=True)
    with pytest.warns(DeprecationWarning, match="set_finished"):
        StatusBase(success=None, done=False)


def test_error_in_settled_method():
    state, cb = _setup_state_and_cb()

    class BrokenStatus(StatusBase):
        def _settled(self):
            raise Exception

    st = BrokenStatus()
    st.add_callback(cb)
    st.set_finished()
    st.wait(1)
    time.sleep(0.1)  # Wait for callbacks to run.
    assert state


def test_error_in_handle_failure_method():
    state, cb = _setup_state_and_cb()

    class BrokenStatus(StatusBase):
        def _handle_failure(self):
            raise Exception

    st = BrokenStatus()
    st.add_callback(cb)
    st.set_finished()
    st.wait(1)
    time.sleep(0.1)  # Wait for callbacks to run.
    assert state
