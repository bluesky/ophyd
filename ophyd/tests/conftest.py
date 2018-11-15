import logging
import random
import sys
import threading
import time
import uuid
import weakref

import pytest
import numpy as np
import numpy.testing

from types import SimpleNamespace
from functools import wraps

from ophyd import (get_cl, set_cl, EpicsMotor, Signal, EpicsSignal,
                   EpicsSignalRO, Component as Cpt, MotorBundle)
from ophyd.utils.epics_pvs import (AlarmSeverity, AlarmStatus)
from caproto.tests.conftest import run_example_ioc

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
                 access_callback=None,
                 **kwargs):

        self.callbacks = dict()

        global _FAKE_PV_LIST
        _FAKE_PV_LIST.append(self)

        self._pvname = pvname
        self._access_callback = access_callback
        self._connection_callback = connection_callback
        self._form = form
        self._auto_monitor = auto_monitor
        self._value = self.fake_values[0]
        self.connected = False
        self._running = True
        self.enum_strs = enum_strs
        FakeEpicsPV._pv_idx += 1
        self._idx = FakeEpicsPV._pv_idx

        self._update = True

        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._update_loop)
        self._thread.daemon = True
        self._thread.start()

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

    def wait_for_connection(self, timeout=None):
        if self._pvname in ('does_not_connect', ):
            return False

        while not self.connected:
            time.sleep(0.05)

        return True

    def _update_loop(self):
        time.sleep(random.uniform(*self._connect_delay))
        if self._pvname in ('does_not_connect', ):
            return

        if self._connection_callback is not None:
            self._connection_callback(pvname=self._pvname, conn=True, pv=self)
            # update connection status AFTER the callback - mirroring pyepics
            self.connected = True

        if self._access_callback is not None:
            self._access_callback(True, True, pv=self)

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
        fcn = self.callbacks[index]()
        if fcn is None:
            self.remove_callback(index)
            return

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
            try:
                self.callbacks[index] = weakref.WeakMethod(callback)
            except TypeError:
                self.callbacks[index] = weakref.ref(callback)

        if run_now:
            if self.connected:
                self.run_callback(index)
        return index

    def remove_callback(self, index=None):
        self.callbacks.pop(index, None)

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

    def force_read_access_rights(self):
        pass


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
        cl = get_cl()
        get_pv_backup = cl.get_pv

        def _fake_get_pv(pvname, form='time', connect=False,
                         context=False, timout=5.0, **kw):
            return FakeEpicsPV(pvname, form=form, **kw)
        cl.get_pv = _fake_get_pv
        try:
            return fcn(*args, **kwargs)
        finally:
            cl.get_pv = get_pv_backup
            _cleanup_fake_pvs()

    return wrapped


def using_fake_epics_waveform(fcn):
    @wraps(fcn)
    def wrapped(*args, **kwargs):
        cl = get_cl()
        get_pv_backup = cl.get_pv

        def _fake_get_pv(pvname, form='time', connect=False,
                         context=False, timout=5.0, **kw):
            return FakeEpicsWaveform(pvname, form=form, **kw)

        cl.get_pv = _fake_get_pv
        try:
            return fcn(*args, **kwargs)
        finally:
            cl.get_pv = get_pv_backup
            _cleanup_fake_pvs()

    return wrapped


@pytest.fixture()
def hw():
    from ophyd.sim import hw
    return hw()


@pytest.fixture(params=['caproto', 'pyepics'], autouse=True)
def cl_selector(request):
    cl_name = request.param
    if cl_name == 'caproto':
        pytest.importorskip('caproto')
    elif cl_name == 'pyepics':
        pytest.importorskip('epics')
    set_cl(cl_name)
    yield
    set_cl()


class CustomAlarmEpicsSignalRO(EpicsSignalRO):
    alarm_status = AlarmStatus.NO_ALARM
    alarm_severity = AlarmSeverity.NO_ALARM


class TestEpicsMotor(EpicsMotor):
    user_readback = Cpt(CustomAlarmEpicsSignalRO, '.RBV', kind='hinted')
    high_limit_switch = Cpt(Signal, value=0, kind='omitted')
    low_limit_switch = Cpt(Signal, value=0, kind='omitted')
    direction_of_travel = Cpt(Signal, value=0, kind='omitted')
    high_limit_value = Cpt(EpicsSignal, '.HLM', kind='config')
    low_limit_value = Cpt(EpicsSignal, '.LLM', kind='config')

    @user_readback.sub_value
    def _pos_changed(self, timestamp=None, value=None, **kwargs):
        '''Callback from EPICS, indicating a change in position'''
        super()._pos_changed(timestamp=timestamp, value=value, **kwargs)


@pytest.fixture(scope='function')
def motor(request, cleanup):
    sim_pv = 'XF:31IDA-OP{Tbl-Ax:X1}Mtr'

    motor = TestEpicsMotor(sim_pv, name='epicsmotor', settle_time=0.1,
                           timeout=10.0)
    cleanup.add(motor)

    print('Created EpicsMotor:', motor)
    motor.wait_for_connection()
    motor.low_limit_value.put(-100, wait=True)
    motor.high_limit_value.put(100, wait=True)

    while motor.motor_done_move.get() != 1:
        print('Waiting for {} to stop moving...'.format(motor))
        time.sleep(0.5)

    return motor


@pytest.fixture(scope='function')
def prefix():
    'Random PV prefix for a server'
    return str(uuid.uuid4())[:8] + ':'


@pytest.fixture(scope='function')
def fake_motor_ioc(prefix, request):
    name = 'Fake motor IOC'
    pvs = dict(setpoint=f'{prefix}setpoint',
               readback=f'{prefix}readback',
               moving=f'{prefix}moving',
               actuate=f'{prefix}actuate',
               stop=f'{prefix}stop',
               step_size=f'{prefix}step_size',
               )

    process = run_example_ioc('ophyd.tests.fake_motor_ioc',
                              request=request,
                              pv_to_check=pvs['setpoint'],
                              args=('--prefix', prefix,))
    return SimpleNamespace(process=process, prefix=prefix, name=name, pvs=pvs,
                           type='caproto')


@pytest.fixture(scope='function')
def signal_test_ioc(prefix, request):
    name = 'test_signal IOC'
    pvs = dict(read_only=f'{prefix}read_only',
               read_write=f'{prefix}read_write',
               waveform=f'{prefix}waveform',
               bool_enum=f'{prefix}bool_enum',
               )

    process = run_example_ioc('ophyd.tests.signal_ioc',
                              request=request,
                              pv_to_check=pvs['read_only'],
                              args=('--prefix', prefix,))
    return SimpleNamespace(process=process, prefix=prefix, name=name, pvs=pvs,
                           type='caproto')


@pytest.fixture(scope='function')
def cleanup(request):
    'Destroy all items added to the list during the finalizer'
    items = []

    class Cleaner:
        def add(self, item):
            items.append(item)

    def clean():
        for item in items:
            print('Destroying', item.name)
            item.destroy()
        items.clear()

    request.addfinalizer(clean)
    return Cleaner()
