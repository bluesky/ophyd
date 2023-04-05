import asyncio
import re
from typing import Dict, Union

import pytest
from bluesky.protocols import Status
from bluesky.run_engine import RunEngine, TransitionError

from ophyd.v2.core import (
    AsyncStatus,
    Device,
    DeviceDict,
    Signal,
    StandardReadable,
    get_device_children,
)


@pytest.fixture(scope="function", params=[False, True])
def RE(request):
    loop = asyncio.new_event_loop()
    loop.set_debug(True)
    RE = RunEngine({}, call_returns_result=request.param, loop=loop)

    def clean_event_loop():
        if RE.state not in ("idle", "panicked"):
            try:
                RE.halt()
            except TransitionError:
                pass
        loop.call_soon_threadsafe(loop.stop)
        RE._th.join()
        loop.close()

    request.addfinalizer(clean_event_loop)
    return RE


class MySignal(Signal):
    @property
    def source(self) -> str:
        return "me"

    async def connect(self, prefix: str = "", sim=False):
        pass


def test_signals_equality_raises():
    s1 = MySignal()
    s2 = MySignal()
    with pytest.raises(
        TypeError,
        match=re.escape(
            "Can't compare two Signals, did you mean await signal.get_value() instead?"
        ),
    ):
        s1 == s2
    with pytest.raises(
        TypeError,
        match=re.escape("'>' not supported between instances of 'MySignal' and 'int'"),
    ):
        s1 > 4


async def test_async_status_success():
    st = AsyncStatus(asyncio.sleep(0.1))
    assert isinstance(st, Status)
    assert not st.done
    assert not st.success
    await st
    assert st.done
    assert st.success


class DummyDevice(Device):
    def __init__(self, name) -> None:
        self._name = name
        self.connected = False

    @property
    def name(self):
        return self._name

    def set_name(self, name: str = ""):
        self._name = name

    async def connect(self, prefix: str = "", sim=False):
        self.connected = True


class Dummy(DummyDevice):
    def __init__(self, name) -> None:
        self.child1 = DummyDevice("device1")
        self.child2 = DummyDevice("device2")
        super().__init__(name)


class DummyStandardReadable(StandardReadable):
    def __init__(self, prefix: str, name: str = ""):
        self.child1 = DummyDevice("device1")
        self.dict_with_children: Dict[Union[int, str], DummyDevice] = DeviceDict(
            {
                "abc": DummyDevice("device2"),
                123: DummyDevice("device3"),
            }
        )
        super().__init__(prefix, name)


def test_get_device_children():
    parent = Dummy("parent")
    names = ["child1", "child2"]
    for idx, (name, child) in enumerate(get_device_children(parent)):
        assert name == names[idx]
        assert type(child) == DummyDevice


async def test_names_correctly_set_with():
    parent = DummyStandardReadable("parent")
    parent.set_name("parent")
    assert parent.child1.name == "parent-child1"
    assert parent.dict_with_children[123].name == "parent-dict_with_children-123"
    assert parent.dict_with_children["abc"].name == "parent-dict_with_children-abc"

    await parent.connect()

    assert parent.child1.connected
    assert parent.dict_with_children[123].connected
    assert parent.dict_with_children["abc"].connected
