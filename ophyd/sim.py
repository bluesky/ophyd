import asyncio
import copy
import inspect
import itertools
import logging
from functools import partial

import numpy as np
import os
import random
import threading
import time as ttime
import uuid
import weakref

from collections import deque, OrderedDict
from tempfile import mkdtemp

from .signal import Signal, SignalRO, EpicsSignal, EpicsSignalRO
from .areadetector.base import EpicsSignalWithRBV
from .status import DeviceStatus, StatusBase
from .device import (Device, Component as Cpt,
                     DynamicDeviceComponent as DDCpt, Kind)
from types import SimpleNamespace
from .pseudopos import (PseudoPositioner, PseudoSingle,
                        real_position_argument, pseudo_position_argument)
from .positioner import SoftPositioner
from .utils import ReadOnlyError, LimitError
from .log import logger


# two convenience functions 'vendored' from bluesky.utils

def new_uid():
    return str(uuid.uuid4())


def short_uid(label=None, truncate=6):
    "Return a readable but unique id like 'label-fjfi5a'"
    if label:
        return '-'.join([label, new_uid()[:truncate]])
    else:
        return new_uid()[:truncate]


class NullStatus(StatusBase):
    "A simple Status object that is always immediately done, successfully."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._finished(success=True)


class EnumSignal(Signal):
    def __init__(self, *args, value=0, enum_strings, **kwargs):
        super().__init__(*args, value=0, **kwargs)
        self._enum_strs = tuple(enum_strings)
        self._metadata['enum_strs'] = tuple(enum_strings)
        self.put(value)

    def put(self, value, **kwargs):
        if value in self._enum_strs:
            value = self._enum_strs.index(value)
        elif isinstance(value, str):
            err = f'{value} not in enum strs {self._enum_strs}'
            raise ValueError(err)
        return super().put(value, **kwargs)

    def get(self, *, as_string=True, **kwargs):
        """
        Implement getting as enum strings
        """
        value = super().get()

        if as_string:
            if self._enum_strs is not None and isinstance(value, int):
                return self._enum_strs[value]
            elif value is not None:
                return str(value)
        return value

    def describe(self):
        desc = super().describe()
        desc[self.name]['enum_strs'] = self._enum_strs
        return desc


class SynSignal(Signal):
    """
    A synthetic Signal that evaluates a Python function when triggered.

    Parameters
    ----------
    func : callable, optional
        This function sets the signal to a new value when it is triggered.
        Expected signature: ``f() -> value``.
        By default, triggering the signal does not change the value.
    name : string, keyword only
    exposure_time : number, optional
        Seconds of delay when triggered (simulated 'exposure time'). Default is
        0.
    precision : integer, optional
        Digits of precision. Default is 3.
    parent : Device, optional
        Used internally if this Signal is made part of a larger Device.
    kind : a member the Kind IntEnum (or equivalent integer), optional
        Default is Kind.normal. See Kind for options.
    loop : asyncio.EventLoop, optional
        used for ``subscribe`` updates; uses ``asyncio.get_event_loop()`` if
        unspecified
    """
    # This signature is arranged to mimic the signature of EpicsSignal, where
    # the Python function (func) takes the place of the PV.
    def __init__(self, func=None, *,
                 name,  # required, keyword-only
                 exposure_time=0,
                 precision=3,
                 parent=None,
                 labels=None,
                 kind=None,
                 loop=None,
                 **kwargs):
        if func is None:
            # When triggered, just put the current value.
            func = self.get
            # Initialize readback with a None value
            self._readback = None
        if loop is None:
            loop = asyncio.get_event_loop()
        self._func = func
        self.exposure_time = exposure_time
        self.precision = precision
        self.loop = loop
        super().__init__(value=self._func(), timestamp=ttime.time(), name=name,
                         parent=parent, labels=labels, kind=kind, **kwargs)
        self._metadata.update(
            connected=True,
        )

        self.log.info(self)

    def describe(self):
        res = super().describe()
        # There should be only one key here, but for the sake of generality....
        for k in res:
            res[k]['precision'] = self.precision
        return res

    def trigger(self):
        self.log.info('trigger %s', self)

        delay_time = self.exposure_time
        if delay_time:
            self.log.info('%s delay_time is %d', self, delay_time)
            st = DeviceStatus(device=self)
            if self.loop.is_running():

                def update_and_finish():
                    self.log.info('update_and_finish %s', self)
                    self.put(self._func())
                    st._finished()

                self.loop.call_later(delay_time, update_and_finish)
            else:

                def sleep_and_finish():
                    self.log.info('sleep_and_finish %s', self)
                    ttime.sleep(delay_time)
                    self.put(self._func())
                    st._finished()

                threading.Thread(target=sleep_and_finish, daemon=True).start()
            return st
        else:
            self.put(self._func())
            return NullStatus()

    def sim_set_func(self, func):
        """
        Update the SynSignal function to set a new value on trigger.
        """
        self._func = func


class SynSignalRO(SynSignal):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._metadata.update(
            connected=True,
            write_access=False,
        )

    def put(self, value, *, timestamp=None, force=False):
        msg = f"{self}.put(value={value}, timestamp={timestamp}, force={force})"
        self.log.error(msg)
        raise ReadOnlyError(msg)

    def set(self, value, *, timestamp=None, force=False):
        msg = f"{self} is readonly"
        self.log.error(msg)
        raise ReadOnlyError(msg)


class SynPeriodicSignal(SynSignal):
    """
    A synthetic Signal that evaluates a Python function periodically.

    Parameters
    ----------
    func : callable, optional
        This function sets the signal to a new value when it is triggered.
        Expected signature: ``f() -> value``.
        By default, triggering the signal generates white noise on [0, 1].
    name : string, keyword only
    period : number, optional
        How often the Signal's value is updated in the background. Default is
        1 second.
    period_jitter : number, optional
        Random Gaussian variation of the period. Default is 1 second.
    exposure_time : number, optional
        Seconds of delay when triggered (simulated 'exposure time'). Default is
        0.
    parent : Device, optional
        Used internally if this Signal is made part of a larger Device.
    kind : a member the Kind IntEnum (or equivalent integer), optional
        Default is Kind.normal. See Kind for options.
    loop : asyncio.EventLoop, optional
        used for ``subscribe`` updates; uses ``asyncio.get_event_loop()`` if
        unspecified
    """
    def __init__(self, func=None, *,
                 name,  # required, keyword-only
                 period=1, period_jitter=1,
                 exposure_time=0,
                 parent=None,
                 labels=None,
                 kind=None,
                 loop=None,
                 **kwargs):
        if func is None:
            func = np.random.rand
        super().__init__(name=name, func=func,
                         exposure_time=exposure_time,
                         parent=parent, labels=labels, kind=kind, loop=loop,
                         **kwargs)

        def periodic_update(ref, period, period_jitter):
            while True:
                signal = ref()
                if not signal:
                    # Our target Signal has been garbage collected. Shut
                    # down the Thread.
                    return
                signal.put(signal._func())
                del signal
                # Sleep for period +/- period_jitter.
                ttime.sleep(
                    max(period + period_jitter * np.random.randn(), 0))

        self.__thread = threading.Thread(target=periodic_update,
                                         daemon=True,
                                         args=(weakref.ref(self),
                                               period,
                                               period_jitter))
        self.__thread.start()


class _ReadbackSignal(Signal):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._metadata.update(
            connected=True,
            write_access=False,
        )

    def get(self):
        self._readback = self.parent.sim_state['readback']
        return self._readback

    def describe(self):
        res = super().describe()
        # There should be only one key here, but for the sake of
        # generality....
        for k in res:
            res[k]['precision'] = self.parent.precision
        return res

    @property
    def timestamp(self):
        '''Timestamp of the readback value'''
        return self.parent.sim_state['readback_ts']

    def put(self, value, *, timestamp=None, force=False):
        raise ReadOnlyError("The signal {} is readonly.".format(self.name))

    def set(self, value, *, timestamp=None, force=False):
        raise ReadOnlyError("The signal {} is readonly.".format(self.name))


class _SetpointSignal(Signal):
    def put(self, value, *, timestamp=None, force=False):
        self._readback = float(value)
        self.parent.set(float(value))

    def get(self):
        self._readback = self.parent.sim_state['setpoint']
        return self.parent.sim_state['setpoint']

    def describe(self):
        res = super().describe()
        # There should be only one key here, but for the sake of generality....
        for k in res:
            res[k]['precision'] = self.parent.precision
        return res

    @property
    def timestamp(self):
        '''Timestamp of the readback value'''
        return self.parent.sim_state['setpoint_ts']


class SynAxis(Device):
    """
    A synthetic settable Device mimic any 1D Axis (position, temperature).

    Parameters
    ----------
    name : string, keyword only
    readback_func : callable, optional
        When the Device is set to ``x``, its readback will be updated to
        ``f(x)``. This can be used to introduce random noise or a systematic
        offset.
        Expected signature: ``f(x) -> value``.
    value : object, optional
        The initial value. Default is 0.
    delay : number, optional
        Simulates how long it takes the device to "move". Default is 0 seconds.
    precision : integer, optional
        Digits of precision. Default is 3.
    parent : Device, optional
        Used internally if this Signal is made part of a larger Device.
    kind : a member the Kind IntEnum (or equivalent integer), optional
        Default is Kind.normal. See Kind for options.
    loop : asyncio.EventLoop, optional
        used for ``subscribe`` updates; uses ``asyncio.get_event_loop()`` if
        unspecified
    """
    readback = Cpt(_ReadbackSignal, value=None, kind='hinted')
    setpoint = Cpt(_SetpointSignal, value=None, kind='normal')

    velocity = Cpt(Signal, value=1, kind='config')
    acceleration = Cpt(Signal, value=1, kind='config')

    unused = Cpt(Signal, value=1, kind='omitted')

    SUB_READBACK = 'readback'
    _default_sub = SUB_READBACK

    def __init__(self, *,
                 name,
                 readback_func=None, value=0, delay=0,
                 precision=3,
                 parent=None,
                 labels=None,
                 kind=None,
                 loop=None,
                 **kwargs):
        if readback_func is None:
            def readback_func(x):
                return x
        if loop is None:
            loop = asyncio.get_event_loop()
        self.sim_state = {}
        self._readback_func = readback_func
        self.delay = delay
        self.precision = precision
        self.loop = loop

        # initialize values
        self.sim_state['setpoint'] = value
        self.sim_state['setpoint_ts'] = ttime.time()
        self.sim_state['readback'] = readback_func(value)
        self.sim_state['readback_ts'] = ttime.time()

        super().__init__(name=name, parent=parent, labels=labels, kind=kind,
                         **kwargs)
        self.readback.name = self.name

    def set(self, value):
        old_setpoint = self.sim_state['setpoint']
        self.sim_state['setpoint'] = value
        self.sim_state['setpoint_ts'] = ttime.time()
        self.setpoint._run_subs(sub_type=self.setpoint.SUB_VALUE,
                                old_value=old_setpoint,
                                value=self.sim_state['setpoint'],
                                timestamp=self.sim_state['setpoint_ts'])

        def update_state():
            old_readback = self.sim_state['readback']
            self.sim_state['readback'] = self._readback_func(value)
            self.sim_state['readback_ts'] = ttime.time()
            self.readback._run_subs(sub_type=self.readback.SUB_VALUE,
                                    old_value=old_readback,
                                    value=self.sim_state['readback'],
                                    timestamp=self.sim_state['readback_ts'])
            self._run_subs(sub_type=self.SUB_READBACK,
                           old_value=old_readback,
                           value=self.sim_state['readback'],
                           timestamp=self.sim_state['readback_ts'])

        if self.delay:
            st = DeviceStatus(device=self)
            if self.loop.is_running():

                def update_and_finish():
                    update_state()
                    st._finished()

                self.loop.call_later(self.delay, update_and_finish)
            else:

                def sleep_and_finish():
                    ttime.sleep(self.delay)
                    update_state()
                    st._finished()

                threading.Thread(target=sleep_and_finish, daemon=True).start()
            return st
        else:
            update_state()
            return NullStatus()

    @property
    def position(self):
        return self.readback.get()


class SynAxisEmptyHints(SynAxis):
    @property
    def hints(self):
        return {}


class SynAxisNoHints(SynAxis):
    readback = Cpt(_ReadbackSignal, value=None, kind='omitted')
    @property
    def hints(self):
        raise AttributeError


class SynGauss(Device):
    """
    Evaluate a point on a Gaussian based on the value of a motor.

    Parameters
    ----------
    name : string
    motor : Device
    motor_field : string
    center : number
        center of peak
    Imax : number
        max intensity of peak
    sigma : number, optional
        Default is 1.
    noise : {'poisson', 'uniform', None}, optional
        Add noise to the gaussian peak.
    noise_multiplier : float, optional
        Only relevant for 'uniform' noise. Multiply the random amount of
        noise by 'noise_multiplier'
    random_state : numpy random state object, optional
        np.random.RandomState(0), to generate random number with given seed

    Example
    -------
    motor = SynAxis(name='motor')
    det = SynGauss('det', motor, 'motor', center=0, Imax=1, sigma=1)
    """
    def _compute(self):
        m = self._motor.read()[self._motor_field]['value']
        # we need to do this one at a time because
        #   - self.read() may be screwed with by the user
        #   - self.get() would cause infinite recursion
        Imax = self.Imax.get()
        center = self.center.get()
        sigma = self.sigma.get()
        noise = self.noise.get()
        noise_multiplier = self.noise_multiplier.get()
        v = Imax * np.exp(-(m - center) ** 2 /
                          (2 * sigma ** 2))
        if noise == 'poisson':
            v = int(self.random_state.poisson(np.round(v), 1))
        elif noise == 'uniform':
            v += self.random_state.uniform(-1, 1) * noise_multiplier
        return v

    val = Cpt(SynSignal, kind='hinted')
    Imax = Cpt(Signal, value=10, kind='config')
    center = Cpt(Signal, value=0, kind='config')
    sigma = Cpt(Signal, value=1, kind='config')
    noise = Cpt(EnumSignal, value='none', kind='config',
                enum_strings=('none', 'poisson', 'uniform'))
    noise_multiplier = Cpt(Signal, value=1, kind='config')

    def __init__(self, name, motor, motor_field, center, Imax,
                 *, random_state=None,

                 **kwargs):
        set_later = {}
        for k in ('sigma', 'noise', 'noise_multiplier'):
            v = kwargs.pop(k, None)
            if v is not None:
                set_later[k] = v
        super().__init__(name=name, **kwargs)
        self._motor = motor
        self._motor_field = motor_field
        self.center.put(center)
        self.Imax.put(Imax)

        self.random_state = random_state or np.random
        self.val.name = self.name
        self.val.sim_set_func(self._compute)
        for k, v in set_later.items():
            getattr(self, k).put(v)

        self.trigger()

    def subscribe(self, *args, **kwargs):
        return self.val.subscribe(*args, **kwargs)

    def clear_sub(self, cb, event_type=None):
        return self.val.clear_sub(cb, event_type=event_type)

    def unsubscribe(self, cid):
        return self.val.unsubscribe(cid)

    def unsubscribe_all(self):
        return self.val.unsubscribe_all()

    def trigger(self, *args, **kwargs):
        return self.val.trigger(*args, **kwargs)

    @property
    def precision(self):
        return self.val.precision

    @precision.setter
    def precision(self, v):
        self.val.precision = v

    @property
    def exposure_time(self):
        return self.val.exposure_time

    @exposure_time.setter
    def exposure_time(self, v):
        self.val.exposure_time = v


class Syn2DGauss(Device):
    """
    Evaluate a point on a Gaussian based on the value of a motor.

    Parameters
    ----------
    name : str
        The name of the detector
    motor0 : SynAxis
        The 'x' coordinate of the 2-D gaussian blob
    motor_field0 : str
        The name field of the motor. Should be the key in motor0.describe()
    motor1 : SynAxis
        The 'y' coordinate of the 2-D gaussian blob
    motor_field1 : str
        The name field of the motor. Should be the key in motor1.describe()
    center : iterable, optional
        The center of the gaussian blob
        Defaults to (0,0)
    Imax : float, optional
        The intensity at `center`
        Defaults to 1
    sigma : float, optional
        Standard deviation for gaussian blob
        Defaults to 1
    noise : {'poisson', 'uniform', None}, optional
        Add noise to the gaussian peak..
        Defaults to None
    noise_multiplier : float, optional
        Only relevant for 'uniform' noise. Multiply the random amount of
        noise by 'noise_multiplier'
        Defaults to 1
    random_state : numpy random state object, optional
        np.random.RandomState(0), to generate random number with given seed

    Example
    -------
    motor = SynAxis(name='motor')
    det = SynGauss('det', motor, 'motor', center=0, Imax=1, sigma=1)
    """

    val = Cpt(SynSignal, kind='hinted')
    Imax = Cpt(Signal, value=10, kind='config')
    center = Cpt(Signal, value=0, kind='config')
    sigma = Cpt(Signal, value=1, kind='config')
    noise = Cpt(EnumSignal, value='none', kind='config',
                enum_strings=('none', 'poisson', 'uniform'))
    noise_multiplier = Cpt(Signal, value=1, kind='config')

    def _compute(self):
        x = self._motor0.read()[self._motor_field0]['value']
        y = self._motor1.read()[self._motor_field1]['value']
        m = np.array([x, y])
        Imax = self.Imax.get()
        center = self.center.get()
        sigma = self.sigma.get()
        noise = self.noise.get()
        noise_multiplier = self.noise_multiplier.get()
        v = Imax * np.exp(-np.sum((m - center) ** 2) / (2 * sigma ** 2))
        if noise == 'poisson':
            v = int(self.random_state.poisson(np.round(v), 1))
        elif noise == 'uniform':
            v += self.random_state.uniform(-1, 1) * noise_multiplier
        return v

    def __init__(self, name, motor0, motor_field0, motor1, motor_field1,
                 center, Imax, sigma=1, noise="none", noise_multiplier=1,
                 random_state=None, **kwargs):
        super().__init__(name=name, **kwargs)
        self._motor0 = motor0
        self._motor1 = motor1
        self._motor_field0 = motor_field0
        self._motor_field1 = motor_field1
        self.center.put(center)
        self.Imax.put(Imax)
        self.sigma.put(sigma)
        self.noise.put(noise)
        self.noise_multiplier.put(noise_multiplier)

        if random_state is None:
            random_state = np.random
        self.random_state = random_state
        self.val.name = self.name
        self.val.sim_set_func(self._compute)

    def trigger(self, *args, **kwargs):
        return self.val.trigger(*args, **kwargs)


class TrivialFlyer:
    """Trivial flyer that complies to the API but returns empty data."""
    name = 'trivial_flyer'
    parent = None

    def kickoff(self):
        return NullStatus()

    def describe_collect(self):
        return {'stream_name': {}}

    def read_configuration(self):
        return OrderedDict()

    def describe_configuration(self):
        return OrderedDict()

    def complete(self):
        return NullStatus()

    def collect(self):
        for i in range(100):
            yield {'data': {}, 'timestamps': {}, 'time': i, 'seq_num': i}

    def stop(self, *, success=False):
        pass


class NewTrivialFlyer(TrivialFlyer):
    """
    The old-style API inserted Resource and Datum documents into a database
    directly. The new-style API only caches the documents and provides an
    interface (collect_asset_docs) for accessing that cache. This change was
    part of the "asset refactor" that changed that way Resource and Datum
    documents flowed through ophyd, bluesky, and databroker. Trivial flyer that
    complies to the API but returns empty data.
    """

    name = 'new_trivial_flyer'

    def collect_asset_docs(self):
        for _ in ():
            yield _


class MockFlyer:
    """
    Class for mocking a flyscan API implemented with stepper motors.
    """

    def __init__(self, name, detector, motor, start, stop, num, loop=None):
        self.name = name
        self.parent = None
        self._mot = motor
        self._detector = detector
        self._steps = np.linspace(start, stop, num)
        self._data = deque()
        self._completion_status = None
        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop

    def __setstate__(self, val):
        name, detector, motor, steps = val
        self.name = name
        self.parent = None
        self._mot = motor
        self._detector = detector
        self._steps = steps
        self._completion_status = None
        self.loop = asyncio.get_event_loop()

    def __getstate__(self):
        return (self.name, self._detector, self._mot, self._steps)

    def read_configuration(self):
        return OrderedDict()

    def describe_configuration(self):
        return OrderedDict()

    def describe_collect(self):
        dd = dict()
        dd.update(self._mot.describe())
        dd.update(self._detector.describe())
        return {'stream_name': dd}

    def complete(self):
        if self._completion_status is None:
            raise RuntimeError("No collection in progress")
        return self._completion_status

    def kickoff(self):
        if self._completion_status is not None:
            raise RuntimeError("Already kicked off.")
        self._data = deque()

        self._future = self.loop.run_in_executor(None, self._scan)
        st = DeviceStatus(device=self)
        self._completion_status = st
        self._future.add_done_callback(lambda x: st._finished())
        return st

    def collect(self):
        if self._completion_status is None or not self._completion_status.done:
            raise RuntimeError("No reading until done!")
        self._completion_status = None

        yield from self._data

    def _scan(self):
        "This will be run on a separate thread, started in self.kickoff()"
        ttime.sleep(.1)
        for p in self._steps:
            stat = self._mot.set(p)
            while True:
                if stat.done:
                    break
                ttime.sleep(0.01)
            stat = self._detector.trigger()
            while True:
                if stat.done:
                    break
                ttime.sleep(0.01)

            event = dict()
            event['time'] = ttime.time()
            event['data'] = dict()
            event['timestamps'] = dict()
            for r in [self._mot, self._detector]:
                d = r.read()
                for k, v in d.items():
                    event['data'][k] = v['value']
                    event['timestamps'][k] = v['timestamp']
            self._data.append(event)

    def stop(self, *, success=False):
        pass


class SynSignalWithRegistry(SynSignal):
    """
    A SynSignal integrated with databroker.assets

    Parameters
    ----------
    func : callable, optional
        This function sets the signal to a new value when it is triggered.
        Expected signature: ``f() -> value``.
        By default, triggering the signal does not change the value.
    name : string, keyword only
    exposure_time : number, optional
        Seconds of delay when triggered (simulated 'exposure time'). Default is
        0.
    parent : Device, optional
        Used internally if this Signal is made part of a larger Device.
    loop : asyncio.EventLoop, optional
        used for ``subscribe`` updates; uses ``asyncio.get_event_loop()`` if
        unspecified
    reg : Registry, optional
        DEPRECATED. If used, this is ignored and a warning is issued. In a
        future release, this parameter will be removed.
    save_path : str, optional
        Path to save files to, if None make a temp dir, defaults to None.
    save_func : function, optional
        The function to save the data, function signature must be:
        `func(file_path, array)`, defaults to np.save
    save_spec : str, optional
        The spec for the save function, defaults to 'RWFS_NPY'
    save_ext : str, optional
        The extension to add to the file name, defaults to '.npy'

    """

    def __init__(self, *args, save_path=None,
                 save_func=partial(np.save, allow_pickle=False),
                 save_spec='NPY_SEQ', save_ext='npy', **kwargs):
        super().__init__(*args, **kwargs)
        self.save_func = save_func
        self.save_ext = save_ext
        self._resource_uid = None
        self._datum_counter = None
        self._asset_docs_cache = deque()
        if save_path is None:
            self.save_path = mkdtemp()
        else:
            self.save_path = save_path
        self._spec = save_spec  # spec name stored in resource doc

        self._file_stem = None
        self._path_stem = None
        self._result = {}

    def stage(self):
        self._file_stem = short_uid()
        self._datum_counter = itertools.count()
        self._path_stem = os.path.join(self.save_path, self._file_stem)

        # This is temporarily more complicated than it will be in the future.
        # It needs to support old configurations that have a registry.
        resource = {'spec': self._spec,
                    'root': self.save_path,
                    'resource_path': self._file_stem,
                    'resource_kwargs': {},
                    'path_semantics': {'posix': 'posix', 'nt': 'windows'}[os.name]}

        self._resource_uid = new_uid()
        resource['uid'] = self._resource_uid
        self._asset_docs_cache.append(('resource', resource))

    def trigger(self):
        super().trigger()
        # save file stash file name
        self._result.clear()
        for idx, (name, reading) in enumerate(super().read().items()):
            # Save the actual reading['value'] to disk. For a real detector,
            # this part would be done by the detector IOC, not by ophyd.
            data_counter = next(self._datum_counter)
            self.save_func('{}_{}.{}'.format(self._path_stem, data_counter,
                                             self.save_ext), reading['value'])
            # This is temporarily more complicated than it will be in the
            # future.  It needs to support old configurations that have a
            # registry.
            datum = {'resource': self._resource_uid,
                     'datum_kwargs': dict(index=data_counter)}

            # If a Registry is not set, we need to generate the datum_id.
            datum_id = '{}/{}'.format(self._resource_uid,
                                      data_counter)
            datum['datum_id'] = datum_id
            self._asset_docs_cache.append(('datum', datum))
            # And now change the reading in place, replacing the value with
            # a reference to Registry.
            reading['value'] = datum_id
            self._result[name] = reading

        return NullStatus()

    def read(self):
        return self._result

    def describe(self):
        res = super().describe()
        for key in res:
            res[key]['external'] = "FILESTORE"
        return res

    def collect_asset_docs(self):
        items = list(self._asset_docs_cache)
        self._asset_docs_cache.clear()
        for item in items:
            yield item

    def unstage(self):
        self._resource_uid = None
        self._datum_counter = None
        self._asset_docs_cache.clear()
        self._file_stem = None
        self._path_stem = None
        self._result.clear()


class NumpySeqHandler:
    specs = {'NPY_SEQ'}

    def __init__(self, filename, root=''):
        self._name = os.path.join(root, filename)

    def __call__(self, index):
        return np.load('{}_{}.npy'.format(self._name, index),
                       allow_pickle=False)

    def get_file_list(self, datum_kwarg_gen):
        "This method is optional. It is not needed for access, but for export."
        return ['{name}_{index}.npy'.format(name=self._name, **kwargs)
                for kwargs in datum_kwarg_gen]


class ABDetector(Device):
    a = Cpt(SynSignal, func=random.random, kind=Kind.hinted)
    b = Cpt(SynSignal, func=random.random)

    def trigger(self):
        return self.a.trigger() & self.b.trigger()


class DetWithCountTime(Device):
    intensity = Cpt(SynSignal, func=lambda: 0, kind=Kind.hinted)
    count_time = Cpt(Signal)


class DetWithConf(Device):
    a = Cpt(SynSignal, func=lambda: 1, kind=Kind.hinted)
    b = Cpt(SynSignal, func=lambda: 2, kind=Kind.hinted)
    c = Cpt(SynSignal, func=lambda: 3)
    d = Cpt(SynSignal, func=lambda: 4)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.read_attrs = ['a', 'b']
        self.configuration_attrs = ['c', 'd']

    def trigger(self):
        return self.a.trigger() & self.b.trigger()


class InvariantSignal(SynSignal):
    # Always returns the same reading, including timestamp.
    def read(self):
        res = super().read()
        for k in res:
            res[k]['timestamp'] = 0
        return res

    def __repr__(self):
        return "<INVARIANT REPR>"


class SPseudo3x3(PseudoPositioner):
    pseudo1 = Cpt(PseudoSingle, limits=(-10, 10), egu='a', kind=Kind.hinted)
    pseudo2 = Cpt(PseudoSingle, limits=(-10, 10), egu='b', kind=Kind.hinted)
    pseudo3 = Cpt(PseudoSingle, limits=None, egu='c', kind=Kind.hinted)
    real1 = Cpt(SoftPositioner, init_pos=0)
    real2 = Cpt(SoftPositioner, init_pos=0)
    real3 = Cpt(SoftPositioner, init_pos=0)

    sig = Cpt(Signal, value=0)

    @pseudo_position_argument
    def forward(self, pseudo_pos):
        pseudo_pos = self.PseudoPosition(*pseudo_pos)
        # logger.debug('forward %s', pseudo_pos)
        return self.RealPosition(real1=-pseudo_pos.pseudo1,
                                 real2=-pseudo_pos.pseudo2,
                                 real3=-pseudo_pos.pseudo3)

    @real_position_argument
    def inverse(self, real_pos):
        real_pos = self.RealPosition(*real_pos)
        # logger.debug('inverse %s', real_pos)
        return self.PseudoPosition(pseudo1=-real_pos.real1,
                                   pseudo2=-real_pos.real2,
                                   pseudo3=-real_pos.real3)


class SPseudo1x3(PseudoPositioner):
    pseudo1 = Cpt(PseudoSingle, limits=(-10, 10), kind=Kind.hinted)
    real1 = Cpt(SoftPositioner, init_pos=0)
    real2 = Cpt(SoftPositioner, init_pos=0)
    real3 = Cpt(SoftPositioner, init_pos=0)

    @pseudo_position_argument
    def forward(self, pseudo_pos):
        pseudo_pos = self.PseudoPosition(*pseudo_pos)
        # logger.debug('forward %s', pseudo_pos)
        return self.RealPosition(real1=-pseudo_pos.pseudo1,
                                 real2=-pseudo_pos.pseudo1,
                                 real3=-pseudo_pos.pseudo1)

    @real_position_argument
    def inverse(self, real_pos):
        real_pos = self.RealPosition(*real_pos)
        # logger.debug('inverse %s', real_pos)
        return self.PseudoPosition(pseudo1=-real_pos.real1)


class SynAxisNoPosition(SynAxis):
    @property
    def position(self):
        raise AttributeError


def make_fake_device(cls):
    """
    Inspect cls and construct a fake device that has the same structure.

    This works by replacing EpicsSignal with FakeEpicsSignal and EpicsSignalRO
    with FakeEpicsSignalRO. The fake class will be a subclass of the real
    class.

    This assumes that EPICS connections are done entirely in EpicsSignal and
    EpicsSignalRO subcomponents. If this is not true, this will fail silently
    on class construction and loudly when manipulating an object.

    Parameters
    ----------
    cls : Device
        A real Device class to inspect and create a fake Device class from

    Returns
    -------
    fake_device : Device
        The resulting fake Device class
    """
    # Cache to avoid repeating work.
    # EpicsSignal and EpicsSignalRO begin in the cache.
    if cls not in fake_device_cache:
        if not issubclass(cls, Device):
            # Ignore non-devices and non-epics-signals
            logger.debug('Ignore cls=%s, bases are %s', cls, cls.__bases__)
            fake_device_cache[cls] = cls
            return cls
        fake_dict = {}
        # Update all the components recursively
        for cpt_name in cls.component_names:
            cpt = getattr(cls, cpt_name)
            if isinstance(cpt, DDCpt):
                # Make a regular Cpt out of the DDC, as it already has
                # been generated
                fake_cpt = Cpt(cls=cpt.cls, suffix=cpt.suffix,
                               lazy=cpt.lazy,
                               trigger_value=cpt.trigger_value,
                               kind=cpt.kind, add_prefix=cpt.add_prefix,
                               doc=cpt.doc, **cpt.kwargs,
                )
            else:
                fake_cpt = copy.copy(cpt)

            fake_cpt.cls = make_fake_device(cpt.cls)
            logger.debug('switch cpt_name=%s to cls=%s', cpt_name,
                         fake_cpt.cls)

            fake_dict[cpt_name] = fake_cpt
        fake_class = type('Fake{}'.format(cls.__name__), (cls,), fake_dict)
        fake_device_cache[cls] = fake_class
        logger.debug('fake_device_cache[%s] = %s', cls, fake_class)
    return fake_device_cache[cls]


def clear_fake_device(dev, *, default_value=0, default_string_value='',
                      ignore_exceptions=False):
    '''Clear a fake device by setting all signals to a specific value

    Parameters
    ----------
    dev : Device
        The fake device
    default_value : any, optional
        The value to put to non-string components
    default_string_value : any, optional
        The value to put to components determined to be strings
    ignore_exceptions : bool, optional
        Ignore any exceptions raised by `sim_put`

    Returns
    -------
    all_values : list
        List of all (signal_instance, value) that were set
    '''

    all_values = []
    for walk in dev.walk_signals(include_lazy=True):
        sig = walk.item
        if not hasattr(sig, 'sim_put'):
            continue

        try:
            string = getattr(sig, 'as_string', False)
            value = (default_string_value
                     if string
                     else default_value)
            sig.sim_put(value)
        except Exception:
            if not ignore_exceptions:
                raise
        else:
            all_values.append((sig, value))

    return all_values


def instantiate_fake_device(dev_cls, *, name=None, prefix='_prefix',
                            **specified_kw):
    '''Instantiate a fake device, optionally specifying some initializer kwargs

    If unspecified, all initializer keyword arguments will default to the
    string f"_{argument_name}_".

    Parameters
    ----------
    dev_cls : class
        The device class to instantiate. This is allowed to be a regular
        device, as `make_fake_device` will be called on it first.
    name : str, optional
        The instantiated device name
    prefix : str, optional
        The instantiated device prefix
    **specified_kw :
        Keyword arguments to override with a specific value

    Returns
    -------
    dev : dev_cls instance
        The instantiated fake device
    '''
    dev_cls = make_fake_device(dev_cls)
    sig = inspect.signature(dev_cls)
    ignore_kw = {'kind', 'read_attrs', 'configuration_attrs', 'parent',
                 'args', 'name', 'prefix'}

    def get_kwarg(name, param):
        default = param.default
        if default == param.empty:
            # NOTE: could check param.annotation here
            default = '_{}_'.format(param.name)
        return specified_kw.get(name, default)

    kwargs = {name: get_kwarg(name, param)
              for name, param in sig.parameters.items()
              if param.kind != param.VAR_KEYWORD and
              name not in ignore_kw
              }
    kwargs['name'] = (name if name is not None else dev_cls.__name__)
    kwargs['prefix'] = prefix
    return dev_cls(**kwargs)


class FakeEpicsSignal(SynSignal):
    """
    Fake version of EpicsSignal that's really just a SynSignal.

    Wheras SynSignal is generally used to test plans, FakeEpicsSignal is
    generally used in conjunction with make_fake_device to test any logic
    inside of a Device subclass.

    Unlike in SynSignal, this class is generally instantiated inside of a
    subcomponent generated automatically by make_fake_device. This means we
    need extra hooks for modifying the signal's properties after the class
    instantiates.

    We can emulate EpicsSignal features here. We currently emulate the put
    limits and some enum handling.
    """
    def __init__(self, read_pv, write_pv=None, *, put_complete=False,
                 string=False, limits=False, auto_monitor=False, name=None,
                 **kwargs):
        """
        Mimic EpicsSignal signature
        """
        self.as_string = string
        self._enum_strs = None
        super().__init__(name=name, **kwargs)
        self._use_limits = limits
        self._put_func = None
        self._limits = None
        self._metadata.update(
            connected=True,
        )

    def describe(self):
        desc = super().describe()
        if self._enum_strs is not None:
            desc[self.name]['enum_strs'] = self.enum_strs
        return desc

    def sim_set_putter(self, putter):
        """
        Define arbirary behavior on signal put.

        This can be used to emulate basic IOC behavior.
        """
        self._put_func = putter

    def get(self, *, as_string=None, connection_timeout=1.0, **kwargs):
        """
        Implement getting as enum strings
        """
        if as_string is None:
            as_string = self.as_string

        value = super().get()

        if as_string:
            if self.enum_strs is not None and isinstance(value, int):
                return self.enum_strs[value]
            elif value is not None:
                return str(value)
        return value

    def put(self, value, *args, **kwargs):
        """
        Implement putting as enum strings and put functions
        """
        if self.enum_strs is not None:
            if value in self.enum_strs:
                value = self.enum_strs.index(value)
            elif isinstance(value, str):
                err = '{} not in enum strs {}'.format(value, self.enum_strs)
                raise ValueError(err)
        if self._put_func is not None:
            return self._put_func(value, *args, **kwargs)
        return super().put(value, *args, **kwargs)

    def sim_put(self, *args, **kwargs):
        """
        Update the read-only signal's value.

        Implement here instead of FakeEpicsSignalRO so you can call it with
        every fake signal.
        """
        force = kwargs.pop('force', True)
        # The following will emit SUB_VALUE:
        ret = Signal.put(self, *args, force=force, **kwargs)
        # Also, ensure that SUB_META has been emitted:
        self._run_subs(sub_type=self.SUB_META, **self._metadata)
        return ret

    @property
    def enum_strs(self):
        """
        Simulated enum strings.

        Use sim_set_enum_strs during setup to set the enum strs.
        """
        return self._enum_strs

    def sim_set_enum_strs(self, enums):
        """
        Set the enum_strs for a fake device

        Parameters
        ----------
        enums: list or tuple of str
            The enums will be accessed by array index, e.g. the first item in
            enums will be 0, the next will be 1, etc.
        """
        self._enum_strs = tuple(enums)
        self._metadata['enum_strs'] = tuple(enums)
        self._run_subs(sub_type=self.SUB_META, **self._metadata)

    @property
    def limits(self):
        return self._limits

    def sim_set_limits(self, limits):
        """
        Set the fake signal's limits.
        """
        self._limits = limits

    def check_value(self, value):
        """
        Implement some of the checks from EpicsSignal
        """
        super().check_value(value)
        if value is None:
            raise ValueError('Cannot write None to EPICS PVs')
        if self._use_limits and not self.limits[0] <= value <= self.limits[1]:
            raise LimitError(f'value={value} not within limits {self.limits}')


class FakeEpicsSignalRO(SynSignalRO, FakeEpicsSignal):
    """
    Read-only FakeEpicsSignal
    """
    pass


class FakeEpicsSignalWithRBV(FakeEpicsSignal):
    """
    FakeEpicsSignal with PV and PV_RBV; used in the AreaDetector PV naming
    scheme
    """
    def __init__(self, prefix, **kwargs):
        super().__init__(prefix + '_RBV', write_pv=prefix, **kwargs)


fake_device_cache = {EpicsSignal: FakeEpicsSignal,
                     EpicsSignalRO: FakeEpicsSignalRO,
                     EpicsSignalWithRBV: FakeEpicsSignalWithRBV,
                     }


class DirectImage(Device):
    img = Cpt(SynSignal, kind='hinted')

    def __init__(self, *args, func=None, **kwargs):
        super().__init__(*args, **kwargs)
        if func is not None:
            self.img.sim_set_func(func)

    def trigger(self):
        return self.img.trigger()


def hw(save_path=None):
    "Build a set of synthetic hardware (hence the abbreviated name, hw)"
    motor = SynAxis(name='motor', labels={'motors'})
    motor1 = SynAxis(name='motor1', labels={'motors'})
    motor2 = SynAxis(name='motor2', labels={'motors'})
    motor3 = SynAxis(name='motor3', labels={'motors'})
    jittery_motor1 = SynAxis(name='jittery_motor1',
                             readback_func=lambda x: x + np.random.rand(),
                             labels={'motors'})
    jittery_motor2 = SynAxis(name='jittery_motor2',
                             readback_func=lambda x: x + np.random.rand(),
                             labels={'motors'})
    noisy_det = SynGauss('noisy_det', motor, 'motor', center=0, Imax=1,
                         noise='uniform', sigma=1, noise_multiplier=0.1,
                         labels={'detectors'})
    det = SynGauss('det', motor, 'motor', center=0, Imax=1, sigma=1,
                   labels={'detectors'})
    identical_det = SynGauss('det', motor, 'motor', center=0, Imax=1, sigma=1,
                             labels={'detectors'})
    det1 = SynGauss('det1', motor1, 'motor1', center=0, Imax=5, sigma=0.5,
                    labels={'detectors'})
    det2 = SynGauss('det2', motor2, 'motor2', center=1, Imax=2, sigma=2,
                    labels={'detectors'})
    det3 = SynGauss('det3', motor3, 'motor3', center=-1, Imax=2, sigma=1,
                    labels={'detectors'})
    det4 = Syn2DGauss('det4', motor1, 'motor1', motor2, 'motor2',
                      center=(0, 0), Imax=1, labels={'detectors'})
    det5 = Syn2DGauss('det5', jittery_motor1, 'jittery_motor1', jittery_motor2,
                      'jittery_motor2', center=(0, 0), Imax=1,
                      labels={'detectors'})

    flyer1 = MockFlyer('flyer1', det, motor, 1, 5, 20)
    flyer2 = MockFlyer('flyer2', det, motor, 1, 5, 10)
    trivial_flyer = TrivialFlyer()
    new_trivial_flyer = NewTrivialFlyer()

    ab_det = ABDetector(name='det', labels={'detectors'})
    # area detector that directly stores image data in Event
    direct_img = DirectImage(func=lambda: np.array(np.ones((10, 10))),
                             name='direct', labels={'detectors'})
    direct_img.img.name = 'img'

    direct_img_list = DirectImage(func=lambda: [[1] * 10] * 10,
                                  name='direct', labels={'detectors'})
    direct_img_list.img.name = 'direct_img_list'

    # area detector that stores data in a file
    img = SynSignalWithRegistry(func=lambda: np.array(np.ones((10, 10))),
                                name='img', labels={'detectors'},
                                save_path=save_path)
    invariant1 = InvariantSignal(func=lambda: 0, name='invariant1',
                                 labels={'detectors'})
    invariant2 = InvariantSignal(func=lambda: 0, name='invariant2',
                                 labels={'detectors'})
    det_with_conf = DetWithConf(name='det', labels={'detectors'})
    det_with_count_time = DetWithCountTime(name='det', labels={'detectors'})
    rand = SynPeriodicSignal(name='rand', labels={'detectors'})
    rand2 = SynPeriodicSignal(name='rand2', labels={'detectors'})
    motor_no_pos = SynAxisNoPosition(name='motor', labels={'motors'})
    bool_sig = Signal(value=False, name='bool_sig', labels={'detectors'})

    motor_empty_hints1 = SynAxisEmptyHints(name='motor1', labels={'motors'})
    motor_empty_hints2 = SynAxisEmptyHints(name='motor2', labels={'motors'})

    motor_no_hints1 = SynAxisNoHints(name='motor1', labels={'motors'})
    motor_no_hints2 = SynAxisNoHints(name='motor2', labels={'motors'})
    # Because some of these reference one another we must define them (above)
    # before we pack them into a namespace (below).

    signal = SynSignal(name='signal')

    return SimpleNamespace(
        motor=motor,
        motor1=motor1,
        motor2=motor2,
        motor3=motor3,
        jittery_motor1=jittery_motor1,
        jittery_motor2=jittery_motor2,
        noisy_det=noisy_det,
        det=det,
        identical_det=identical_det,
        det1=det1,
        det2=det2,
        det3=det3,
        det4=det4,
        det5=det5,
        flyer1=flyer1,
        flyer2=flyer2,
        trivial_flyer=trivial_flyer,
        new_trivial_flyer=new_trivial_flyer,
        ab_det=ab_det,
        direct_img=direct_img,
        direct_img_list=direct_img_list,
        img=img,
        invariant1=invariant1,
        invariant2=invariant2,
        pseudo3x3=SPseudo3x3(name='pseudo3x3'),
        pseudo1x3=SPseudo1x3(name='pseudo1x3'),
        sig=Signal(name='sig', value=0),
        det_with_conf=det_with_conf,
        det_with_count_time=det_with_count_time,
        rand=rand,
        rand2=rand2,
        motor_no_pos=motor_no_pos,
        motor_empty_hints1=motor_empty_hints1,
        motor_empty_hints2=motor_empty_hints2,
        motor_no_hints1=motor_no_hints1,
        motor_no_hints2=motor_no_hints2,
        bool_sig=bool_sig,
        signal=signal,
    )


# Dump instances of the example hardware generated by hw() into the global
# namespcae for convenience and back-compat.
globals().update(hw().__dict__)
