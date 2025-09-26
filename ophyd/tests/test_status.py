import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from ophyd import Device
from ophyd.signal import EpicsSignalRO, Signal
from ophyd.status import (
    DeviceStatus,
    MoveStatus,
    OrAnyStatus,
    StableSubscriptionStatus,
    StatusBase,
    SubscriptionStatus,
    TransitionStatus,
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


def test_subscription_status_does_not_try_and_stop_ro_device():
    # Arbitrary device
    d = EpicsSignalRO("Tst:Prefix", name="test")

    # Full fake callback signature
    def cb(*args, **kwargs):
        pass

    status = SubscriptionStatus(d, cb, event_type=d.SUB_VALUE)
    status._settled_event.set()
    status.set_exception(Exception())
    status.log.exception = MagicMock()

    status._run_callbacks()
    status.log.exception.assert_not_called()


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


def test_device_status_failure():
    dev = Device(name="dev")
    st = DeviceStatus(dev)
    with patch.object(dev, "stop") as mock_stop:
        st.set_exception(Exception("fail"))
        assert mock_stop.call_count == 1
    st2 = DeviceStatus(dev, call_stop_on_failure=False)
    with patch.object(dev, "stop") as mock_stop:
        st2.set_exception(Exception("fail"))
        assert mock_stop.call_count == 0


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


def test_status_timeout_infinite_with_settle_time():
    """
    When no timeout is specified, a "_run_callbacks" thread is not started,
    it is called upon termination of the status ("set_finished" or exception).
    However, if settle_time is given the callbacks will be called only
    after the settle time has expired (from a timer thread).
    """
    cb = Mock()
    st = StatusBase(settle_time=1)
    st.add_callback(cb)

    # there is no timeout, explicitely set finished ;
    # the callback should be called after "settle_time"
    st.set_finished()

    assert cb.call_count == 0
    with pytest.raises(WaitTimeoutError):
        # not ready yet
        st.wait(0.5)
    st.wait(0.6)
    cb.assert_called_once()


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


def test_compare_status_number():
    """Test CompareStatus with different operations."""
    sig = Signal(name="test_signal", value=0)
    status = CompareStatus(signal=sig, value=5, operation_success="==")
    assert status.done is False
    sig.put(1)
    assert status.done is False
    sig.put(5)
    status.wait(timeout=5)
    assert status.done is True

    sig.put(5)
    # Test with different operations
    status = CompareStatus(signal=sig, value=5, operation_success="!=")
    assert status.done is False
    sig.put(5)
    assert status.done is False
    sig.put(6)
    assert status.done is True
    assert status.success is True
    assert status.exception() is None

    sig.put(0)
    status = CompareStatus(signal=sig, value=5, operation_success=">")
    assert status.done is False
    sig.put(5)
    assert status.done is False
    sig.put(10)
    assert status.done is True
    assert status.success is True
    assert status.exception() is None

    # Should raise
    sig.put(0)
    status = CompareStatus(
        signal=sig, value=5, operation_success="==", failure_value=[10]
    )
    with pytest.raises(ValueError):
        sig.put(10)
        status.wait()
    assert status.done is True
    assert status.success is False
    assert isinstance(status.exception(), ValueError)

    # failure_operation
    sig.put(0)
    status = CompareStatus(
        signal=sig,
        value=5,
        operation_success="==",
        failure_value=10,
        operation_failure=">",
    )
    sig.put(10)
    assert status.done is False
    assert status.success is False
    sig.put(11)
    with pytest.raises(ValueError):
        status.wait()
    assert status.done is True
    assert status.success is False

    # raise if array is returned
    sig.put(0)
    status = CompareStatus(signal=sig, value=5, operation_success="==")
    with pytest.raises(ValueError):
        sig.put([1, 2, 3])
        status.wait(timeout=2)
    assert status.done is True
    assert status.success is False


def test_compare_status_string():
    """Test CompareStatus with string values"""
    sig = Signal(name="test_signal", value="test")
    status = CompareStatus(signal=sig, value="test", operation_success="==")
    assert status.done is False
    sig.put("test1")
    assert status.done is False
    sig.put("test")
    assert status.done is True

    sig.put("test")
    # Test with different operations
    status = CompareStatus(signal=sig, value="test", operation_success="!=")
    assert status.done is False
    sig.put("test")
    assert status.done is False
    sig.put("test1")
    assert status.done is True
    assert status.success is True
    assert status.exception() is None


def test_transition_status():
    """Test TransitionStatus"""
    sig = Signal(name="test_signal", value=0)

    # Test strict=True, without intermediate transitions
    sig.put(0)
    status = TransitionStatus(signal=sig, transitions=[1, 2, 3], strict=True)

    assert status.done is False
    sig.put(1)
    assert status.done is False
    sig.put(2)
    assert status.done is False
    sig.put(3)
    assert status.done is True
    assert status.success is True
    assert status.exception() is None

    # Test strict=True, failure_states
    sig.put(1)
    status = TransitionStatus(
        signal=sig, transitions=[1, 2, 3], strict=True, failure_states=[4]
    )
    assert status.done is False
    sig.put(4)
    with pytest.raises(ValueError):
        status.wait()

    assert status.done is True
    assert status.success is False
    assert isinstance(status.exception(), ValueError)

    # Test strict=False, with intermediate transitions
    sig.put(0)
    status = TransitionStatus(signal=sig, transitions=[1, 2, 3], strict=False)

    assert status.done is False
    sig.put(1)  # entering first transition
    sig.put(3)
    sig.put(2)  # transision
    assert status.done is False
    sig.put(4)
    sig.put(2)
    sig.put(3)  # last transition
    assert status.done is True
    assert status.success is True
    assert status.exception() is None


def test_transition_status_strings():
    """Test TransitionStatus with string values"""
    sig = Signal(name="test_signal", value="a")

    # Test strict=True, without intermediate transitions
    sig.put("a")
    status = TransitionStatus(signal=sig, transitions=["b", "c", "d"], strict=True)

    assert status.done is False
    sig.put("b")
    assert status.done is False
    sig.put("c")
    assert status.done is False
    sig.put("d")
    assert status.done is True
    assert status.success is True
    assert status.exception() is None

    # Test strict=True with additional intermediate transition

    sig.put("a")
    status = TransitionStatus(signal=sig, transitions=["b", "c", "d"], strict=True)

    assert status.done is False
    sig.put("b")  # first transition
    sig.put("e")
    sig.put("b")
    sig.put("c")  # transision
    assert status.done is False
    sig.put("f")
    sig.put("b")
    sig.put("c")
    sig.put("d")  # transision
    assert status.done is True
    assert status.success is True
    assert status.exception() is None

    # Test strict=False, with intermediate transitions
    sig.put("a")
    status = TransitionStatus(signal=sig, transitions=["b", "c", "d"], strict=False)

    assert status.done is False
    sig.put("b")  # entering first transition
    sig.put("d")
    sig.put("c")  # transision
    assert status.done is False
    sig.put("e")
    sig.put("c")
    sig.put("d")  # last transition
    assert status.done is True
    assert status.success is True


def test_and_all_status():
    """Test AndAllStatus"""
    dev = Device("Tst:Prefix", name="test")
    st1 = StatusBase()
    st2 = StatusBase()
    st3 = DeviceStatus(dev)
    and_status = AndAllStatus(dev, [st1, st2, st3])

    # Finish in success
    assert and_status.done is False
    st1.set_finished()
    assert and_status.done is False
    st2.set_finished()
    assert and_status.done is False
    st3.set_finished()
    assert and_status.done is True
    assert and_status.success is True

    # Failure
    st1 = StatusBase()
    st2 = StatusBase()
    st3 = DeviceStatus(dev)
    and_status = AndAllStatus(dev, [st1, st2, st3])

    assert and_status.done is False
    st1.set_finished()
    assert and_status.done is False
    st2.set_exception(Exception("Test exception"))
    assert and_status.done is True
    assert and_status.success is False
    assert st2.success is False
    assert st3.success is False

    # Not resolved before failure
    assert st3.done is False

    # Already resolved before failure
    assert st1.success is True


def test_or_any_status():
    """Test OrAnyStatus"""
    dev = Device("Tst:Prefix", name="test")
    st1 = StatusBase()
    st2 = StatusBase()
    st3 = DeviceStatus(dev)
    or_status = OrAnyStatus(dev, [st1, st2, st3])

    # Finish in success
    assert or_status.done is False
    st1.set_finished()
    assert or_status.done is True
    assert or_status.success is True

    st1 = StatusBase()
    or_status = OrAnyStatus(dev, [st1, st2, st3])
    assert or_status.done is False
    assert or_status.success is False
    st1.set_exception(Exception("Test exception"))
    assert or_status.done is False
    assert or_status.success is False
    st2.set_exception(RuntimeError("Test exception 2"))
    assert or_status.done is False
    assert or_status.success is False
    st3.set_exception(ValueError("Test exception 3"))
    assert or_status.done is True
    assert or_status.success is False
    assert isinstance(or_status.exception(), RuntimeError)
    assert (
        str(or_status.exception())
        == "Exception: Test exception; RuntimeError: Test exception 2; ValueError: Test exception 3"
    )
