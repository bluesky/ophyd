import logging
import time
import copy
import pytest

from ophyd.signal import (Signal, EpicsSignal, EpicsSignalRO, DerivedSignal)
from ophyd.utils import ReadOnlyError
from ophyd.status import wait

logger = logging.getLogger(__name__)


def test_signal_base():
    start_t = time.time()

    name = 'test'
    value = 10.0
    signal = Signal(name=name, value=value, timestamp=start_t)
    signal.wait_for_connection()

    assert signal.connected
    assert signal.name == name
    assert signal.value == value
    assert signal.get() == value
    assert signal.timestamp == start_t

    info = dict(called=False)

    def _sub_test(**kwargs):
        info['called'] = True
        info['kw'] = kwargs

    signal.subscribe(_sub_test, run=False,
                     event_type=signal.SUB_VALUE)
    assert not info['called']

    signal.value = value
    signal.clear_sub(_sub_test)

    signal.subscribe(_sub_test, run=False,
                     event_type=signal.SUB_VALUE)
    signal.clear_sub(_sub_test, event_type=signal.SUB_VALUE)

    kw = info['kw']
    assert 'value' in kw
    assert 'timestamp' in kw
    assert 'old_value' in kw

    assert kw['value'] == value
    assert kw['old_value'] == value
    assert kw['timestamp'] == signal.timestamp

    # readback callback for soft signal
    info = dict(called=False)
    signal.subscribe(_sub_test, event_type=Signal.SUB_VALUE,
                     run=False)
    assert not info['called']
    signal.put(value + 1)
    assert info['called']

    signal.clear_sub(_sub_test)
    kw = info['kw']

    assert 'value' in kw
    assert 'timestamp' in kw
    assert 'old_value' in kw

    assert kw['value'] == value + 1
    assert kw['old_value'] == value
    assert kw['timestamp'] == signal.timestamp

    signal.trigger()
    signal.read()
    signal.describe()
    signal.read_configuration()
    signal.describe_configuration()

    eval(repr(signal))


def test_signal_copy():
    start_t = time.time()

    name = 'test'
    value = 10.0
    signal = Signal(name=name, value=value, timestamp=start_t)
    sig_copy = copy.copy(signal)

    assert signal.name == sig_copy.name
    assert signal.value == sig_copy.value
    assert signal.get() == sig_copy.get()
    assert signal.timestamp == sig_copy.timestamp


def test_rw_removal(cleanup, signal_test_ioc):
    # rw kwarg is no longer used
    with pytest.raises(RuntimeError):
        EpicsSignal(signal_test_ioc.pvs['read_only'], rw=False)

    with pytest.raises(RuntimeError):
        EpicsSignal(signal_test_ioc.pvs['read_only'], rw=True)


def test_epicssignal_readonly(cleanup, signal_test_ioc):
    signal = EpicsSignalRO(signal_test_ioc.pvs['read_only'])
    cleanup.add(signal)
    signal.wait_for_connection()
    signal.value

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


def test_epicssignal_readwrite_limits(cleanup, signal_test_ioc):
    signal = EpicsSignal(
        read_pv=signal_test_ioc.pvs['read_only'],
        write_pv=signal_test_ioc.pvs['read_write'], limits=True
    )
    cleanup.add(signal)

    signal.wait_for_connection()
    signal.check_value((signal.low_limit + signal.high_limit) / 2)

    with pytest.raises(ValueError):
        signal.check_value(None)

    with pytest.raises(ValueError):
        signal.check_value(signal.low_limit - 1)

    with pytest.raises(ValueError):
        signal.check_value(signal.high_limit + 1)


def test_epicssignal_readwrite(cleanup, signal_test_ioc):
    signal = EpicsSignal(
        read_pv=signal_test_ioc.pvs['read_only'],
        write_pv=signal_test_ioc.pvs['read_write'], limits=True
    )
    cleanup.add(signal)

    signal.wait_for_connection()
    assert signal.setpoint_pvname == signal_test_ioc.pvs['read_write']
    assert signal.pvname == signal_test_ioc.pvs['read_only']
    signal.value

    signal._update_rate = 2
    time.sleep(0.2)

    value = 10
    signal.value = value
    signal.setpoint = value
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
    def update_cb(value=None, **kwargs):
        assert len(value) > 1

    signal = EpicsSignal(signal_test_ioc.pvs['waveform'], string=True)
    cleanup.add(signal)
    signal.wait_for_connection()

    sub = signal.subscribe(update_cb, event_type=signal.SUB_VALUE)
    assert len(signal.value) > 1
    signal.unsubscribe(sub)


def test_no_connection(cleanup, signal_test_ioc):
    sig = EpicsSignal('does_not_connect')
    cleanup.add(sig)

    with pytest.raises(TimeoutError):
        sig.wait_for_connection()

    sig = EpicsSignal('does_not_connect')
    cleanup.add(sig)

    with pytest.raises(TimeoutError):
        sig.put(0.0)

    with pytest.raises(TimeoutError):
        sig.get()

    sig = EpicsSignal(signal_test_ioc.pvs['read_only'], write_pv='does_not_connect')
    cleanup.add(sig)
    with pytest.raises(TimeoutError):
        sig.wait_for_connection()


def test_enum_strs(cleanup, signal_test_ioc):
    sig = EpicsSignal(signal_test_ioc.pvs['bool_enum'])
    cleanup.add(sig)
    sig.wait_for_connection()

    assert sig.enum_strs == ('Off', 'On')


def test_setpoint(cleanup, signal_test_ioc):
    sig = EpicsSignal(signal_test_ioc.pvs['read_write'])
    cleanup.add(sig)
    sig.wait_for_connection()

    sig.get_setpoint()
    sig.get_setpoint(as_string=True)


def test_epicssignalro():
    with pytest.raises(TypeError):
        # not in initializer parameters anymore
        EpicsSignalRO('test', write_pv='nope_sorry')


def test_describe(cleanup, signal_test_ioc):
    sig = EpicsSignal(signal_test_ioc.pvs['bool_enum'], name='my_pv')
    cleanup.add(sig)
    sig.wait_for_connection()

    sig.put(1)
    desc = sig.describe()['my_pv']
    assert desc['dtype'] == 'integer'
    assert desc['shape'] == []
    # assert 'precision' in desc
    assert desc['enum_strs'] == ['Off', 'On']
    assert 'upper_ctrl_limit' in desc
    assert 'lower_ctrl_limit' in desc

    sig = Signal(name='my_pv')
    sig.put('Off')
    desc = sig.describe()['my_pv']
    assert desc['dtype'] == 'string'
    assert desc['shape'] == []

    sig.put(3.14)
    desc = sig.describe()['my_pv']
    assert desc['dtype'] == 'number'
    assert desc['shape'] == []

    import numpy as np
    sig.put(np.array([1, ]))
    desc = sig.describe()['my_pv']
    assert desc['dtype'] == 'array'
    assert desc['shape'] == [1, ]


def test_set_method():
    sig = Signal(name='sig')

    st = sig.set(28)
    wait(st)
    assert st.done
    assert st.success
    assert sig.get() == 28


def test_soft_derived():
    timestamp = 1.0
    value = 'q'
    original = Signal(name='original', timestamp=timestamp, value=value)

    cb_values = []

    def callback(value=None, **kwargs):
        cb_values.append(value)

    derived = DerivedSignal(derived_from=original, name='derived')
    derived.subscribe(callback, event_type=derived.SUB_VALUE)

    assert derived.timestamp == timestamp
    assert derived.get() == value
    assert derived.timestamp == timestamp
    assert derived.describe()[derived.name]['derived_from'] == original.name
    assert derived.write_access == original.write_access
    assert derived.read_access == original.read_access

    new_value = 'r'
    derived.put(new_value)
    assert original.get() == new_value
    assert derived.get() == new_value
    assert derived.timestamp == original.timestamp
    assert derived.limits == original.limits

    copied = copy.copy(derived)
    assert copied.derived_from.value == original.value
    assert copied.derived_from.timestamp == original.timestamp
    assert copied.derived_from.name == original.name

    derived.put('s')
    assert cb_values == ['r', 's']

    called = []

    def meta_callback(*, connected, read_access, write_access, **kw):
        called.append(('meta', connected, read_access, write_access))

    derived.subscribe(meta_callback, event_type=derived.SUB_META, run=False)

    original._metadata['write_access'] = False
    original._run_subs(sub_type='meta', timestamp=None, **original._metadata)

    assert called == [('meta', True, True, False)]


def test_epics_signal_derived(cleanup, signal_test_ioc):
    signal = EpicsSignalRO(
        read_pv=signal_test_ioc.pvs['read_only'],
        name='original',
    )
    cleanup.add(signal)

    signal.wait_for_connection()
    assert signal.connected
    assert signal.read_access
    assert not signal.write_access

    derived = DerivedSignal(derived_from=signal, name='derived')
    derived.wait_for_connection()

    assert derived.connected
    assert derived.read_access
    assert not derived.write_access

    assert derived.timestamp == signal.timestamp
    assert derived.get() == signal.value


@pytest.mark.parametrize('put_complete', [True, False])
def test_epicssignal_set(cleanup, motor, put_complete):
    sim_pv = EpicsSignal(write_pv=motor.user_setpoint.pvname,
                         read_pv=motor.user_readback.pvname,
                         put_complete=put_complete)
    cleanup.add(sim_pv)
    sim_pv.wait_for_connection()

    logging.getLogger('ophyd.signal').setLevel(logging.DEBUG)
    logging.getLogger('ophyd.utils.epics_pvs').setLevel(logging.DEBUG)
    print('tolerance=', sim_pv.tolerance)
    assert sim_pv.tolerance is not None

    start_pos = sim_pv.get()

    # move to +0.2 and check the status object
    target = sim_pv.get() + 0.2
    st = sim_pv.set(target, timeout=1, settle_time=0.001)
    wait(st, timeout=5)
    assert st.done
    assert st.success
    print('status 1', st)
    assert abs(target - sim_pv.get()) < 0.05

    # move back to -0.2, forcing a timeout with a low value
    target = sim_pv.get() - 0.2
    st = sim_pv.set(target, timeout=1e-6)
    time.sleep(0.5)
    print('status 2', st)
    assert st.done
    assert not st.success

    # keep the axis in position
    st = sim_pv.set(start_pos)
    wait(st, timeout=5)


def test_epicssignal_alarm_status(cleanup, motor):
    sig = EpicsSignal(write_pv=motor.user_setpoint.setpoint_pvname,
                      read_pv=motor.user_readback.pvname)
    cleanup.add(sig)
    sig.wait_for_connection()
    sig.alarm_status
    sig.alarm_severity
    sig.setpoint_alarm_status
    sig.setpoint_alarm_severity


def test_epicssignalro_alarm_status(cleanup, motor):
    sig = EpicsSignalRO(motor.user_readback.pvname)
    cleanup.add(sig)
    sig.wait_for_connection()
    sig.alarm_status
    sig.alarm_severity


def test_hints(cleanup, motor):
    sig = EpicsSignalRO(motor.user_readback.pvname)
    cleanup.add(sig)
    assert sig.hints == {'fields': [sig.name]}
