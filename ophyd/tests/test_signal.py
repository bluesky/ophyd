import logging
import time
import copy
import pytest
from ophyd import get_cl

from ophyd.signal import (Signal, EpicsSignal, EpicsSignalRO, DerivedSignal)
from ophyd.utils import ReadOnlyError
from ophyd.status import wait

from .conftest import (FakeEpicsWaveform, using_fake_epics_pv,
                       using_fake_epics_waveform)
logger = logging.getLogger(__name__)


@using_fake_epics_pv
def test_fakepv():
    pvname = 'fakepv_nowaythisexists' * 10

    info = dict(called=False)

    def conn(**kwargs):
        info['conn'] = True
        info['conn_kw'] = kwargs

    def value_cb(**kwargs):
        info['value'] = True
        info['value_kw'] = kwargs
    cl = get_cl()
    pv = cl.get_pv(pvname, callback=value_cb, connection_callback=conn)

    if not pv.wait_for_connection():
        raise ValueError('should return True on connection')

    assert pv.pvname == pvname

    pv._update_rate = 0.5
    time.sleep(0.2)

    assert info['conn']
    assert info['value']
    assert info['value_kw']['value'] == pv.value


@using_fake_epics_pv
def test_fakepv_signal():
    sig = EpicsSignal(write_pv='XF:31IDA-OP{Tbl-Ax:X1}Mtr.VAL',
                      read_pv='XF:31IDA-OP{Tbl-Ax:X1}Mtr.RBV')
    st = sig.set(1)

    for j in range(10):
        if st.done:
            break
        time.sleep(.1)

    assert st.done


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


def test_rw_removal():
    # rw kwarg is no longer used
    with pytest.raises(RuntimeError):
        EpicsSignal('readpv', rw=False)

    with pytest.raises(RuntimeError):
        EpicsSignal('readpv', rw=True)


@using_fake_epics_pv
def test_epicssignal_readonly():
    signal = EpicsSignalRO('readpv')
    signal.wait_for_connection()
    signal.value

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


@using_fake_epics_pv
def test_epicssignal_readwrite_limits():
    signal = EpicsSignal('readpv', write_pv='readpv', limits=True)

    signal.wait_for_connection()
    signal.check_value((signal.low_limit + signal.high_limit) / 2)

    try:
        signal.check_value(None)
    except ValueError:
        pass
    else:
        raise ValueError('value=None')

    try:
        signal.check_value(signal.low_limit - 1)
    except ValueError:
        pass
    else:
        raise ValueError('lower limit %s' % (signal.limits, ))

    try:
        signal.check_value(signal.high_limit + 1)
    except ValueError:
        pass
    else:
        raise ValueError('upper limit')


@using_fake_epics_pv
def test_epicssignal_readwrite():
    signal = EpicsSignal('readpv', write_pv='writepv')

    signal.wait_for_connection()
    assert signal.setpoint_pvname == 'writepv'
    assert signal.pvname == 'readpv'
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


@using_fake_epics_waveform
def test_epicssignal_waveform():
    def update_cb(value=None, **kwargs):
        assert value in FakeEpicsWaveform.strings

    signal = EpicsSignal('readpv', string=True)

    signal.wait_for_connection()

    signal.subscribe(update_cb, event_type=signal.SUB_VALUE)
    assert signal.value in FakeEpicsWaveform.strings


@using_fake_epics_pv
def test_no_connection():
    # special case in FakeEpicsPV that returns false in wait_for_connection
    sig = EpicsSignal('does_not_connect')
    pytest.raises(TimeoutError, sig.wait_for_connection)

    sig = EpicsSignal('does_not_connect')
    pytest.raises(TimeoutError, sig.put, 0.0)
    pytest.raises(TimeoutError, sig.get)

    sig = EpicsSignal('connects', write_pv='does_not_connect')
    pytest.raises(TimeoutError, sig.wait_for_connection)


@using_fake_epics_pv
def test_enum_strs():
    sig = EpicsSignal('connects')
    sig.wait_for_connection()

    enums = ['enum_strs']

    # hack this onto the FakeEpicsPV
    sig._read_pv.enum_strs = enums

    assert sig.enum_strs == enums


@using_fake_epics_pv
def test_setpoint():
    sig = EpicsSignal('connects')
    sig.wait_for_connection()

    sig.get_setpoint()
    sig.get_setpoint(as_string=True)


def test_epicssignalro():
    # not in initializer parameters anymore
    pytest.raises(TypeError, EpicsSignalRO, 'test',
                  write_pv='nope_sorry')


@using_fake_epics_pv
def test_describe():
    sig = EpicsSignal('my_pv')
    sig._write_pv.enum_strs = ('enum1', 'enum2')
    sig.wait_for_connection()

    sig.put(1)
    desc = sig.describe()['my_pv']
    assert desc['dtype'] == 'integer'
    assert desc['shape'] == []
    assert 'precision' in desc
    assert 'enum_strs' in desc
    assert 'upper_ctrl_limit' in desc
    assert 'lower_ctrl_limit' in desc

    sig.put('foo')
    desc = sig.describe()['my_pv']
    assert desc['dtype'] == 'string'
    assert desc['shape'] == []

    sig.put(3.14)
    desc = sig.describe()['my_pv']
    assert desc['dtype'] == 'number'
    assert desc['shape'] == []

    import numpy as np
    sig.put(np.array([1,]))
    desc = sig.describe()['my_pv']
    assert desc['dtype'] == 'array'
    assert desc['shape'] == [1,]


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
        nonlocal cb_values
        cb_values.append(value)

    derived = DerivedSignal(derived_from=original, name='derived')
    derived.subscribe(callback, event_type=derived.SUB_VALUE)

    assert derived.timestamp == timestamp
    assert derived.get() == value
    assert derived.timestamp == timestamp
    assert derived.describe()[derived.name]['derived_from'] == original.name

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


@using_fake_epics_pv
def test_epics_signal_derived():
    signal = EpicsSignalRO('fakepv', name='original')

    derived = DerivedSignal(derived_from=signal, name='derived')
    derived.wait_for_connection()

    derived.connected

    # race condition with the FakeEpicsPV update loop, can't really test
    # assert derived.timestamp == signal.timestamp
    # assert derived.get() == signal.value


@pytest.mark.parametrize('put_complete', [True, False])
def test_epicssignal_set(put_complete):
    sim_pv = EpicsSignal(write_pv='XF:31IDA-OP{Tbl-Ax:X1}Mtr.VAL',
                         read_pv='XF:31IDA-OP{Tbl-Ax:X1}Mtr.RBV',
                         put_complete=put_complete)
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
    time.sleep(0.1)
    print('status 2', st)
    assert st.done
    assert not st.success

    # keep the axis in position
    st = sim_pv.set(start_pos)
    wait(st, timeout=5)



def test_epicssignal_alarm_status():
    sig = EpicsSignal(write_pv='XF:31IDA-OP{Tbl-Ax:X1}Mtr.VAL',
                      read_pv='XF:31IDA-OP{Tbl-Ax:X1}Mtr.RBV')
    sig.alarm_status
    sig.alarm_severity
    sig.setpoint_alarm_status
    sig.setpoint_alarm_severity


def test_epicssignalro_alarm_status():
    sig = EpicsSignalRO('XF:31IDA-OP{Tbl-Ax:X1}Mtr.RBV')
    sig.alarm_status
    sig.alarm_severity


def test_hints():
    sig = EpicsSignalRO('XF:31IDA-OP{Tbl-Ax:X1}Mtr.RBV')
    assert sig.hints == {'fields': [sig.name]}
