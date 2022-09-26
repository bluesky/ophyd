"""EPICS Signals over CA or PVA"""

from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, Type

from bluesky.protocols import Descriptor, Reading

from ._channel import DISCONNECTED_CHANNEL, Channel, Monitor, uninstantiatable_channel
from ._channelsim import ChannelSim
from .core import (
    AsyncStatus,
    Callback,
    Signal,
    SignalR,
    SignalRW,
    SignalW,
    T,
    wait_for_connection,
)

try:
    from ._channelca import ChannelCa
except ImportError:
    ChannelCa = uninstantiatable_channel("ca")  # type: ignore


class _WithDatatype(Generic[T]):
    datatype: Type[T]


__all__ = [
    # Re-export _channel.py
    "Channel",
    "Monitor",
    # Re-export _channelca.py
    "ChannelCa",
    # Re-export _channelsim.py
    "ChannelSim",
    # From this file
    "EpicsSignalR",
    "EpicsSignalRW",
    "EpicsSignalW",
    "EpicsSignalX",
    "EpicsTransport",
    "set_default_epics_transport",
]


class EpicsSignalR(SignalR[T], _WithDatatype[T]):
    """Readable EPICS Signal backed by a single PV"""

    def __init__(self, datatype: Type[T], read_pv: str = None) -> None:
        #: Request that underlying PV connection is made using this Python datatype
        self.datatype = datatype
        #: Read PV. Can be prefixed by passing prefix in `connect()`
        self.read_pv = read_pv
        #: Read `Channel`. A connected instance will be set in `connect()`
        self.read_channel: Channel[T] = DISCONNECTED_CHANNEL
        self._monitor: Optional[Monitor] = None
        self._valid = asyncio.Event()
        self._value: Optional[T] = None
        self._reading: Optional[Reading] = None
        self._value_listeners: List[Callback[T]] = []
        self._reading_listeners: List[Callback[Dict[str, Reading]]] = []
        self._staged = False

    def source(self) -> str:
        return self.read_channel.source

    async def connect(self, prefix: str = "", sim=False):
        assert self.read_pv is not None, "Read PV not set"
        self.read_channel = _make_channel_class(
            prefix + self.read_pv, self.datatype, sim, self.read_channel
        )
        await self.read_channel.connect()

    def _check_cached(self, cached: Optional[bool]) -> bool:
        if cached is None:
            cached = bool(self._monitor)
        elif cached:
            assert self._monitor, f"{self.source} not being monitored"
        return cached

    async def read(self, cached: Optional[bool] = None) -> Dict[str, Reading]:
        if self._check_cached(cached):
            await self._valid.wait()
            assert self._reading is not None, "Monitor not working"
            return {self.name: self._reading}
        else:
            return {self.name: await self.read_channel.get_reading()}

    async def describe(self) -> Dict[str, Descriptor]:
        return {self.name: await self.read_channel.get_descriptor()}

    async def get_value(self, cached: Optional[bool] = None) -> T:
        if self._check_cached(cached):
            await self._valid.wait()
            assert self._value is not None, "Monitor not working"
            return self._value
        else:
            return await self.read_channel.get_value()

    def _callback(self, reading: Reading, value: T):
        self._reading = reading
        self._value = value
        self._valid.set()
        for value_listener in self._value_listeners:
            value_listener(self._value)
        for reading_listener in self._reading_listeners:
            reading_listener({self.name: self._reading})

    def _monitor_if_needed(self) -> None:
        should_monitor = (
            self._value_listeners or self._reading_listeners or self._staged
        )
        if should_monitor and not self._monitor:
            # Start a monitor
            self._monitor = self.read_channel.monitor_reading_value(self._callback)
        elif self._monitor and not should_monitor:
            # Stop the monitor
            self._monitor.close()
            self._valid.clear()
            self._monitor = None
            self._reading = None
            self._value = None

    def subscribe_value(self, function: Callback[T]) -> None:
        self._value_listeners.append(function)
        if self._value is not None:
            function(self._value)
        self._monitor_if_needed()

    def subscribe(self, function: Callback[Dict[str, Reading]]) -> None:
        self._reading_listeners.append(function)
        if self._reading is not None:
            function({self.name: self._reading})
        self._monitor_if_needed()

    def clear_sub(self, function: Callback):
        try:
            self._value_listeners.remove(function)
        except ValueError:
            self._reading_listeners.remove(function)
        self._monitor_if_needed()

    def stage(self) -> List[Any]:
        self._staged = True
        self._monitor_if_needed()
        return [self]

    def unstage(self) -> List[Any]:
        self._staged = False
        self._monitor_if_needed()
        return [self]


class EpicsSignalW(SignalW[T], _WithDatatype[T]):
    """Writeable EPICS Signal backed by a single PV"""

    def __init__(self, datatype: Type[T], write_pv: str = None, wait=True) -> None:
        #: Request that underlying PV connection is made using this Python datatype
        self.datatype = datatype
        #: Write PV. Can be prefixed by passing prefix in `connect()`
        self.write_pv = write_pv
        #: Whether to wait for the put to callback before returning from `set()`
        self.wait = wait
        #: Write `Channel`. A connected instance will be set in `connect()`
        self.write_channel: Channel[T] = DISCONNECTED_CHANNEL

    @property
    def source(self) -> str:
        return self.write_channel.source

    async def connect(self, prefix: str = "", sim=False) -> None:
        assert self.write_pv is not None, "Write PV not set"
        self.write_channel = _make_channel_class(
            prefix + self.write_pv, self.datatype, sim, self.write_channel
        )
        await self.write_channel.connect()

    def set(self, value: T) -> AsyncStatus:
        return AsyncStatus(self.write_channel.put(value, wait=self.wait))


class EpicsSignalRW(EpicsSignalW[T], EpicsSignalR[T], SignalRW[T]):
    """Readable and Writeable EPICS Signal backed by one or two PVs"""

    # Unfortunately have to copy these here to make Sphinx autosummary happy
    #: Request that underlying PV connection is made using this Python datatype
    datatype: Type[T]
    #: Read PV. Can be prefixed by passing prefix in `connect()`
    read_pv: Optional[str]
    #: Read `Channel`. A connected instance will be set in `connect()`
    read_channel: Channel[T]
    #: Write PV. Can be prefixed by passing prefix in `connect()`
    write_pv: Optional[str]
    #: Whether to wait for the put to callback before returning from `set()`
    wait: bool
    #: Write `Channel`. A connected instance will be set in `connect()`
    write_channel: Channel[T]

    def __init__(
        self, datatype: Type[T], read_pv: str = None, write_pv: str = None, wait=True
    ) -> None:
        EpicsSignalR.__init__(self, datatype, read_pv)
        EpicsSignalW.__init__(self, datatype, write_pv, wait)

    async def connect(self, prefix: str = "", sim=False):
        assert self.read_pv is not None, "Read PV not set"
        self.read_channel = _make_channel_class(
            prefix + self.read_pv, self.datatype, sim, self.read_channel
        )
        if self.write_pv is None:
            self.write_channel = self.read_channel
            await self.read_channel.connect()
        else:
            self.write_channel = _make_channel_class(
                prefix + self.write_pv, self.datatype, sim, self.write_channel
            )
            await wait_for_connection(
                read_pv=self.read_channel.connect(),
                write_pv=self.write_channel.connect(),
            )


class EpicsSignalX(Signal):
    """Executable EPICS Signal that puts a set value to a PV on execute()"""

    def __init__(self, write_pv: str = None, write_value: Any = 0, wait=True) -> None:
        #: Write PV. Can be prefixed by passing prefix in connect()
        self.write_pv = write_pv
        #: What value to write to the PV on execute()
        self.write_value = write_value
        #: Whether to wait for the put to callback before returning from set()
        self.wait = wait
        #: Write `Channel`. A connected instance will be set in connect()
        self.write_channel: Channel = DISCONNECTED_CHANNEL

    @property
    def source(self) -> str:
        return self.write_channel.source

    async def connect(self, prefix: str = "", sim=False):
        assert self.write_pv is not None, "Write PV not set"
        self.write_channel = _make_channel_class(
            prefix + self.write_pv, type(self.write_value), sim, self.write_channel
        )
        await self.write_channel.connect()

    async def execute(self) -> None:
        """Execute the Signal, putting `write_value` to `write_pv`"""
        await self.write_channel.put(self.write_value, wait=self.wait)


class EpicsTransport(Enum):
    """The sorts of transport EPICS support"""

    #: Use Channel Access (using aioca library)
    ca = ChannelCa
    #: Use PVAccess (using p4p library)
    pva = ChannelCa  # TODO change to ChannelPva when Alan's written it


_default_epics_transport = EpicsTransport.ca


def set_default_epics_transport(epics_transport: EpicsTransport):
    """Set the default EPICS transport. Defaults to `EpicsTransport.ca`.

    If PVs are specified as ca://PV or pva://PV they will be connected with the
    requested transport. If unspecified the default EPICS transport will be
    used.
    """
    global _default_epics_transport
    _default_epics_transport = epics_transport


def _make_channel_class(
    pv: str,
    datatype: Type[T],
    sim=False,
    existing_channel: Channel = DISCONNECTED_CHANNEL,
) -> Channel[T]:
    split = pv.split("://", 1)
    if len(split) > 1:
        # We got something like pva://mydevice, so use specified comms mode
        transport, pv = split
        pv_mode = EpicsTransport[transport]
    else:
        # No comms mode specified, use the default
        pv_mode = _default_epics_transport
    if existing_channel is not DISCONNECTED_CHANNEL:
        assert (
            existing_channel.pv == pv
        ), f"Reconnect asked to change from {existing_channel.pv} to {pv}"
    if sim:
        pv_cls = ChannelSim
    else:
        pv_cls = pv_mode.value
    return pv_cls(pv, datatype)
