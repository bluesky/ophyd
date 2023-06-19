import asyncio
import re
import traceback
from unittest.mock import Mock

import bluesky.plan_stubs as bps
import pytest
from bluesky import FailedStatus, RunEngine
from bluesky.protocols import Movable, Status

from ophyd.v2.core import (
    AsyncStatus,
    Device,
    DeviceCollector,
    DeviceVector,
    Signal,
    SimSignalBackend,
    get_device_children,
    set_sim_put_proceeds,
    wait_for_connection,
)


class MySignal(Signal):
    @property
    def source(self) -> str:
        return "me"

    async def connect(self, sim=False):
        pass


def test_signals_equality_raises():
    sim_backend = SimSignalBackend(str, "test")

    s1 = MySignal(sim_backend)
    s2 = MySignal(sim_backend)
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


class DummyBaseDevice(Device):
    def __init__(self) -> None:
        self.connected = False

    async def connect(self, sim=False):
        self.connected = True


class DummyDeviceGroup(Device):
    def __init__(self, name: str) -> None:
        self.child1 = DummyBaseDevice()
        self.child2 = DummyBaseDevice()
        self.dict_with_children: DeviceVector[DummyBaseDevice] = DeviceVector(
            {123: DummyBaseDevice()}
        )
        self.set_name(name)


def test_get_device_children():
    parent = DummyDeviceGroup("parent")

    names = ["child1", "child2", "dict_with_children"]
    for idx, (name, child) in enumerate(get_device_children(parent)):
        assert name == names[idx]
        assert (
            type(child) == DummyBaseDevice
            if name.startswith("child")
            else type(child) == DeviceVector
        )


async def test_children_of_device_have_set_names_and_get_connected():
    parent = DummyDeviceGroup("parent")

    assert parent.name == "parent"
    assert parent.child1.name == "parent-child1"
    assert parent.child2.name == "parent-child2"
    assert parent.dict_with_children.name == "parent-dict_with_children"
    assert parent.dict_with_children[123].name == "parent-dict_with_children-123"

    await parent.connect()

    assert parent.child1.connected
    assert parent.dict_with_children[123].connected


async def test_device_with_device_collector():
    async with DeviceCollector(sim=True):
        parent = DummyDeviceGroup("parent")

    assert parent.name == "parent"
    assert parent.child1.name == "parent-child1"
    assert parent.child2.name == "parent-child2"
    assert parent.dict_with_children.name == "parent-dict_with_children"
    assert parent.dict_with_children[123].name == "parent-dict_with_children-123"
    assert parent.child1.connected
    assert parent.dict_with_children[123].connected


async def normal_coroutine(time: float):
    await asyncio.sleep(time)


async def failing_coroutine(time: float):
    await normal_coroutine(time)
    raise ValueError()


async def test_async_status_propagates_exception():
    status = AsyncStatus(failing_coroutine(0.1))
    assert status.exception() is None

    with pytest.raises(ValueError):
        await status

    assert type(status.exception()) == ValueError


async def test_async_status_propagates_cancelled_error():
    status = AsyncStatus(normal_coroutine(0.1))
    assert status.exception() is None

    status.task.exception = Mock(side_effect=asyncio.CancelledError(""))
    await status

    assert type(status.exception()) == asyncio.CancelledError


async def test_async_status_has_no_exception_if_coroutine_successful():
    status = AsyncStatus(normal_coroutine(0.1))
    assert status.exception() is None

    await status

    assert status.exception() is None


async def test_async_status_success_if_cancelled():
    status = AsyncStatus(normal_coroutine(0.1))
    assert status.exception() is None
    status.task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await status
    assert status.success is False
    assert isinstance(status.exception(), asyncio.CancelledError)


async def test_async_status_wrap():
    wrapped_coroutine = AsyncStatus.wrap(normal_coroutine)
    status = wrapped_coroutine(0.1)

    await status
    assert status.success is True


async def test_async_status_initialised_with_a_task():
    normal_task = asyncio.Task(normal_coroutine(0.1))
    status = AsyncStatus(normal_task)

    await status
    assert status.success is True


async def test_async_status_str_for_normal_coroutine():
    normal_task = asyncio.Task(normal_coroutine(0.01))
    status = AsyncStatus(normal_task)

    assert str(status) == "<AsyncStatus pending>"
    await status

    assert str(status) == "<AsyncStatus done>"


async def test_async_status_str_for_failing_coroutine():
    failing_task = asyncio.Task(failing_coroutine(0.01))
    status = AsyncStatus(failing_task)

    assert str(status) == "<AsyncStatus pending>"
    with pytest.raises(ValueError):
        await status

    assert str(status) == "<AsyncStatus errored>"


async def test_wait_for_connection():
    class DummyDeviceWithSleep(DummyBaseDevice):
        def __init__(self, name) -> None:
            self.set_name(name)

        async def connect(self, sim=False):
            await asyncio.sleep(0.01)
            self.connected = True

    device1, device2 = DummyDeviceWithSleep("device1"), DummyDeviceWithSleep("device2")

    normal_coros = {"device1": device1.connect(), "device2": device2.connect()}

    await wait_for_connection(**normal_coros)

    assert device1.connected
    assert device2.connected


async def test_wait_for_connection_propagates_error():
    failing_coros = {"test": normal_coroutine(0.01), "failing": failing_coroutine(0.01)}

    with pytest.raises(ValueError) as e:
        await wait_for_connection(**failing_coros)
        assert traceback.extract_tb(e.__traceback__)[-1].name == "failing_coroutine"


class FailingMovable(Movable, Device):
    def _fail(self):
        raise ValueError("This doesn't work")

    async def _set(self, value):
        if value:
            self._fail()

    def set(self, value) -> AsyncStatus:
        return AsyncStatus(self._set(value))


async def test_status_propogates_traceback_under_RE() -> None:
    expected_call_stack = ["_set", "_fail"]
    RE = RunEngine()
    d = FailingMovable()
    with pytest.raises(FailedStatus) as ctx:
        RE(bps.mv(d, 3))
    # We get "The above exception was the direct cause of the following exception:",
    # so extract that first exception traceback and check
    assert ctx.value.__cause__
    assert expected_call_stack == [
        x.name for x in traceback.extract_tb(ctx.value.__cause__.__traceback__)
    ]
    # Check we get the same from the status.exception
    status: AsyncStatus = ctx.value.args[0]
    exception = status.exception()
    assert exception
    assert expected_call_stack == [
        x.name for x in traceback.extract_tb(exception.__traceback__)
    ]


async def test_set_sim_put_proceeds():
    sim_signal = Signal(SimSignalBackend(str, "test"))
    await sim_signal.connect(sim=True)

    assert sim_signal._backend.put_proceeds.is_set() is True

    set_sim_put_proceeds(sim_signal, False)
    assert sim_signal._backend.put_proceeds.is_set() is False
    set_sim_put_proceeds(sim_signal, True)
    assert sim_signal._backend.put_proceeds.is_set() is True


async def test_sim_backend_descriptor_fails_for_invalid_class():
    class myClass:
        def __init__(self) -> None:
            pass

    sim_signal = Signal(SimSignalBackend(myClass, "test"))
    await sim_signal.connect(sim=True)

    with pytest.raises(AssertionError):
        await sim_signal._backend.get_descriptor()
