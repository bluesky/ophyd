from __future__ import annotations

import asyncio
import time
from typing import Dict, Generic, List, Sequence, Type, TypeVar

from bluesky.protocols import Descriptor, Dtype, Reading
from typing_extensions import Protocol

from ._channel import Channel, Monitor, ReadingValueCallback
from .core import T

primitive_dtypes: Dict[type, Dtype] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def make_sim_descriptor(source: str, value) -> Descriptor:
    try:
        dtype = primitive_dtypes[type(value)]
        shape = []
    except KeyError:
        assert isinstance(value, Sequence), f"Can't get dtype for {type(value)}"
        dtype = "array"
        shape = [len(value)]
    return dict(source=source, dtype=dtype, shape=shape)


ValueT = TypeVar("ValueT", contravariant=True)


class PutHandler(Protocol, Generic[ValueT]):
    async def __call__(self, value: ValueT) -> None:
        pass


class SimMonitor(Generic[T]):
    def __init__(
        self, callback: ReadingValueCallback[T], listeners: List[SimMonitor[T]]
    ):
        self.callback = callback
        self._listeners = listeners
        self._listeners.append(self)

    def close(self):
        self._listeners.remove(self)


class ChannelSim(Channel[T]):
    _value: T
    _timestamp: float

    def __init__(self, pv: str, datatype: Type[T]):
        super().__init__(pv, datatype)
        #: If cleared, then any `put(wait=True)` will wait until it is set
        self.put_proceeds = asyncio.Event()
        self.put_proceeds.set()
        self._listeners: List[SimMonitor[T]] = []
        self.set_value(datatype())

    @property
    def source(self) -> str:
        return f"sim://{self.pv}"

    async def connect(self):
        pass

    async def put(self, value: T, wait=True):
        self.set_value(value)
        if wait:
            await self.put_proceeds.wait()

    async def get_descriptor(self) -> Descriptor:
        return make_sim_descriptor(self.source, self._value)

    @property
    def _reading(self) -> Reading:
        return dict(value=self._value, timestamp=self._timestamp)

    async def get_reading(self) -> Reading:
        return self._reading

    async def get_value(self) -> T:
        return self._value

    def monitor_reading_value(self, callback: ReadingValueCallback[T]) -> Monitor:
        callback(self._reading, self._value)
        return SimMonitor(callback, self._listeners)

    def set_value(self, value: T) -> None:
        """Set the simulated value, and set timestamp to now"""
        self._value = value
        self._timestamp = time.time()
        for rl in self._listeners:
            rl.callback(self._reading, self._value)
