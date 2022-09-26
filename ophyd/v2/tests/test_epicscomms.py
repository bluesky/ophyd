from typing import Callable, cast
from unittest.mock import Mock, patch

import pytest
from bluesky.protocols import Descriptor, Reading

from ophyd.v2._channel import Channel, uninstantiatable_channel
from ophyd.v2._channelsim import SimMonitor
from ophyd.v2.core import HasReadableSignals, T
from ophyd.v2.epics import EpicsSignalR, EpicsSignalRW, Monitor


def test_uninstantiatable_channel():
    pv = uninstantiatable_channel("ca")
    with pytest.raises(LookupError) as cm:
        pv("pv_prefix")
    assert (
        str(cm.value) == "Can't make a ca pv as the correct libraries are not installed"
    )


def test_hashing_signal():
    s = EpicsSignalR(float)
    s2 = EpicsSignalR(float)
    assert len({s, s2}) == 2


async def test_disconnected_signal():
    match = "No PV has been set as EpicsSignal.connect has not been called"
    signal = EpicsSignalRW(int)
    assert not signal.source
    with pytest.raises(NotImplementedError, match=match):
        await signal.read_channel.connect()
    with pytest.raises(NotImplementedError, match=match):
        await signal.read()
    with pytest.raises(NotImplementedError, match=match):
        await signal.set(1)
    with pytest.raises(NotImplementedError, match=match):
        await signal.describe()
    with pytest.raises(NotImplementedError, match=match):
        await signal.get_value()
    with pytest.raises(NotImplementedError, match=match):
        signal.subscribe(print)
    with pytest.raises(NotImplementedError, match=match):
        signal.subscribe_value(print)


class MockPv(Channel[T]):
    descriptor: Mock = Mock()
    reading: Mock = Mock()
    monitored: Mock = Mock()

    @property
    def source(self) -> str:
        return "something"

    async def connect(self):
        pass

    async def put(self, value: T, wait=True):
        pass

    async def get_descriptor(self) -> Descriptor:
        return self.descriptor()

    async def get_reading(self) -> Reading:
        return self.reading()

    async def get_value(self) -> T:
        return self.reading()["value"]

    def monitor_reading_value(self, callback: Callable[[Reading, T], None]) -> Monitor:
        self.monitored()
        m = Mock()
        callback(m, m.value)
        return SimMonitor(callback, [])


def do_nothing(value):
    pass


class MyHasReadableSignals(HasReadableSignals):
    """To satisfy mypy that name is concrete when instantiating below"""

    name = ""


async def test_readable_signals_cached_read() -> None:
    sig = EpicsSignalR(float, "blah")
    with patch("ophyd.v2.epics.ChannelSim", MockPv):
        await sig.connect(sim=True)
    pv = cast(MockPv, sig.read_channel)
    sc = MyHasReadableSignals()
    sc.set_readable_signals(read=[sig])
    # To start there is no monitoring
    assert sig._monitor is None
    # Now start caching
    sc.stage()
    assert sig._monitor
    # Check that calling read will call monitor
    assert pv.reading.call_count == 0
    assert pv.monitored.call_count == 1
    reading1 = await sc.read()
    assert pv.reading.call_count == 0
    assert pv.monitored.call_count == 1
    # And calling a second time uses cached result
    reading2 = await sc.read()
    assert pv.reading.call_count == 0
    assert pv.monitored.call_count == 1
    assert reading1 == reading2
    # When we make a second cache it should give the same thing
    # without doing another read
    assert (await sig.read()) == reading1
    assert pv.reading.call_count == 0
    assert pv.monitored.call_count == 1
    # Same with value
    assert (await sig.get_value()) is reading1[""].value
    assert pv.reading.call_count == 0
    assert pv.monitored.call_count == 1
    # Adding a monitor should keep it alive
    sig.subscribe(do_nothing)
    sc.unstage()
    assert sig._monitor
    # But closing the monitor does gc
    sig.clear_sub(do_nothing)
    assert sig._monitor is None
    # And read calls the right thing
    await sc.read()
    assert pv.reading.call_count == 1
    assert pv.monitored.call_count == 1
    # Starting monitoring again gives a different cached value
    sc.stage()
    reading3 = await sig.read()
    assert pv.reading.call_count == 1
    assert pv.monitored.call_count == 2
    assert reading1 != reading3
    # GC will stop caching
    del sc
    await sig.read()
    assert pv.reading.call_count == 2
    assert pv.monitored.call_count == 2
