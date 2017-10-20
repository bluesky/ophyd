import asyncio
import time as ttime
from collections import deque, OrderedDict
from threading import RLock
import numpy as np
import threading
from tempfile import mkdtemp
import os
import weakref
import uuid

from .signal import Signal
from .status import DeviceStatus, StatusBase
from .device import Device, Component


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
    trigger_delay : number, optional
        Seconds of delay when triggered (simulated 'exposure time'). Default is
        0.
    parent : Device, optional
        Used internally if this Signal is made part of a larger Device.
    loop : event loop, optional
    """
    # This signature is arranged to mimic the signature of EpicsSignal, where
    # the Python function (func) takes the place of the PV.
    def __init__(self, func=None, *,
                 name,  # required, keyword-only
                 trigger_delay=0,
                 parent=None,
                 loop=None):
        if func is None:
            # When triggered, just put the current value.
            func = self.get
        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop
        self._func = func
        self._trigger_delay = trigger_delay
        super().__init__(value=0, timestamp=ttime.time(), name=name,
                         parent=parent)

    def trigger(self):
        delay_time = self._trigger_delay
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
            return NullStatus()

    def get(self):
        # Get a new value, which allows us to synthesize noisy data, for
        # example.
        return super().get()


class SynSignalRO(SynSignal):
    def put(self, value, *, timestamp=None, force=False):
        raise NotImplementedError("The signal {} is readonly."
                                  "".format(self.name))


class SignalRO(Signal):
    def put(self, value, *, timestamp=None, force=False):
        raise NotImplementedError("The signal {} is readonly."
                                  "".format(self.name))


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
    trigger_delay : number, optional
        Seconds of delay when triggered (simulated 'exposure time'). Default is
        0.
    parent : Device, optional
        Used internally if this Signal is made part of a larger Device.
    loop : event loop, optional
    """
    def __init__(self, func=None, *,
                 name,  # required, keyword-only
                 period=1, period_jitter=1,
                 trigger_delay=0,
                 parent=None,
                 loop=None):
        if func is None:
            func = np.random.rand
        super().__init__(name=name, func=func,
                         trigger_delay=trigger_delay,
                         parent=parent, loop=loop)

        self.__thread = threading.Thread(target=periodic_update, daemon=True,
                                         args=(weakref.ref(self),
                                               period,
                                               period_jitter))
        self.__thread.start()


class ReadbackSignal(SignalRO):
    def get(self):
        return self.parent.sim_state['readback']


class SetpointSignal(Signal):
    def put(self, value, *, timestamp=None, force=False):
        self.parent.set(value)
        # TODO wait?

    def get(self):
        return self.parent.sim_state['setpoint']


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
    parent : Device, optional
        Used internally if this Signal is made part of a larger Device.
    loop : event loop, optional
    """
    readback = Component(ReadbackSignal, value=None)
    setpoint = Component(SetpointSignal, value=None)

    def __init__(*,
                 name,
                 readback_func=None, value=0, delay=0,
                 parent=None,
                 loop=None):
        if readback_func is None:
            readback_func = lambda x: x
        if loop is None:
            loop = asyncio.get_event_loop()

        self.sim_state = {}
        self._readback_func = readback_func

        # initialize values
        self.sim_state['readback'] = readback_func(value)
        self.sim_state['setpoint'] = value


    def set(self, value):

        def update_state():
            self.sim_state['readback'] = self._readback_func(value)
            self.sim_state['setpoint'] = value

        if loop.is_running():
            st = Device(device=self)
            st.add_callback(update_state)
            loop.call_later(delay, st._finished)
            return st
        else:
            ttime.sleep(delay)
            update_state()
            return NullStatus()

    @property
    def position(self):
        return self.readbaack.get()

    @property
    def hints(self):
        return {'fields': [self.readback.name]}


###############################################################################
#
# The code below is migrated from early (pre-1.0) bluesky. It is not well
# aligned with the ophyd API and generally should not be used. It is only
# maintained to support some legacy code.
#
###############################################################################


SimpleStatus = DeviceStatus


class SynGauss:
    """
    Evaluate a point on a Gaussian based on the value of a motor.

    Parameters
    ----------
    noise : {'poisson', 'uniform', None}
        Add noise to the gaussian peak.
    noise_multiplier : float
        Only relevant for 'uniform' noise. Multiply the random amount of
        noise by 'noise_multiplier'

    Example
    -------
    motor = Mover('motor', {'motor': lambda x: x}, {'x': 0})
    det = SynGauss('det', motor, 'motor', center=0, Imax=1, sigma=1)
    """

    def __init__(self, name, motor, motor_field, center, Imax, sigma=1,
                 noise=None, noise_multiplier=1, **kwargs):
        if noise not in ('poisson', 'uniform', None):
            raise ValueError("noise must be one of 'poisson', 'uniform', None")

        def func():
            m = motor.read()[motor_field]['value']
            v = Imax * np.exp(-(m - center) ** 2 / (2 * sigma ** 2))
            if noise == 'poisson':
                v = int(np.random.poisson(np.round(v), 1))
            elif noise == 'uniform':
                v += np.random.uniform(-1, 1) * noise_multiplier
            return v

        super().__init__(name, {name: func}, **kwargs)


class Syn2DGauss:
    """
    Evaluate a point on a Gaussian based on the value of a motor.

    Parameters
    ----------
    name : str
        The name of the detector
    motor0 : `Mover`
        The 'x' coordinate of the 2-D gaussian blob
    motor_field0 : str
        The name field of the motor. Should be the key in motor0.describe()
    motor1 : `Mover`
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
    noise : {'poisson', 'uniform', None}
        Add noise to the gaussian peak..
        Defaults to None
    noise_multiplier : float, optional
        Only relevant for 'uniform' noise. Multiply the random amount of
        noise by 'noise_multiplier'
        Defaults to 1

    Example
    -------
    motor = Mover('motor', ['motor'])
    det = SynGauss('det', motor, 'motor', center=0, Imax=1, sigma=1)
    """

    def __init__(self, name, motor0, motor_field0, motor1, motor_field1,
                 center, Imax, sigma=1, noise=None, noise_multiplier=1):

        if noise not in ('poisson', 'uniform', None):
            raise ValueError("noise must be one of 'poisson', 'uniform', None")

        def func():
            x = motor0.read()[motor_field0]['value']
            y = motor1.read()[motor_field1]['value']
            m = np.array([x, y])
            v = Imax * np.exp(-np.sum((m - center) ** 2) / (2 * sigma ** 2))
            if noise == 'poisson':
                v = int(np.random.poisson(np.round(v), 1))
            elif noise == 'uniform':
                v += np.random.uniform(-1, 1) * noise_multiplier
            return v

        super().__init__(name, {name: func})


class ReaderWithRegistry:
    """

    Parameters
    ----------
    name : string
    read_fields : dict
        Mapping field names to functions that return simulated data. The
        function will be passed no arguments.
    conf_fields : dict, optional
        Like `read_fields`, but providing slow-changing configuration data.
        If `None`, the configuration will simply be an empty dict.
    monitor_intervals : list, optional
        iterable of numbers, specifying the spacing in time of updates from the
        device (this applies only if the ``subscribe`` method is used)
    loop : asyncio.EventLoop, optional
        used for ``subscribe`` updates; uses ``asyncio.get_event_loop()`` if
        unspecified
    reg : Registry
        Registry object that supports inserting resource and datum documents
    save_path : str, optional
        Path to save files to, if None make a temp dir, defaults to None.

    """

    def __init__(self, *args, reg, save_path=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.reg = reg
        self._resource_id = None
        if save_path is None:
            self.save_path = mkdtemp()
        else:
            self.save_path = save_path
        self._spec = 'RWFS_NPY'  # spec name stored in resource doc

        self._file_stem = None
        self._path_stem = None
        self._result = {}

    def stage(self):
        self._file_stem = short_uid()
        self._path_stem = os.path.join(self.save_path, self._file_stem)
        self._resource_id = self.reg.register_resource(self._spec,
                                                       self.save_path,
                                                       self._file_stem, {})

    def trigger(self):
        # save file stash file name
        self._result.clear()
        for idx, (name, reading) in enumerate(self.trigger_read().items()):
            # Save the actual reading['value'] to disk and create a record
            # in Registry.
            np.save('{}_{}.npy'.format(self._path_stem, idx), reading['value'])
            datum_id = new_uid()
            self.reg.insert_datum(self._resource_id, datum_id,
                                  dict(index=idx))
            # And now change the reading in place, replacing the value with
            # a reference to Registry.
            reading['value'] = datum_id
            self._result[name] = reading

        delay_time = self.exposure_time
        if delay_time:
            if self.loop.is_running():
                st = SimpleStatus(device=self)
                self.loop.call_later(delay_time, st._finished)
                return st
            else:
                ttime.sleep(delay_time)

        return NullStatus()

    def trigger_read(self):
        return super().read()

    def read(self):
        return self._result

    def describe(self):
        res = super().describe()
        for key in res:
            res[key]['external'] = "FILESTORE"
        return res

    def unstage(self):
        self._resource_id = None
        self._file_stem = None
        self._path_stem = None
        self._result.clear()


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
        return self._completion_status

    def kickoff(self):
        if self._completion_status is not None:
            raise RuntimeError("Already kicked off.")
        self._data = deque()

        # Setup a status object that will be returned by
        # self.complete(). Separately, make dummy status object
        # that is immediately done, and return that, indicated that
        # the 'kickoff' step is done.
        self._future = self.loop.run_in_executor(None, self._scan)
        st = SimpleStatus(device=self)
        self._completion_status = st
        self._future.add_done_callback(lambda x: st._finished())

        return NullStatus()

    def collect(self):
        if self._completion_status is not None:
            raise RuntimeError("No reading until done!")

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
        self._completion_status._finished()
        self._completion_status = None

    def stop(self, *, success=False):
        pass


class GeneralReaderWithRegistry:
    """

    Parameters
    ----------
    name : string
    read_fields : dict
        Mapping field names to functions that return simulated data. The
        function will be passed no arguments.
    conf_fields : dict, optional
        Like `read_fields`, but providing slow-changing configuration data.
        If `None`, the configuration will simply be an empty dict.
    monitor_intervals : list, optional
        iterable of numbers, specifying the spacing in time of updates from the
        device (this applies only if the ``subscribe`` method is used)
    loop : asyncio.EventLoop, optional
        used for ``subscribe`` updates; uses ``asyncio.get_event_loop()`` if
        unspecified
    reg : Registry
        Registry object that supports inserting resource and datum documents
    save_path : str, optional
        Path to save files to, if None make a temp dir, defaults to None.
    save_func : function, optional
        The function to save the data, function signature must be:
        `func(file_path, array)`, defaults to np.save
    save_spec : str, optional
        The spec for the save function, defaults to 'RWFS_NPY'
    save_ext : str, optional
        The extention to add to the file name, defaults to '.npy'

    """

    def __init__(self, *args, reg, save_path=None, save_func=np.save,
                 save_spec='RWFS_NPY', save_ext='.npy',
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.reg = reg
        self.save_func = save_func
        self.save_ext = save_ext
        self._resource_id = None
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
        self._path_stem = os.path.join(self.save_path, self._file_stem)
        self._resource_id = self.reg.register_resource(self._spec,
                                                       self.save_path,
                                                       self._file_stem, {})

    def trigger(self):
        # save file stash file name
        self._result.clear()
        for idx, (name, reading) in enumerate(super().read().items()):
            # Save the actual reading['value'] to disk and create a record
            # in Registry.
            self.save_func('{}_{}.{}'.format(self._path_stem, idx,
                                             self.save_ext), reading['value'])
            datum_id = new_uid()
            self.reg.insert_datum(self._resource_id, datum_id,
                                  dict(index=idx))
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

    def unstage(self):
        self._resource_id = None
        self._file_stem = None
        self._path_stem = None
        self._result.clear()


class ReaderWithRegistryHandler:
    specs = {'RWFS_NPY'}

    def __init__(self, filename, root=''):
        self._name = os.path.join(root, filename)

    def __call__(self, index):
        return np.load('{}_{}.npy'.format(self._name, index))

    def get_file_list(self, datum_kwarg_gen):
        "This method is optional. It is not needed for access, but for export."
        return ['{name}_{index}.npy'.format(name=self._name, **kwargs)
                for kwargs in datum_kwarg_gen]


# motor = Mover('motor', OrderedDict([('motor', lambda x: x),
#                                     ('motor_setpoint', lambda x: x)]),
#               {'x': 0})
# motor1 = Mover('motor1', OrderedDict([('motor1', lambda x: x),
#                                       ('motor1_setpoint', lambda x: x)]),
#                {'x': 0})
# motor2 = Mover('motor2', OrderedDict([('motor2', lambda x: x),
#                                       ('motor2_setpoint', lambda x: x)]),
#                {'x': 0})
# motor3 = Mover('motor3', OrderedDict([('motor3', lambda x: x),
#                                       ('motor3_setpoint', lambda x: x)]),
#                {'x': 0})
# jittery_motor1 = Mover('jittery_motor1',
#                        OrderedDict([('jittery_motor1',
#                                      lambda x: x + np.random.randn()),
#                                     ('jittery_motor1_setpoint', lambda x: x)]),
#                        {'x': 0})
# jittery_motor2 = Mover('jittery_motor2',
#                        OrderedDict([('jittery_motor2',
#                                      lambda x: x + np.random.randn()),
#                                     ('jittery_motor2_setpoint', lambda x: x)]),
#                        {'x': 0})
# noisy_det = SynGauss('noisy_det', motor, 'motor', center=0, Imax=1,
#                      noise='uniform', sigma=1, noise_multiplier=0.1)
# det = SynGauss('det', motor, 'motor', center=0, Imax=1, sigma=1)
# det1 = SynGauss('det1', motor1, 'motor1', center=0, Imax=5, sigma=0.5)
# det2 = SynGauss('det2', motor2, 'motor2', center=1, Imax=2, sigma=2)
# det3 = SynGauss('det3', motor3, 'motor3', center=-1, Imax=2, sigma=1)
# det4 = Syn2DGauss('det4', motor1, 'motor1', motor2, 'motor2',
#                   center=(0, 0), Imax=1)
# det5 = Syn2DGauss('det5', jittery_motor1, 'jittery_motor1', jittery_motor2,
#                   'jittery_motor2', center=(0, 0), Imax=1)
# 
# flyer1 = MockFlyer('flyer1', det, motor, 1, 5, 20)
# flyer2 = MockFlyer('flyer2', det, motor, 1, 5, 10)