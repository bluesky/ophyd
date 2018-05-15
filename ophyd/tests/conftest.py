import sys
import time
import random
import logging
import pytest
import threading
from functools import wraps
import weakref

import numpy as np
import numpy.testing

from ophyd import get_cl, set_cl

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

        self.callbacks = dict()

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
            self._connected = True

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


class AssertTools:
    @staticmethod
    def assertEquals(a, b):
        assert a == b

    @staticmethod
    def assertEqual(a, b):
        assert a == b

    @staticmethod
    def assertNotEqual(a, b):
        assert a != b

    @staticmethod
    def assertRaises(Etype, func, *args, **kwargs):
        with pytest.raises(Etype):
            func(*args, **kwargs)

    @staticmethod
    def assertIn(val, target):
        assert val in target

    @staticmethod
    def assertIs(a, b):
        assert a is b

    @staticmethod
    def assertTrue(v):
        assert v

    @staticmethod
    def assertFalse(v):
        assert not v

    @staticmethod
    def assertGreater(a, b):
        assert a > b

    @staticmethod
    def assertAlmostEqual(a, b):
        numpy.testing.assert_almost_equal(a, b)

    @staticmethod
    def skipTest(msg):
        pytest.skip(msg)
