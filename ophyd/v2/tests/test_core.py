import asyncio
import re
import time
import traceback
from enum import Enum
from typing import Any, Callable, Sequence, Tuple, Type
from unittest.mock import Mock

import bluesky.plan_stubs as bps
import numpy as np
import numpy.typing as npt
import pytest
from bluesky import FailedStatus, RunEngine
from bluesky.protocols import Movable, Reading, Status

from ophyd.v2.core import (
    AsyncStatus,
    Device,
    DeviceCollector,
    DeviceVector,
    Signal,
    SignalBackend,
    SimSignalBackend,
    T,
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


class MyEnum(str, Enum):
    a = "Aaa"
    b = "Bbb"
    c = "Ccc"


def integer_d(value):
    return dict(dtype="integer", shape=[])


def number_d(value):
    return dict(dtype="number", shape=[])


def string_d(value):
    return dict(dtype="string", shape=[])


def enum_d(value):
    return dict(dtype="string", shape=[], choices=["Aaa", "Bbb", "Ccc"])


def waveform_d(value):
    return dict(dtype="array", shape=[len(value)])


class MonitorQueue:
    def __init__(self, backend: SignalBackend):
        self.backend = backend
        self.updates: asyncio.Queue[Tuple[Reading, Any]] = asyncio.Queue()
        backend.set_callback(self.add_reading_value)

    def add_reading_value(self, reading: Reading, value):
        self.updates.put_nowait((reading, value))

    async def assert_updates(self, expected_value):
        expected_reading = {
            "value": expected_value,
            "timestamp": pytest.approx(time.monotonic(), rel=0.1),
            "alarm_severity": 0,
        }
        reading, value = await self.updates.get()
        
        backend_value = await self.backend.get_value()
        backend_reading = await self.backend.get_reading()

        assert value == expected_value == backend_value, f"value: {backend_value}"
        assert reading == expected_reading == backend_reading, f"reading: got {backend_reading} but expected {expected_reading}. got value: {expected_value} but expected {expected_value}"

    def close(self):
        self.backend.set_callback(None)
    

@pytest.mark.parametrize(
    "datatype, initial_value, put_value, descriptor",
    [
        (int, 0, 43, integer_d),
        (float, 0.0, 43.5, number_d),
        (str, "", "goodbye", string_d),
        (MyEnum, MyEnum.a, MyEnum.c, enum_d),
        (npt.NDArray[np.int8], [], [-8, 3, 44], waveform_d),
        (npt.NDArray[np.uint8], [], [218], waveform_d),
        (npt.NDArray[np.int16], [], [-855], waveform_d),
        (npt.NDArray[np.uint16], [], [5666], waveform_d),
        (npt.NDArray[np.int32], [], [-2], waveform_d),
        (npt.NDArray[np.uint32], [], [1022233], waveform_d),
        (npt.NDArray[np.int64], [], [-3], waveform_d),
        (npt.NDArray[np.uint64], [], [995444], waveform_d),
        (npt.NDArray[np.float32], [], [1.0], waveform_d),
        (npt.NDArray[np.float64], [], [0.2], waveform_d),
        (Sequence[str], [], ["nine", "ten"], waveform_d),
        # Can't do long strings until https://github.com/epics-base/pva2pva/issues/17
        # (str, "longstr", ls1, ls2, string_d),
        # (str, "longstr2.VAL$", ls1, ls2, string_d),
    ],
)
async def test_backend_get_put_monitor(
    datatype: Type[T],
    initial_value: T,
    put_value: T,
    descriptor: Callable[[Any], dict],
):
    backend = SimSignalBackend(datatype, "")

    await backend.connect()
    q = MonitorQueue(backend)
    try:
        # Check descriptor
        assert dict(source="sim://", **descriptor(initial_value)) == await backend.get_descriptor()
        # Check initial value
        await q.assert_updates(pytest.approx(initial_value) if initial_value != "" else initial_value)
        # Put to new value and check that
        await backend.put(put_value)
        await q.assert_updates(pytest.approx(put_value))
    finally:
        q.close()


async def test_sim_backend_with_numpy_typing():
    sim_backend = SimSignalBackend(npt.NDArray[np.float64], pv="SOME-IOC:PV")
    await sim_backend.connect()

    array = await sim_backend.get_value()
    assert array.shape == (0,)


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
