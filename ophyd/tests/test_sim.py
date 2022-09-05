import shutil
import tempfile
from typing import Callable

import numpy as np
import pytest

from ophyd.areadetector.base import EpicsSignalWithRBV
from ophyd.areadetector.paths import EpicsPathSignal
from ophyd.device import Component as Cpt
from ophyd.device import Device
from ophyd.device import DynamicDeviceComponent as DDCpt
from ophyd.device import FormattedComponent as FCpt
from ophyd.signal import EpicsSignal, EpicsSignalRO, Signal
from ophyd.sim import (
    FakeEpicsPathSignal,
    FakeEpicsSignal,
    FakeEpicsSignalRO,
    FakeEpicsSignalWithRBV,
    Syn2DGauss,
    SynAxis,
    SynAxisEmptyHints,
    SynAxisNoHints,
    SynAxisNoPosition,
    SynGauss,
    SynSignalWithRegistry,
    clear_fake_device,
    instantiate_fake_device,
    make_fake_device,
)
from ophyd.utils import DisconnectedError, LimitError, ReadOnlyError


def test_random_state_gauss1d():
    """With given random state, the output value should stay the same.
    Test performs on 1D gaussian.
    """
    dlist = []
    motor = SynAxis(name="motor")
    for i in range(2):
        s = np.random.RandomState(0)
        noisy_det = SynGauss(
            "noisy_det",
            motor,
            "motor",
            center=0,
            Imax=1,
            noise="uniform",
            sigma=1,
            noise_multiplier=0.1,
            random_state=s,
        )
        noisy_det.trigger()
        d = noisy_det.read()["noisy_det"]["value"]
        dlist.append(d)
    assert dlist[0] == dlist[1]

    # Without random state, output will be different.
    dlist.clear()
    for i in range(2):
        noisy_det = SynGauss(
            "noisy_det",
            motor,
            "motor",
            center=0,
            Imax=1,
            noise="uniform",
            sigma=1,
            noise_multiplier=0.1,
        )
        noisy_det.trigger()
        d = noisy_det.read()["noisy_det"]["value"]
        dlist.append(d)
    assert dlist[0] != dlist[1]


def test_random_state_gauss2d():
    """With given random state, the output value should stay the same.
    Test performs on 2D gaussian.
    """
    dlist = []
    motor1 = SynAxis(name="motor1")
    motor2 = SynAxis(name="motor2")
    for i in range(2):
        s = np.random.RandomState(0)
        noisy_det = Syn2DGauss(
            "noisy_det",
            motor1,
            "motor1",
            motor2,
            "motor2",
            center=(0, 0),
            Imax=1,
            noise="uniform",
            sigma=1,
            noise_multiplier=0.1,
            random_state=s,
        )
        noisy_det.trigger()
        d = noisy_det.read()["noisy_det"]["value"]
        dlist.append(d)
    assert dlist[0] == dlist[1]


@pytest.mark.parametrize("events_per_move", [0, -1, -10])
def test_synaxis_requires_at_least_1_event_per_move(events_per_move):
    with pytest.raises(ValueError):
        SynAxis(name="motor1", events_per_move=0)


@pytest.mark.parametrize(
    "motor_factory",
    [
        lambda: SynAxis(name="motor", value=0.0),
        lambda: SynAxisEmptyHints(name="motor", value=0.0),
        lambda: SynAxisNoHints(name="motor", value=0.0),
        lambda: SynAxisNoPosition(name="motor", value=0.0),
    ],
)
def test_move_synaxis(motor_factory: Callable[[], SynAxis]):
    # Test is run twice, once for caproto and once for pyepics, so we need a
    # factory rather than a global object to preserve state management
    motor = motor_factory()

    initial_value = motor.readback.get()
    motor.set(1.0).wait()
    final_value = motor.readback.get()

    assert initial_value == 0.0
    assert final_value == 1.0


def test_synaxisnoposition_has_no_position():
    motor = SynAxisNoPosition(name="motor", labels={"motors"})
    with pytest.raises(AttributeError):
        motor.position


@pytest.mark.parametrize("events_per_move", [1, 2, 6, 20])
def test_synaxis_subcribe(events_per_move: int):
    hits = dict.fromkeys(["r", "s", "a"], 0)
    vals = dict.fromkeys(["r", "s", "a"], None)

    def p1(tar, value):
        hits[tar] += 1
        vals[tar] = value

    motor = SynAxis(name="motor1", events_per_move=events_per_move)
    # prime the cb cache so these run an subscription
    motor.set(0)
    motor.subscribe(lambda *, value, _tar="a", **kwargs: p1(_tar, value))
    motor.readback.subscribe(lambda *, value, _tar="r", **kwargs: p1(_tar, value))
    motor.setpoint.subscribe(lambda *, value, _tar="s", **kwargs: p1(_tar, value))

    assert vals["r"] == motor.readback.get()
    assert vals["a"] == motor.readback.get()
    assert vals["s"] == motor.setpoint.get()

    assert all(v == 1 for v in hits.values())

    motor.set(1)

    assert vals["r"] == motor.readback.get()
    assert vals["a"] == motor.readback.get()
    assert vals["s"] == motor.setpoint.get()

    assert hits["r"] == 1 + events_per_move
    assert hits["a"] == 1 + events_per_move
    assert hits["s"] == 2


def test_synaxis_timestamps():
    import time

    from ophyd.status import wait

    def time_getter(m):
        return {k: v["timestamp"] for k, v in m.read().items()}

    def tester(m, orig_time):
        new_time = time_getter(m)
        assert orig_time != new_time
        return new_time

    motor = SynAxis(name="motor1")
    motor.delay = 0.01
    orig_time = time_getter(motor)

    wait(motor.set(3))
    orig_time = tester(motor, orig_time)

    wait(motor.setpoint.set(4))
    orig_time = tester(motor, orig_time)

    motor.setpoint.put(3)
    time.sleep(2 * motor.delay)
    orig_time = tester(motor, orig_time)


# Classes for testing make_fake_device
class SampleNested(Device):
    yolk = Cpt(EpicsSignal, ":YOLK", string=True)
    whites = Cpt(EpicsSignalRO, ":WHITES")


class Sample(Device):
    egg = Cpt(SampleNested, ":EGG")
    butter = Cpt(
        EpicsSignal,
        ":BUTTER",
        timeout=10.0,
        write_timeout=10.0,
        connection_timeout=10.0,
    )
    flour = Cpt(EpicsSignalRO, ":FLOUR")
    baster = FCpt(EpicsSignal, "{self.drawer}:BASTER")
    sink = FCpt(EpicsSignal, "{self.sink_location}:SINK")
    fridge = DDCpt(
        {"milk": (EpicsSignal, ":MILK", {}), "cheese": (EpicsSignalRO, ":CHEESE", {})}
    )
    nothing = Cpt(Signal)

    def __init__(
        self, prefix, *, drawer="UNDER_THE_SINK", sink_location="COUNTER", **kwargs
    ):
        self.drawer = drawer
        self.sink_location = sink_location
        super().__init__(prefix, **kwargs)


def test_make_fake_device():
    assert make_fake_device(EpicsSignal) == FakeEpicsSignal
    assert make_fake_device(EpicsSignalRO) == FakeEpicsSignalRO
    assert make_fake_device(EpicsSignalWithRBV) == FakeEpicsSignalWithRBV
    assert make_fake_device(EpicsPathSignal) == FakeEpicsPathSignal

    FakeSample = make_fake_device(Sample)
    my_fake = FakeSample("KITCHEN", name="kitchen")
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


def test_clear_fake_device():
    FakeSample = make_fake_device(Sample)
    my_fake = FakeSample("KITCHEN", name="kitchen")
    clear_fake_device(my_fake, default_value=49, default_string_value="string")
    assert my_fake.butter.get() == 49
    assert my_fake.flour.get() == 49
    assert my_fake.sink.get() == 49
    assert my_fake.egg.yolk.get() == "string"
    assert my_fake.egg.whites.get() == 49


def test_instantiate_fake_device():
    my_fake = instantiate_fake_device(Sample)
    assert my_fake.drawer == "UNDER_THE_SINK"
    assert my_fake.sink_location == "COUNTER"
    assert my_fake.name == "FakeSample"
    assert my_fake.prefix == "_prefix"

    my_fake = instantiate_fake_device(Sample, drawer="JUNK_DRAWER")
    assert my_fake.drawer == "JUNK_DRAWER"
    assert my_fake.sink_location == "COUNTER"
    assert my_fake.name == "FakeSample"


def test_do_not_break_real_class():
    make_fake_device(Sample)
    assert Sample.butter.cls is EpicsSignal
    assert Sample.egg.cls is SampleNested
    assert SampleNested.whites.cls is EpicsSignalRO
    assert Sample.fridge.defn["milk"][0] is EpicsSignal

    with pytest.raises(DisconnectedError):
        my_real = Sample("KITCHEN", name="kitchen")
        my_real.read()


def test_fake_epics_signal():
    sig = FakeEpicsSignal("PVNAME", name="sig", limits=True)
    with pytest.raises(ValueError):
        sig.put(None)
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
    assert sig.get(as_string=True) == str(7)


def test_fake_epics_signal_ro():
    sig = FakeEpicsSignalRO("PVNAME", name="sig")
    with pytest.raises(ReadOnlyError):
        sig.put(3)
    with pytest.raises(ReadOnlyError):
        sig.put(4)
    with pytest.raises(ReadOnlyError):
        sig.set(5)
    sig.sim_put(1)
    assert sig.get() == 1


def test_fake_epics_signal_enum():
    sig = FakeEpicsSignal("PVNAME", name="sig", string=True)
    sig.sim_set_enum_strs(["zero", "one", "two", "three"])
    sig.put(0)
    assert sig.describe()["sig"]["enum_strs"] == ("zero", "one", "two", "three")
    assert sig.get() == "zero"
    assert sig.get(as_string=False) == 0
    sig.put("two")
    assert sig.get(as_string=False) == 2
    with pytest.raises(ValueError):
        sig.put("bazillion")


def test_SynSignalWithRegistry():
    tempdirname = tempfile.mkdtemp()

    def data_func():
        return np.array(np.ones((10, 10)))

    img = SynSignalWithRegistry(
        data_func, save_path=tempdirname, name="img", labels={"detectors"}
    )
    img.stage()
    img.trigger()
    d0 = img.read()
    assert int(d0["img"]["value"][-1]) == 0
    img.trigger()
    d1 = img.read()
    assert int(d1["img"]["value"][-1]) == 1  # increased by 1
    shutil.rmtree(tempdirname)


def test_synaxis_describe():
    bs = pytest.importorskip("bluesky")
    import bluesky.plans as bp

    motor1 = SynAxis(name="motor1")
    RE = bs.RunEngine()
    RE(bp.scan([], motor1, -5, 5, 5))


def test_describe(hw):
    # These need to be staged and triggered before they can be described, just
    # like real area detectors do. We plan to change this approach and remove
    # this limitation in ophyd 1.6.0, but for now we'll just skip these.
    SKIP = (
        "img",
        "direct_img",
        "direct_img_list",
    )
    for name, obj in hw.__dict__.items():
        if name in SKIP:
            continue
        if hasattr(obj, "describe"):
            obj.describe()
        elif hasattr(obj, "describe_collect"):
            obj.describe_collect()
        else:
            raise AttributeError("expected describe or describe_collect")
