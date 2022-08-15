import copy
import logging
import threading
import time

import pytest

from ophyd import get_cl
from ophyd.areadetector.paths import EpicsPathSignal
from ophyd.signal import (
    DerivedSignal,
    EpicsSignal,
    EpicsSignalNoValidation,
    EpicsSignalRO,
    InternalSignal,
    InternalSignalError,
    Signal,
)
from ophyd.status import wait
from ophyd.utils import AlarmSeverity, AlarmStatus, ReadOnlyError

logger = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def ro_signal(cleanup, signal_test_ioc):
    sig = EpicsSignalRO(signal_test_ioc.pvs["pair_rbv"], name="pair_rbv")
    cleanup.add(sig)
    sig.wait_for_connection()
    return sig


@pytest.fixture(scope="function")
def nv_signal(cleanup, signal_test_ioc):
    sig = EpicsSignalNoValidation(signal_test_ioc.pvs["pair_set"], name="pair_set")
    cleanup.add(sig)
    sig.wait_for_connection()
    return sig


@pytest.fixture(scope="function")
def bool_enum_signal(cleanup, signal_test_ioc):
    sig = EpicsSignal(signal_test_ioc.pvs["bool_enum"], name="bool_enum")
    cleanup.add(sig)
    sig.wait_for_connection()
    return sig


@pytest.fixture(scope="function")
def rw_signal(cleanup, signal_test_ioc):
    sig = EpicsSignal(signal_test_ioc.pvs["read_write"], name="read_write")
    cleanup.add(sig)
    sig.wait_for_connection()
    return sig


@pytest.fixture(scope="function")
def pair_signal(cleanup, signal_test_ioc):
    sig = EpicsSignal(
        read_pv=signal_test_ioc.pvs["pair_rbv"],
        write_pv=signal_test_ioc.pvs["pair_set"],
        name="pair",
    )
    cleanup.add(sig)
    sig.wait_for_connection()
    return sig


@pytest.fixture(scope="function")
def motor_pair_signal(cleanup, motor):
    sig = EpicsSignal(
        write_pv=motor.user_setpoint.pvname, read_pv=motor.user_readback.pvname
    )
    cleanup.add(sig)
    sig.wait_for_connection()
    return sig


@pytest.fixture(scope="function")
def set_severity_signal(cleanup, signal_test_ioc):
    sig = EpicsSignal(signal_test_ioc.pvs["set_severity"], name="set_severity")
    cleanup.add(sig)
    sig.wait_for_connection()
    return sig


@pytest.fixture(scope="function")
def alarm_status_signal(cleanup, signal_test_ioc):
    sig = EpicsSignal(signal_test_ioc.pvs["alarm_status"], name="alarm_status")
    cleanup.add(sig)
    sig.wait_for_connection()
    return sig


def test_signal_base():
    start_t = time.time()

    name = "test"
    value = 10.0
    signal = Signal(name=name, value=value, timestamp=start_t)
    signal.wait_for_connection()

    assert signal.connected
    assert signal.name == name
    with pytest.warns(UserWarning):
        assert signal.value == value
    assert signal.get() == value
    assert signal.timestamp == start_t

    info = dict(called=False)

    def _sub_test(**kwargs):
        info["called"] = True
        info["kw"] = kwargs

    signal.subscribe(_sub_test, run=False, event_type=signal.SUB_VALUE)
    assert not info["called"]

    signal.value = value
    signal.clear_sub(_sub_test)

    signal.subscribe(_sub_test, run=False, event_type=signal.SUB_VALUE)
    signal.clear_sub(_sub_test, event_type=signal.SUB_VALUE)

    kw = info["kw"]
    assert "value" in kw
    assert "timestamp" in kw
    assert "old_value" in kw

    assert kw["value"] == value
    assert kw["old_value"] == value
    assert kw["timestamp"] == signal.timestamp

    # readback callback for soft signal
    info = dict(called=False)
    signal.subscribe(_sub_test, event_type=Signal.SUB_VALUE, run=False)
    assert not info["called"]
    signal.put(value + 1)
    assert info["called"]

    signal.clear_sub(_sub_test)
    kw = info["kw"]

    assert "value" in kw
    assert "timestamp" in kw
    assert "old_value" in kw

    assert kw["value"] == value + 1
    assert kw["old_value"] == value
    assert kw["timestamp"] == signal.timestamp

    signal.trigger()
    signal.read()
    signal.describe()
    signal.read_configuration()
    signal.describe_configuration()

    eval(repr(signal))


def test_signal_copy():
    start_t = time.time()

    name = "test"
    value = 10.0
    signal = Signal(name=name, value=value, timestamp=start_t)
    sig_copy = copy.copy(signal)

    assert signal.name == sig_copy.name
    with pytest.warns(UserWarning):
        assert signal.value == sig_copy.value
    assert signal.get() == sig_copy.get()
    assert signal.timestamp == sig_copy.timestamp


def test_signal_describe_fail():
    """
    Test Signal.describe() exception handling in the
    case where a Signal's value is not bluesky-friendly.
    """
    signal = Signal(name="the_none_signal", value=None)
    with pytest.raises(ValueError) as excinfo:
        signal.describe()
    assert "failed to describe 'the_none_signal' with value 'None'" in str(
        excinfo.value
    )


def test_internalsignal_write_from_internal():
    test_signal = InternalSignal(name="test_signal")
    for value in range(10):
        test_signal.put(value, internal=True)
        assert test_signal.get() == value
    for value in range(10):
        test_signal.set(value, internal=True).wait()
        assert test_signal.get() == value


def test_internalsignal_write_protection():
    test_signal = InternalSignal(name="test_signal")
    for value in range(10):
        with pytest.raises(InternalSignalError):
            test_signal.put(value)
        with pytest.raises(InternalSignalError):
            test_signal.set(value)


def test_epicssignal_readonly(cleanup, signal_test_ioc):
    signal = EpicsSignalRO(signal_test_ioc.pvs["read_only"])
    cleanup.add(signal)
    signal.wait_for_connection()
    print("EpicsSignalRO.metadata=", signal.metadata)
    signal.get()

    assert not signal.write_access
    assert signal.read_access

    with pytest.raises(ReadOnlyError):
        signal.value = 10

    with pytest.raises(ReadOnlyError):
        signal.put(10)

    with pytest.raises(ReadOnlyError):
        signal.set(10)

    # vestigial, to be removed
    with pytest.raises(AttributeError):
        signal.setpoint_ts

    # vestigial, to be removed
    with pytest.raises(AttributeError):
        signal.setpoint

    signal.precision
    signal.timestamp
    signal.limits

    signal.read()
    signal.describe()
    signal.read_configuration()
    signal.describe_configuration()

    eval(repr(signal))
    time.sleep(0.2)


def test_epicssignal_novalidation(nv_signal):
    print("EpicsSignalNoValidation.metadata=", nv_signal.metadata)

    nv_signal.put(10)
    st = nv_signal.set(11)

    assert st.done

    nv_signal.get()
    nv_signal.read()

    nv_signal.describe()
    nv_signal.describe_configuration()

    nv_signal.read_configuration()


def test_epicssignal_readwrite_limits(pair_signal):
    signal = pair_signal
    signal.use_limits = True
    signal.check_value((signal.low_limit + signal.high_limit) / 2)

    with pytest.raises(ValueError):
        signal.check_value(None)

    with pytest.raises(ValueError):
        signal.check_value(signal.low_limit - 1)

    with pytest.raises(ValueError):
        signal.check_value(signal.high_limit + 1)


def test_epicssignal_readwrite(signal_test_ioc, pair_signal):
    pair_signal.use_limits = True
    signal = pair_signal

    assert signal.setpoint_pvname == signal_test_ioc.pvs["pair_set"]
    assert signal.pvname == signal_test_ioc.pvs["pair_rbv"]
    signal.get()

    time.sleep(0.2)

    value = 10
    signal.value = value
    signal.put(value)
    assert signal.setpoint == value
    signal.setpoint_ts

    signal.limits
    signal.precision
    signal.timestamp

    signal.read()
    signal.describe()
    signal.read_configuration()
    signal.describe_configuration()

    eval(repr(signal))
    time.sleep(0.2)


def test_epicssignal_waveform(cleanup, signal_test_ioc):
    called = False

    def update_cb(value=None, **kwargs):
        nonlocal called
        assert len(value) > 1
        called = True

    signal = EpicsSignal(signal_test_ioc.pvs["waveform"], string=True)
    cleanup.add(signal)
    signal.wait_for_connection()

    sub = signal.subscribe(update_cb, event_type=signal.SUB_VALUE)
    assert len(signal.get()) > 1
    # force the current thread to allow other threads to run to service
    # subscription
    time.sleep(0.2)
    assert called
    signal.unsubscribe(sub)


def test_no_connection(cleanup, signal_test_ioc):
    sig = EpicsSignal("does_not_connect")
    cleanup.add(sig)

    with pytest.raises(TimeoutError):
        sig.wait_for_connection()

    sig = EpicsSignal("does_not_connect")
    cleanup.add(sig)

    with pytest.raises(TimeoutError):
        sig.put(0.0)

    with pytest.raises(TimeoutError):
        sig.get()

    sig = EpicsSignal(signal_test_ioc.pvs["read_only"], write_pv="does_not_connect")
    cleanup.add(sig)
    with pytest.raises(TimeoutError):
        sig.wait_for_connection()


def test_enum_strs(bool_enum_signal):
    assert bool_enum_signal.enum_strs == ("Off", "On")


def test_setpoint(rw_signal):
    rw_signal.get_setpoint()
    rw_signal.get_setpoint(as_string=True)


def test_epicssignalro():
    with pytest.raises(TypeError):
        # not in initializer parameters anymore
        EpicsSignalRO("test", write_pv="nope_sorry")


def test_describe(bool_enum_signal):
    sig = bool_enum_signal

    sig.put(1)
    desc = sig.describe()["bool_enum"]
    assert desc["dtype"] == "integer"
    assert desc["shape"] == []
    # assert 'precision' in desc
    assert desc["enum_strs"] == ("Off", "On")
    assert "upper_ctrl_limit" in desc
    assert "lower_ctrl_limit" in desc

    sig = Signal(name="my_pv")
    sig.put("Off")
    desc = sig.describe()["my_pv"]
    assert desc["dtype"] == "string"
    assert desc["shape"] == []

    sig.put(3.14)
    desc = sig.describe()["my_pv"]
    assert desc["dtype"] == "number"
    assert desc["shape"] == []

    import numpy as np

    sig.put(
        np.array(
            [
                1,
            ]
        )
    )
    desc = sig.describe()["my_pv"]
    assert desc["dtype"] == "array"
    assert desc["shape"] == [
        1,
    ]


def test_set_method():
    sig = Signal(name="sig")

    st = sig.set(28)
    wait(st)
    assert st.done
    assert st.success
    assert sig.get() == 28


def test_soft_derived():
    timestamp = 1.0
    value = "q"
    original = Signal(name="original", timestamp=timestamp, value=value)

    cb_values = []

    def callback(value=None, **kwargs):
        cb_values.append(value)

    derived = DerivedSignal(derived_from=original, name="derived")
    derived.subscribe(callback, event_type=derived.SUB_VALUE)

    assert derived.timestamp == timestamp
    assert derived.get() == value
    assert derived.timestamp == timestamp
    assert derived.describe()[derived.name]["derived_from"] == original.name
    assert derived.write_access == original.write_access
    assert derived.read_access == original.read_access

    new_value = "r"
    derived.put(new_value)
    assert original.get() == new_value
    assert derived.get() == new_value
    assert derived.timestamp == original.timestamp
    assert derived.limits == original.limits

    copied = copy.copy(derived)
    with pytest.warns(UserWarning):
        assert copied.derived_from.value == original.value
    assert copied.derived_from.timestamp == original.timestamp
    assert copied.derived_from.name == original.name

    derived.put("s")
    assert cb_values == ["r", "s"]

    called = []

    event = threading.Event()

    def meta_callback(*, connected, read_access, write_access, **kw):
        called.append(("meta", connected, read_access, write_access))
        event.set()

    derived.subscribe(meta_callback, event_type=derived.SUB_META, run=False)

    original._metadata["write_access"] = False
    original._run_subs(sub_type="meta", **original._metadata)

    event.wait(1)

    assert called == [("meta", True, True, False)]


def test_epics_signal_derived_ro(ro_signal):
    assert ro_signal.connected
    assert ro_signal.read_access
    assert not ro_signal.write_access

    derived = DerivedSignal(derived_from=ro_signal, name="derived")
    derived.wait_for_connection()

    assert derived.connected
    assert derived.read_access
    assert not derived.write_access

    assert derived.timestamp == ro_signal.timestamp
    assert derived.get() == ro_signal.get()


def test_epics_signal_derived_nv(nv_signal):
    assert nv_signal.connected
    assert nv_signal.read_access
    assert nv_signal.write_access

    derived = DerivedSignal(derived_from=nv_signal, name="derived")
    derived.wait_for_connection()

    assert derived.connected

    assert derived.timestamp == nv_signal.timestamp


@pytest.mark.motorsim
@pytest.mark.parametrize("put_complete", [True, False])
def test_epicssignal_set(motor_pair_signal, put_complete):
    sim_pv = motor_pair_signal
    sim_pv.put_complete = put_complete

    logging.getLogger("ophyd.signal").setLevel(logging.DEBUG)
    logging.getLogger("ophyd.utils.epics_pvs").setLevel(logging.DEBUG)
    print("tolerance=", sim_pv.tolerance)
    assert sim_pv.tolerance is not None

    start_pos = sim_pv.get()

    # move to +0.2 and check the status object
    target = sim_pv.get() + 0.2
    st = sim_pv.set(target, timeout=1, settle_time=0.001)
    wait(st, timeout=5)
    assert st.done
    assert st.success
    print("status 1", st)
    assert abs(target - sim_pv.get()) < 0.05

    # move back to -0.2, forcing a timeout with a low value
    target = sim_pv.get() - 0.2
    st = sim_pv.set(target, timeout=1e-6)
    time.sleep(0.5)
    print("status 2", st)
    assert st.done
    assert not st.success

    # keep the axis in position
    st = sim_pv.set(start_pos)
    wait(st, timeout=5)


statuses_and_severities = [
    (AlarmStatus.NO_ALARM, AlarmSeverity.NO_ALARM),
    (AlarmStatus.READ, AlarmSeverity.MINOR),
    (AlarmStatus.WRITE, AlarmSeverity.MAJOR),
    (AlarmStatus.HIHI, AlarmSeverity.INVALID),
    (AlarmStatus.NO_ALARM, AlarmSeverity.NO_ALARM),
]


@pytest.mark.parametrize("status, severity", statuses_and_severities)
def test_epicssignal_alarm_status(
    set_severity_signal, alarm_status_signal, pair_signal, status, severity
):
    alarm_status_signal.put(status, wait=True)
    set_severity_signal.put(severity, wait=True)

    pair_signal.get()
    assert pair_signal.alarm_status == status
    assert pair_signal.alarm_severity == severity

    pair_signal.get_setpoint()
    assert pair_signal.setpoint_alarm_status == status
    assert pair_signal.setpoint_alarm_severity == severity


@pytest.mark.parametrize("status, severity", statuses_and_severities)
def test_epicssignalro_alarm_status(
    set_severity_signal, alarm_status_signal, ro_signal, status, severity
):
    alarm_status_signal.put(status, wait=True)
    set_severity_signal.put(severity, wait=True)

    ro_signal.get()
    assert ro_signal.alarm_status == status
    assert ro_signal.alarm_severity == severity


def test_hints(cleanup, fake_motor_ioc):
    sig = EpicsSignalRO(fake_motor_ioc.pvs["setpoint"])
    cleanup.add(sig)
    assert sig.hints == {"fields": [sig.name]}


def test_epicssignal_sub_setpoint(cleanup, fake_motor_ioc):
    pvs = fake_motor_ioc.pvs
    pv = EpicsSignal(write_pv=pvs["setpoint"], read_pv=pvs["readback"], name="pv")
    cleanup.add(pv)

    setpoint_called = []
    setpoint_meta_called = []

    def sub_setpoint(old_value, value, **kwargs):
        setpoint_called.append((old_value, value))

    def sub_setpoint_meta(timestamp, **kwargs):
        setpoint_meta_called.append(timestamp)

    pv.subscribe(sub_setpoint, event_type=pv.SUB_SETPOINT)
    pv.subscribe(sub_setpoint_meta, event_type=pv.SUB_SETPOINT_META)

    pv.wait_for_connection()

    pv.put(1, wait=True)
    pv.put(2, wait=True)
    time.sleep(1.0)

    assert len(setpoint_called) >= 3
    assert len(setpoint_meta_called) >= 3


def test_epicssignal_get_in_callback(fake_motor_ioc, cleanup):
    pvs = fake_motor_ioc.pvs
    sig = EpicsSignal(write_pv=pvs["setpoint"], read_pv=pvs["readback"], name="motor")
    cleanup.add(sig)

    called = []

    def generic_sub(sub_type, **kwargs):
        called.append((sub_type, sig.get(), sig.get_setpoint()))

    for event_type in (
        sig.SUB_VALUE,
        sig.SUB_META,
        sig.SUB_SETPOINT,
        sig.SUB_SETPOINT_META,
    ):
        sig.subscribe(generic_sub, event_type=event_type)

    sig.wait_for_connection()

    sig.put(1, wait=True)
    sig.put(2, wait=True)
    time.sleep(0.5)

    print(called)
    # Arbitrary threshold, but if @klauer screwed something up again, this will
    # blow up
    assert len(called) < 20
    print("total", len(called))
    sig.unsubscribe_all()


@pytest.mark.motorsim
@pytest.mark.parametrize(
    "pvname, count",
    [
        ("sim:mtr1.RBV", 10),
        ("sim:mtr2.RBV", 10),
        ("sim:mtr1.RBV", 100),
        ("sim:mtr2.RBV", 100),
    ],
)
def test_epicssignal_pv_reuse(cleanup, pvname, count):
    signals = [EpicsSignal(pvname, name="sig") for i in range(count)]

    for sig in signals:
        cleanup.add(sig)
        sig.wait_for_connection()
        assert sig.connected
        assert sig.get() is not None

    if get_cl().name == "pyepics":
        assert len(set(id(sig._read_pv) for sig in signals)) == 1


@pytest.fixture(scope="function")
def path_signal(cleanup, signal_test_ioc):
    sig = EpicsPathSignal(
        signal_test_ioc.pvs["path"], name="path", path_semantics="posix"
    )
    cleanup.add(sig)
    sig.wait_for_connection()
    return sig


@pytest.mark.parametrize(
    "paths",
    [
        ("C:\\some\\path\\here"),
        ("D:\\here\\is\\another\\"),
        ("C:/yet/another/path"),
        ("D:/more/paths/here/"),
    ],
)
def test_windows_paths(paths, path_signal):
    path_signal.path_semantics = "nt"
    path_signal.set(paths).wait(3)


@pytest.mark.parametrize("paths", [("/some/path/here"), ("/here/is/another/")])
def test_posix_paths(paths, path_signal):
    path_signal.set(paths).wait(3)


def test_path_semantics_exception():
    with pytest.raises(ValueError):
        EpicsPathSignal("TEST", path_semantics="not_a_thing")


def test_import_ro_signal_class():
    from ophyd import SignalRO as SignalRoFromPkg
    from ophyd.signal import SignalRO as SignalRoFromModule

    assert SignalRoFromPkg is SignalRoFromModule
