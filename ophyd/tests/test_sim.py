from ophyd.sim import (SynGauss, Syn2DGauss, SynAxis,
                       make_fake_device, FakeEpicsSignal, FakeEpicsSignalRO)
from ophyd.device import (Device, Component as Cpt, FormattedComponent as FCpt,
                          DynamicDeviceComponent as DDCpt)
from ophyd.signal import Signal, EpicsSignal, EpicsSignalRO
from ophyd.utils import ReadOnlyError, LimitError, DisconnectedError
import numpy as np
import pytest


def test_random_state_gauss1d():
    """With given random state, the output value should stay the same.
    Test performs on 1D gaussian.
    """
    dlist = []
    motor = SynAxis(name='motor')
    for i in range(2):
        s = np.random.RandomState(0)
        noisy_det = SynGauss('noisy_det', motor, 'motor', center=0, Imax=1,
                             noise='uniform', sigma=1, noise_multiplier=0.1,
                             random_state=s)
        noisy_det.trigger()
        d = noisy_det.read()['noisy_det']['value']
        dlist.append(d)
    assert dlist[0] == dlist[1]

    # Without random state, output will be different.
    dlist.clear()
    for i in range(2):
        noisy_det = SynGauss('noisy_det', motor, 'motor', center=0, Imax=1,
                             noise='uniform', sigma=1, noise_multiplier=0.1)
        noisy_det.trigger()
        d = noisy_det.read()['noisy_det']['value']
        dlist.append(d)
    assert dlist[0] != dlist[1]


def test_random_state_gauss2d():
    """With given random state, the output value should stay the same.
    Test performs on 2D gaussian.
    """
    dlist = []
    motor1 = SynAxis(name='motor1')
    motor2 = SynAxis(name='motor2')
    for i in range(2):
        s = np.random.RandomState(0)
        noisy_det = Syn2DGauss('noisy_det', motor1, 'motor1', motor2, 'motor2',
                               center=(0, 0), Imax=1, noise='uniform',
                               sigma=1, noise_multiplier=0.1, random_state=s)
        noisy_det.trigger()
        d = noisy_det.read()['noisy_det']['value']
        dlist.append(d)
    assert dlist[0] == dlist[1]


def test_synaxis_subcribe():
    hits = dict.fromkeys(['r', 's', 'a'], 0)
    vals = dict.fromkeys(['r', 's', 'a'], None)

    def p1(tar, value):
        hits[tar] += 1
        vals[tar] = value

    motor = SynAxis(name='motor1')
    # prime the cb cache so these run an subscription
    motor.set(0)
    motor.subscribe(lambda *, value, _tar='a', **kwargs:
                    p1(_tar, value))
    motor.readback.subscribe(lambda *, value, _tar='r', **kwargs:
                             p1(_tar, value))
    motor.setpoint.subscribe(lambda *, value, _tar='s', **kwargs:
                             p1(_tar, value))

    assert vals['r'] == motor.readback.get()
    assert vals['a'] == motor.readback.get()
    assert vals['s'] == motor.setpoint.get()

    assert all(v == 1 for v in hits.values())

    motor.set(1)

    assert vals['r'] == motor.readback.get()
    assert vals['a'] == motor.readback.get()
    assert vals['s'] == motor.setpoint.get()

    assert all(v == 2 for v in hits.values())


def test_synaxis_timestamps():
    from ophyd.status import wait
    import time

    def time_getter(m):
        return {k: v['timestamp']
                for k, v in m.read().items()}

    def tester(m, orig_time):
        new_time = time_getter(m)
        assert orig_time != new_time
        return new_time

    motor = SynAxis(name='motor1')
    motor.delay = .01
    orig_time = time_getter(motor)

    wait(motor.set(3))
    orig_time = tester(motor, orig_time)

    wait(motor.setpoint.set(4))
    orig_time = tester(motor, orig_time)

    motor.setpoint.put(3)
    time.sleep(2*motor.delay)
    orig_time = tester(motor, orig_time)


# Classes for testing make_fake_device
class SampleNested(Device):
    yolk = Cpt(EpicsSignal, ':YOLK')
    whites = Cpt(EpicsSignalRO, ':WHITES')


class Sample(Device):
    egg = Cpt(SampleNested, ':EGG')
    butter = Cpt(EpicsSignal, ':BUTTER')
    flour = Cpt(EpicsSignalRO, ':FLOUR')
    sink = FCpt(EpicsSignal, '{self.sink_location}:SINK')
    fridge = DDCpt({'milk': (EpicsSignal, ':MILK', {}),
                    'cheese': (EpicsSignalRO, ':CHEESE', {})})
    nothing = Cpt(Signal)

    sink_location = 'COUNTER'


def test_make_fake_device():
    assert make_fake_device(EpicsSignal) == FakeEpicsSignal
    assert make_fake_device(EpicsSignalRO) == FakeEpicsSignalRO

    FakeSample = make_fake_device(Sample)
    my_fake = FakeSample('KITCHEN', name='kitchen')
    assert isinstance(my_fake, Sample)

    # Skipped
    assert my_fake.nothing.__class__ is Signal

    # Normal
    assert isinstance(my_fake.butter, FakeEpicsSignal)
    assert isinstance(my_fake.flour, FakeEpicsSignalRO)
    assert isinstance(my_fake.sink, FakeEpicsSignal)

    # Nested
    assert isinstance(my_fake.egg.yolk, FakeEpicsSignal)
    assert isinstance(my_fake.egg.whites, FakeEpicsSignalRO)

    # Dynamic
    assert isinstance(my_fake.fridge.milk, FakeEpicsSignal)
    assert isinstance(my_fake.fridge.cheese, FakeEpicsSignalRO)

    my_fake.read()


def test_do_not_break_real_class():
    make_fake_device(Sample)
    assert Sample.butter.cls is EpicsSignal
    assert Sample.egg.cls is SampleNested
    assert SampleNested.whites.cls is EpicsSignalRO
    assert Sample.fridge.defn['milk'][0] is EpicsSignal

    with pytest.raises(DisconnectedError):
        my_real = Sample('KITCHEN', name='kitchen')
        my_real.read()


def test_fake_epics_signal():
    sig = FakeEpicsSignal('PVNAME', name='sig', limits=True)
    sig.sim_set_limits((0, 10))
    with pytest.raises(LimitError):
        sig.put(11)
    sig.put(4)
    assert sig.get() == 4
    sig.sim_put(5)
    assert sig.get() == 5
    sig.sim_set_putter(lambda x: sig.sim_put(x + 1))
    sig.put(6)
    assert sig.get() == 7


def test_fake_epics_signal_ro():
    sig = FakeEpicsSignalRO('PVNAME', name='sig')
    with pytest.raises(ReadOnlyError):
        sig.put(3)
    with pytest.raises(ReadOnlyError):
        sig.put(4)
    with pytest.raises(ReadOnlyError):
        sig.set(5)
    sig.sim_put(1)
    assert sig.get() == 1
