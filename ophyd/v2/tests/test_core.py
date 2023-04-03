import asyncio
import re
from typing import Callable, Optional
from unittest.mock import Mock

import pytest
from bluesky.protocols import Descriptor, Reading, Status

from ophyd.v2.core import (
    AsyncStatus,
    Monitor,
    Signal,
    SignalBackend,
    SignalR,
    SimMonitor,
    SimSignalBackend,
    StandardReadable,
    T,
    wait_for_value,
)

# Long enough for multiple asyncio event loop cycles to run so
# all the tasks have a chance to run
A_WHILE = 0.001


def test_hashing_signal():
    s = Signal(None)
    s2 = Signal(None)
    assert len({s, s2}) == 2


def test_signals_equality_raises():
    s1 = Signal(None)
    s2 = Signal(None)
    with pytest.raises(
        TypeError,
        match=re.escape(
            "Can't compare two Signals, did you mean await signal.get_value() instead?"
        ),
    ):
        s1 == s2
    with pytest.raises(
        TypeError,
        match=re.escape("'>' not supported between instances of 'Signal' and 'int'"),
    ):
        s1 > 4


async def test_wait_for_value_function():
    backend = SimSignalBackend(int, "test")
    s = SignalR(backend)
    backend.set_value(3)
    t = asyncio.create_task(wait_for_value(s, lambda x: x > 4))
    await asyncio.sleep(A_WHILE)
    assert not t.done()
    backend.set_value(4)
    await asyncio.sleep(A_WHILE)
    assert not t.done()
    backend.set_value(5)
    await asyncio.sleep(A_WHILE)
    assert t.done()
    await t


async def test_wait_for_value_equality():
    backend = SimSignalBackend(int, "test")
    s = SignalR(backend)
    backend.set_value(3)
    t = asyncio.create_task(wait_for_value(s, 4))
    await asyncio.sleep(A_WHILE)
    assert not t.done()
    backend.set_value(4)
    await asyncio.sleep(A_WHILE)
    assert t.done()
    await t


async def test_wait_for_value_timeout():
    backend = SimSignalBackend(int, "test")
    s = SignalR(backend)
    with pytest.raises(asyncio.TimeoutError):
        await wait_for_value(s, lambda x: x > 4, timeout=0.1)


async def test_async_status_success():
    st = AsyncStatus(asyncio.sleep(0.1))
    assert isinstance(st, Status)
    assert not st.done
    assert not st.success
    await st
    assert st.done
    assert st.success


class MockBackend(SignalBackend):
    descriptor: Mock = Mock()
    reading: Mock = Mock()
    monitored: Mock = Mock()
    source = "something"

    async def connect(self):
        pass

    async def put(self, value: Optional[T], wait=True, timeout=None):
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


async def test_readable_signals_cached_read() -> None:
    backend = MockBackend()
    sig = SignalR(backend)
    sc = StandardReadable("", read=[sig])
    # To start there is no monitoring
    assert sig._cache is None
    # Now start caching
    sc.stage()
    assert sig._cache
    # Check that calling read will call monitor
    assert backend.reading.call_count == 0
    assert backend.monitored.call_count == 1
    reading1 = await sc.read()
    assert backend.reading.call_count == 0
    assert backend.monitored.call_count == 1
    # And calling a second time uses cached result
    reading2 = await sc.read()
    assert backend.reading.call_count == 0
    assert backend.monitored.call_count == 1
    assert reading1 == reading2
    # When we make a second cache it should give the same thing
    # without doing another read
    assert (await sig.read()) == reading1
    assert backend.reading.call_count == 0
    assert backend.monitored.call_count == 1
    # Same with value
    assert (await sig.get_value()) is reading1[""].value
    assert backend.reading.call_count == 0
    assert backend.monitored.call_count == 1
    # Adding a monitor should keep it alive
    sig.subscribe(do_nothing)
    sc.unstage()
    assert sig._cache
    # But closing the monitor does gc
    sig.clear_sub(do_nothing)
    assert sig._cache is None
    # And read calls the right thing
    await sc.read()
    assert backend.reading.call_count == 1
    assert backend.monitored.call_count == 1
    # Starting monitoring again gives a different cached value
    sc.stage()
    reading3 = await sig.read()
    assert backend.reading.call_count == 1
    assert backend.monitored.call_count == 2
    assert reading1 != reading3
