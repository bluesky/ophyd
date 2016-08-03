import sys
import logging
import unittest
import threading
import random
import time
import copy
import pytest
from functools import wraps
import weakref

import numpy as np
import epics

from ophyd.signal import (Signal, EpicsSignal, EpicsSignalRO, DerivedSignal)
from ophyd.utils import ReadOnlyError
from ophyd.status import wait

logger = logging.getLogger(__name__)


_FAKE_PV_LIST = []


class FakeEpicsPV(object):
    _connect_delay = (0.05, 0.1)
    _update_rate = 0.1
    fake_values = (0.1, 0.2, 0.3)
    _pv_idx = 0
    auto_monitor = True

    def __init__(self, pvname, form=None,
                 callback=None, connection_callback=None,
                 auto_monitor=True, enum_strs=None,
                 **kwargs):

        global _FAKE_PV_LIST
        _FAKE_PV_LIST.append(self)

        self._pvname = pvname
        self._connection_callback = connection_callback
        self._form = form
        self._auto_monitor = auto_monitor
        self._value = self.fake_values[0]
        self._connected = False
        self._running = True
        self.enum_strs = enum_strs
        FakeEpicsPV._pv_idx += 1
        self._idx = FakeEpicsPV._pv_idx

        self._update = True

        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._update_loop)
        self._thread.daemon = True
        self._thread.start()

        # callbacks mechanism copied from pyepics
        # ... but tweaked with a weakvaluedictionary so PV objects get
        # destructed
        self.callbacks = weakref.WeakValueDictionary()

        if callback:
            self.add_callback(callback)

    def __del__(self):
        self.clear_callbacks()
        self._running = False

        try:
            self._thread.join()
            self._thread = None
        except Exception:
            pass

    def get_timevars(self):
        pass

    def get_ctrlvars(self):
        pass

    @property
    def connected(self):
        return self._connected

    def wait_for_connection(self, timeout=None):
        if self._pvname in ('does_not_connect', ):
            return False

        while not self._connected:
            time.sleep(0.05)

        return True

    def _update_loop(self):
        time.sleep(random.uniform(*self._connect_delay))
        if self._connection_callback is not None:
            self._connection_callback(pvname=self._pvname, conn=True, pv=self)

        if self._pvname in ('does_not_connect', ):
            return

        self._connected = True
        last_value = None

        while self._running:
            with self._lock:
                if self._update:
                    self._value = random.choice(self.fake_values)

                if self._value != last_value:
                    sys.stdout.flush()
                    self.run_callbacks()
                    last_value = self._value

                time.sleep(self._update_rate)

            time.sleep(0.01)

    @property
    def lower_ctrl_limit(self):
        return min(self.fake_values)

    @property
    def upper_ctrl_limit(self):
        return max(self.fake_values)

    def run_callbacks(self):
        for index in sorted(list(self.callbacks.keys())):
            if not self._running:
                break
            self.run_callback(index)

    def run_callback(self, index):
        fcn = self.callbacks[index]
        kwd = dict(pvname=self._pvname,
                   count=1,
                   nelm=1,
                   type=None,
                   typefull=None,
                   ftype=None,
                   access='rw',
                   chid=self._idx,
                   read_access=True,
                   write_access=True,
                   value=self.value,
                   )

        kwd['cb_info'] = (index, self)
        if hasattr(fcn, '__call__'):
            fcn(**kwd)

    def add_callback(self, callback=None, index=None, run_now=False,
                     with_ctrlvars=True):
        if hasattr(callback, '__call__'):
            if index is None:
                index = 1
                if len(self.callbacks) > 0:
                    index = 1 + max(self.callbacks.keys())
            self.callbacks[index] = callback

        if run_now:
            if self.connected:
                self.run_callback(index)
        return index

    def remove_callback(self, index=None):
        if index in self.callbacks:
            self.callbacks.pop(index)

    def clear_callbacks(self):
        self.callbacks.clear()

    @property
    def precision(self):
        return 0

    @property
    def units(self):
        return str(None)

    @property
    def timestamp(self):
        return time.time()

    @property
    def pvname(self):
        return self._pvname

    @property
    def value(self):
        return self._value

    def __repr__(self):
        return '<FakePV %s value=%s>' % (self._pvname, self.value)

    def get(self, as_string=False, use_numpy=False,
            use_monitor=False):
        if as_string:

            if isinstance(self.value, list):
                if self.enum_strs:
                    return [self.enum_strs[_] for _ in self.value]
                return list(self.value)
            if isinstance(self.value, str):
                return self.value
            else:
                if self.enum_strs:
                    return self.enum_strs[self.value]
                return str(self.value)
        elif use_numpy:
            return np.array(self.value)
        else:
            return self.value

    def put(self, value, wait=False, timeout=30.0,
            use_complete=False, callback=None, callback_data=None):

        with self._lock:
            self._update = False
            self._value = value


class FakeEpicsWaveform(FakeEpicsPV):
    strings = ['abcd', 'efgh', 'ijkl']
    fake_values = [[ord(c) for c in s] + [0]
                   for s in strings]
    auto_monitor = False
    form = 'time'


def _cleanup_fake_pvs():
    pvs = list(_FAKE_PV_LIST)
    del _FAKE_PV_LIST[:]

    for pv in pvs:
        pv.clear_callbacks()
        pv._running = False
        pv._connection_callback = None

    for pv in pvs:
        try:
            pv._thread.join()
            pv._thread = None
        except Exception:
            pass


def using_fake_epics_pv(fcn):
    @wraps(fcn)
    def wrapped(*args, **kwargs):
        pv_backup = epics.PV
        epics.PV = FakeEpicsPV
        try:
            return fcn(*args, **kwargs)
        finally:
            epics.PV = pv_backup
            _cleanup_fake_pvs()

    return wrapped


def using_fake_epics_waveform(fcn):
    @wraps(fcn)
    def wrapped(*args, **kwargs):
        pv_backup = epics.PV
        epics.PV = FakeEpicsWaveform
        try:
            return fcn(*args, **kwargs)
        finally:
            epics.PV = pv_backup
            _cleanup_fake_pvs()

    return wrapped


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

    pv = epics.PV(pvname, callback=value_cb, connection_callback=conn,
                  )

    if not pv.wait_for_connection():
        raise ValueError('should return True on connection')

    assert pv.pvname == pvname

    pv._update_rate = 0.5
    time.sleep(0.2)

    assert info['conn']
    assert info['value']
    assert info['value_kw']['value'] == pv.value


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

    signal.subscribe(_sub_test, run=False)
    assert not info['called']

    signal.value = value
    signal.clear_sub(_sub_test)

    signal.subscribe(_sub_test, run=False)
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

    signal.subscribe(update_cb)
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
    sig = Signal()

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
    derived.subscribe(callback)

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
    wait(st)
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
    wait(st)


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


from . import main
is_main = (__name__ == '__main__')
main(is_main)
