import asyncio
import time as ttime
from collections import deque, OrderedDict
import itertools
import numpy as np
import random
import threading
from tempfile import mkdtemp
import os
import warnings
import weakref
import uuid
import copy
import logging

from .signal import Signal, EpicsSignal, EpicsSignalRO
from .status import DeviceStatus, StatusBase
from .device import (Device, Component, Component as C,
                     DynamicDeviceComponent as DDC, Kind)
from types import SimpleNamespace
from .pseudopos import (PseudoPositioner, PseudoSingle,
                        real_position_argument, pseudo_position_argument)
from .positioner import SoftPositioner
from .utils import DO_NOT_USE, ReadOnlyError, LimitError

logger = logging.getLogger(__name__)


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
                 loop=None):
        if func is None:
            # When triggered, just put the current value.
            func = self.get
            # Initialize readback with a None value
            self._readback = None
        if loop is None:
            loop = asyncio.get_event_loop()
        self._func = func
        self.exposure_time = exposure_time
        self.precision = 3
        self.loop = loop
        super().__init__(value=self._func(), timestamp=ttime.time(), name=name,
                         parent=parent, labels=labels, kind=kind)

    def describe(self):
        res = super().describe()
        # There should be only one key here, but for the sake of generality....
        for k in res:
            res[k]['precision'] = self.precision
        return res

    def trigger(self):
        delay_time = self.exposure_time
        if delay_time:
            st = DeviceStatus(device=self)
            if self.loop.is_running():

                def update_and_finish():
                    self.put(self._func())
                    st._finished()

                self.loop.call_later(delay_time, update_and_finish)
            else:

                def sleep_and_finish():
                    ttime.sleep(delay_time)
                    self.put(self._func())
                    st._finished()

                threading.Thread(target=sleep_and_finish, daemon=True).start()
            return st
        else:
            self.put(self._func())
            return NullStatus()

    def get(self):
        # Get a new value, which allows us to synthesize noisy data, for
        # example.
        return super().get()


class SignalRO(Signal):
    def put(self, value, *, timestamp=None, force=False):
        raise ReadOnlyError("The signal {} is readonly.".format(self.name))

    def set(self, value, *, timestamp=None, force=False):
        raise ReadOnlyError("The signal {} is readonly.".format(self.name))


class SynSignalRO(SignalRO, SynSignal):
    pass


def periodic_update(ref, period, period_jitter):
    while True:
        signal = ref()
        if not signal:
            # Our target Signal has been garbage collected. Shut down the
            # Thread.
            return
        signal.put(signal._func())
        del signal
        # Sleep for period +/- period_jitter.
        ttime.sleep(max(period + period_jitter * np.random.randn(), 0))


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
                 loop=None):
        if func is None:
            func = np.random.rand
        super().__init__(name=name, func=func,
                         exposure_time=exposure_time,
                         parent=parent, labels=labels, kind=kind, loop=loop)

        self.__thread = threading.Thread(target=periodic_update, daemon=True,
                                         args=(weakref.ref(self),
                                               period,
                                               period_jitter))
        self.__thread.start()


class ReadbackSignal(SignalRO):
    def get(self):
        return self.parent.sim_state['readback']

    def describe(self):
        res = super().describe()
        # There should be only one key here, but for the sake of generality....
        for k in res:
            res[k]['precision'] = self.parent.precision
        return res

    @property
    def timestamp(self):
        '''Timestamp of the readback value'''
        return self.parent.sim_state['readback_ts']


class SetpointSignal(Signal):
    def put(self, value, *, timestamp=None, force=False):
        self.parent.set(value)

    def get(self):
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


class SynAxisNoHints(Device):
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
    readback = Component(ReadbackSignal, value=None)
    setpoint = Component(SetpointSignal, value=None)
    SUB_READBACK = 'readback'
    _default_sub = SUB_READBACK

    def __init__(self, *,
                 name,
                 readback_func=None, value=0, delay=0,
                 precision=3,
                 parent=None,
                 labels=None,
                 kind=None,
                 loop=None):
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

        super().__init__(name=name, parent=parent, labels=labels, kind=kind)
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


class SynAxis(SynAxisNoHints):
    readback = Component(ReadbackSignal, value=None, kind=Kind.hinted)


class SynGauss(SynSignal):
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

    def __init__(self, name, motor, motor_field, center, Imax, sigma=1,
                 noise=None, noise_multiplier=1, random_state=None, **kwargs):
        if noise not in ('poisson', 'uniform', None):
            raise ValueError("noise must be one of 'poisson', 'uniform', None")
        self._motor = motor
        if random_state is None:
            random_state = np.random

        def func():
            m = motor.read()[motor_field]['value']
            v = Imax * np.exp(-(m - center) ** 2 / (2 * sigma ** 2))
            if noise == 'poisson':
                v = int(random_state.poisson(np.round(v), 1))
            elif noise == 'uniform':
                v += random_state.uniform(-1, 1) * noise_multiplier
            return v

        super().__init__(func=func, name=name, **kwargs)


class Syn2DGauss(SynSignal):
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

    def __init__(self, name, motor0, motor_field0, motor1, motor_field1,
                 center, Imax, sigma=1, noise=None, noise_multiplier=1,
                 random_state=None, **kwargs):

        if noise not in ('poisson', 'uniform', None):
            raise ValueError("noise must be one of 'poisson', 'uniform', None")
        self._motor = motor0
        self._motor1 = motor1
        if random_state is None:
            random_state = np.random

        def func():
            x = motor0.read()[motor_field0]['value']
            y = motor1.read()[motor_field1]['value']
            m = np.array([x, y])
            v = Imax * np.exp(-np.sum((m - center) ** 2) / (2 * sigma ** 2))
            if noise == 'poisson':
                v = int(random_state.poisson(np.round(v), 1))
            elif noise == 'uniform':
                v += random_state.uniform(-1, 1) * noise_multiplier
            return v

        super().__init__(name=name, func=func, **kwargs)


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

    def __init__(self, *args, reg=DO_NOT_USE, save_path=None,
                 save_func=np.save, save_spec='NPY_SEQ', save_ext='npy',
                 **kwargs):
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

        if reg is not DO_NOT_USE:
            warnings.warn("The parameter 'reg' is deprecated. It will be "
                          "ignored. In a future release the parameter will be "
                          "removed and passing a value for 'reg' will raise "
                          "an error.")
            self.reg = reg
        else:
            self.reg = None

    def stage(self):
        self._file_stem = short_uid()
        self._path_stem = os.path.join(self.save_path, self._file_stem)
        self._datum_counter = itertools.count()

        # This is temporarily more complicated than it will be in the future.
        # It needs to support old configurations that have a registry.
        resource = {'spec': self._spec,
                    'root': self.save_path,
                    'resource_path': self._file_stem,
                    'resource_kwargs': {},
                    'path_semantics': os.name}
        # If a Registry is set, we need to allow it to generate the uid for us.
        if self.reg is not None:
            # register_resource has accidentally different parameter names...
            self._resource_uid = self.reg.register_resource(
                rpath=resource['resource_path'],
                rkwargs=resource['resource_kwargs'],
                root=resource['root'],
                spec=resource['spec'],
                path_semantics=resource['path_semantics'])
        # If a Registry is not set, we need to generate the uid.
        else:
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
            self.save_func('{}_{}.{}'.format(self._path_stem, idx,
                                             self.save_ext), reading['value'])
            # This is temporarily more complicated than it will be in the
            # future.  It needs to support old configurations that have a
            # registry.
            datum = {'resource': self._resource_uid,
                     'datum_kwargs': dict(index=idx)}
            if self.reg is not None:
                # If a Registry is set, we need to allow it to generate the
                # datum_id for us.
                datum_id = self.reg.register_datum(
                    datum_kwargs=datum['datum_kwargs'],
                    resource_uid=datum['resource'])
            else:
                # If a Registry is not set, we need to generate the datum_id.
                datum_id = '{}/{}'.format(self._resource_uid,
                                          next(self._datum_counter))
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
        return np.load('{}_{}.npy'.format(self._name, index))

    def get_file_list(self, datum_kwarg_gen):
        "This method is optional. It is not needed for access, but for export."
        return ['{name}_{index}.npy'.format(name=self._name, **kwargs)
                for kwargs in datum_kwarg_gen]


class ABDetector(Device):
    a = Component(SynSignal, func=random.random, kind=Kind.hinted)
    b = Component(SynSignal, func=random.random)

    def trigger(self):
        return self.a.trigger() & self.b.trigger()


class DetWithCountTime(Device):
    intensity = Component(SynSignal, func=lambda: 0, kind=Kind.hinted)
    count_time = Component(Signal)


class DetWithConf(Device):
    a = Component(SynSignal, func=lambda: 1, kind=Kind.hinted)
    b = Component(SynSignal, func=lambda: 2, kind=Kind.hinted)
    c = Component(SynSignal, func=lambda: 3)
    d = Component(SynSignal, func=lambda: 4)

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
    pseudo1 = C(PseudoSingle, limits=(-10, 10), egu='a', kind=Kind.hinted)
    pseudo2 = C(PseudoSingle, limits=(-10, 10), egu='b', kind=Kind.hinted)
    pseudo3 = C(PseudoSingle, limits=None, egu='c', kind=Kind.hinted)
    real1 = C(SoftPositioner, init_pos=0)
    real2 = C(SoftPositioner, init_pos=0)
    real3 = C(SoftPositioner, init_pos=0)

    sig = C(Signal, value=0)

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
    pseudo1 = C(PseudoSingle, limits=(-10, 10), kind=Kind.hinted)
    real1 = C(SoftPositioner, init_pos=0)
    real2 = C(SoftPositioner, init_pos=0)
    real3 = C(SoftPositioner, init_pos=0)

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
            fake_cpt = copy.copy(cpt)
            if isinstance(cpt, Component):
                fake_cpt.cls = make_fake_device(cpt.cls)
                logger.debug('switch cpt_name=%s to cls=%s',
                             cpt_name, fake_cpt.cls)
            # DDCpt stores the classes in a different place
            elif isinstance(cpt, DDC):
                fake_defn = {}
                for ddcpt_name, ddcpt_tuple in cpt.defn.items():
                    subcls = make_fake_device(ddcpt_tuple[0])
                    fake_defn[ddcpt_name] = [subcls] + list(ddcpt_tuple[1:])
                fake_cpt.defn = fake_defn
            else:
                raise RuntimeError(("{} is not a component or a dynamic "
                                    "device component. I don't know how you "
                                    "found this error, should be impossible "
                                    "to reach it.".format(cpt)))
            fake_dict[cpt_name] = fake_cpt
        fake_class = type('Fake{}'.format(cls.__name__), (cls,), fake_dict)
        fake_device_cache[cls] = fake_class
        logger.debug('fake_device_cache[%s] = %s', cls, fake_class)
    return fake_device_cache[cls]


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

    We can emulate EpicsSignal features here. Currently we just emulate the put
    limits because it was involved in a kwarg.
    """
    def __init__(self, read_pv, write_pv=None, *, pv_kw=None,
                 put_complete=False, string=False, limits=False,
                 auto_monitor=False, name=None, **kwargs):
        """
        Mimic EpicsSignal signature
        """
        super().__init__(name=name, **kwargs)
        self._use_limits = limits
        self._put_func = None

    def sim_set_func(self, func):
        """
        Update the SynSignal function to set a new value on trigger.
        """
        self._func = func

    def sim_set_putter(self, putter):
        """
        Define arbirary behavior on signal put.

        This can be used to emulate basic IOC behavior.
        """
        self._put_func = putter

    def put(self, *args, **kwargs):
        if self._put_func is not None:
            return self._put_func(*args, **kwargs)
        return super().put(*args, **kwargs)

    def sim_put(self, *args, **kwargs):
        """
        Update the read-only signal's value.

        Implement here instead of FakeEpicsSignalRO so you can call it with
        every fake signal.
        """
        return Signal.put(self, *args, **kwargs)

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
        Check fake limits before putting
        """
        super().check_value(value)
        if self._use_limits and not self.limits[0] < value < self.limits[1]:
            raise LimitError('value={} limits={}'.format(value, self.limits))


class FakeEpicsSignalRO(SynSignalRO, FakeEpicsSignal):
    """
    Read-only FakeEpicsSignal
    """
    pass


fake_device_cache = {EpicsSignal: FakeEpicsSignal,
                     EpicsSignalRO: FakeEpicsSignalRO}


def hw():
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

    ab_det = ABDetector(name='det', labels={'detectors'})
    # area detector that directly stores image data in Event
    direct_img = SynSignal(func=lambda: np.array(np.ones((10, 10))),
                           name='img', labels={'detectors'})
    # area detector that stores data in a file
    img = SynSignalWithRegistry(func=lambda: np.array(np.ones((10, 10))),
                                name='img', labels={'detectors'})
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

    motor_no_hints1 = SynAxisNoHints(name='motor1', labels={'motors'})
    motor_no_hints2 = SynAxisNoHints(name='motor2', labels={'motors'})
    # Because some of these reference one another we must define them (above)
    # before we pack them into a namespace (below).

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
        ab_det=ab_det,
        direct_img=direct_img,
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
        motor_no_hints1=motor_no_hints1,
        motor_no_hints2=motor_no_hints2,
        bool_sig=bool_sig,
    )


# Dump instances of the example hardware generated by hw() into the global
# namespcae for convenience and back-compat.
globals().update(hw().__dict__)
