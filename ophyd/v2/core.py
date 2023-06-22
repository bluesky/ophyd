"""Core Ophyd.v2 functionality like Device and Signal"""
from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import re
import sys
import time
from abc import abstractmethod
from collections import abc
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Coroutine,
    Dict,
    Generator,
    Generic,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    get_origin,
)

import numpy as np
from bluesky.protocols import (
    Configurable,
    Descriptor,
    Dtype,
    HasName,
    Movable,
    Readable,
    Reading,
    Stageable,
    Status,
    Subscribable,
)
from bluesky.run_engine import call_in_bluesky_event_loop

T = TypeVar("T")
Callback = Callable[[T], None]


class AsyncStatus(Status):
    "Convert asyncio awaitable to bluesky Status interface"

    def __init__(
        self,
        awaitable: Awaitable,
        watchers: Optional[List[Callable]] = None,
    ):
        if isinstance(awaitable, asyncio.Task):
            self.task = awaitable
        else:
            self.task = asyncio.create_task(awaitable)  # type: ignore
        self.task.add_done_callback(self._run_callbacks)
        self._callbacks = cast(List[Callback[Status]], [])
        self._watchers = watchers

    def __await__(self):
        return self.task.__await__()

    def add_callback(self, callback: Callback[Status]):
        if self.done:
            callback(self)
        else:
            self._callbacks.append(callback)

    def _run_callbacks(self, task: asyncio.Task):
        if not task.cancelled():
            for callback in self._callbacks:
                callback(self)

    # TODO: remove ignore and bump min version when bluesky v1.12.0 is released
    def exception(self, timeout: Optional[float] = 0.0) -> Optional[BaseException]:  # type: ignore
        if timeout != 0.0:
            raise Exception(
                "cannot honour any timeout other than 0 in an asynchronous function"
            )

        if self.task.done():
            try:
                return self.task.exception()
            except asyncio.CancelledError as e:
                return e
        return None

    @property
    def done(self) -> bool:
        return self.task.done()

    @property
    def success(self) -> bool:
        return (
            self.task.done() and not self.task.cancelled() and not self.task.exception()
        )

    def watch(self, watcher: Callable):
        """Add watcher to the list of interested parties.

        Arguments as per Bluesky :external+bluesky:meth:`watch` protocol.
        """
        if self._watchers is not None:
            self._watchers.append(watcher)

    @classmethod
    def wrap(cls, f: Callable[[T], Coroutine]) -> Callable[[T], AsyncStatus]:
        @functools.wraps(f)
        def wrap_f(self) -> AsyncStatus:
            return AsyncStatus(f(self))

        return wrap_f

    def __repr__(self) -> str:
        if self.done:
            if self.exception() is not None:
                status = "errored"
            else:
                status = "done"
        else:
            status = "pending"
        return f"<{type(self).__name__} {status}>"

    __str__ = __repr__


class Device(HasName):
    """Common base class for all Ophyd.v2 Devices.

    By default, names and connects all Device children.
    """

    _name: str = ""
    #: The parent Device if it exists
    parent: Optional[Device] = None

    def __init__(self, name: str = "") -> None:
        self.set_name(name)

    @property
    def name(self) -> str:
        """Return the name of the Device"""
        return self._name

    def set_name(self, name: str):
        """Set ``self.name=name`` and each ``self.child.name=name+"-child"``.

        Parameters
        ----------
        name:
            New name to set
        """
        self._name = name
        name_children(self, name)

    async def connect(self, sim: bool = False):
        """Connect self and all child Devices.

        Parameters
        ----------
        sim:
            If True then connect in simulation mode.
        """
        await connect_children(self, sim)


class NotConnected(Exception):
    """Exception to be raised if a `Device.connect` is cancelled"""

    def __init__(self, *lines: str):
        self.lines = list(lines)

    def __str__(self) -> str:
        return "\n".join(self.lines)


async def wait_for_connection(**coros: Awaitable[None]):
    """Call many underlying signals, accumulating `NotConnected` exceptions

    Raises
    ------
    `NotConnected` if cancelled
    """
    ts = {k: asyncio.create_task(c) for (k, c) in coros.items()}  # type: ignore
    try:
        done, pending = await asyncio.wait(ts.values())
    except asyncio.CancelledError:
        for t in ts.values():
            t.cancel()
        lines: List[str] = []
        for k, t in ts.items():
            try:
                await t
            except NotConnected as e:
                if len(e.lines) == 1:
                    lines.append(f"{k}: {e.lines[0]}")
                else:
                    lines.append(f"{k}:")
                    lines += [f"  {line}" for line in e.lines]
        raise NotConnected(*lines)
    else:
        # Wait for everything to foreground the exceptions
        for f in list(done) + list(pending):
            await f


async def connect_children(device: Device, sim: bool):
    """Call ``child.connect(sim)`` on all child devices in parallel.

    Typically used to implement `Device.connect` like this::

        async def connect(self, sim=False):
            await connect_children(self, sim)
    """

    coros = {
        name: child_device.connect(sim)
        for name, child_device in get_device_children(device)
    }
    if coros:
        await wait_for_connection(**coros)


def name_children(device: Device, name: str):
    """Call ``child.set_name(child_name)`` on all child devices in series."""
    for attr_name, child in get_device_children(device):
        child_name = f"{name}-{attr_name.rstrip('_')}" if name else ""
        child.set_name(child_name)
        child.parent = device


def get_device_children(device: Device) -> Generator[Tuple[str, Device], None, None]:
    for attr_name, attr in device.__dict__.items():
        if attr_name != "parent" and isinstance(attr, Device):
            yield attr_name, attr


class DeviceCollector:
    """Collector of top level Device instances to be used as a context manager

    Parameters
    ----------
    set_name:
        If True, call ``device.set_name(variable_name)`` on all collected
        Devices
    connect:
        If True, call ``device.connect(sim)`` in parallel on all
        collected Devices
    sim:
        If True, connect Signals in simulation mode
    timeout:
        How long to wait for connect before logging an exception

    Notes
    -----
    Example usage::

        [async] with DeviceCollector():
            t1x = motor.Motor("BLxxI-MO-TABLE-01:X")
            t1y = motor.Motor("pva://BLxxI-MO-TABLE-01:Y")
            # Names and connects devices here
        assert t1x.comm.velocity.source
        assert t1x.name == "t1x"

    """

    def __init__(
        self,
        set_name=True,
        connect=True,
        sim=False,
        timeout: float = 10.0,
    ):
        self._set_name = set_name
        self._connect = connect
        self._sim = sim
        self._timeout = timeout
        self._names_on_enter: Set[str] = set()
        self._objects_on_exit: Dict[str, Any] = {}

    def _caller_locals(self):
        """Walk up until we find a stack frame that doesn't have us as self"""
        try:
            raise ValueError
        except ValueError:
            _, _, tb = sys.exc_info()
            assert tb, "Can't get traceback, this shouldn't happen"
            caller_frame = tb.tb_frame
            while caller_frame.f_locals.get("self", None) is self:
                caller_frame = caller_frame.f_back
            return caller_frame.f_locals

    def __enter__(self) -> DeviceCollector:
        # Stash the names that were defined before we were called
        self._names_on_enter = set(self._caller_locals())
        return self

    async def __aenter__(self) -> DeviceCollector:
        return self.__enter__()

    async def _on_exit(self) -> None:
        # Name and kick off connect for devices
        tasks: Dict[asyncio.Task, str] = {}
        for name, obj in self._objects_on_exit.items():
            if name not in self._names_on_enter and isinstance(obj, Device):
                if self._set_name and not obj.name:
                    obj.set_name(name)
                if self._connect:
                    task = asyncio.create_task(obj.connect(self._sim))
                    tasks[task] = name
        # Wait for all the signals to have finished
        if tasks:
            await self._wait_for_tasks(tasks)

    async def _wait_for_tasks(self, tasks: Dict[asyncio.Task, str]):
        done, pending = await asyncio.wait(tasks, timeout=self._timeout)
        if pending:
            msg = f"{len(pending)} Devices did not connect:"
            for t in pending:
                t.cancel()
                with suppress(Exception):
                    await t
                e = t.exception()
                msg += f"\n  {tasks[t]}: {type(e).__name__}"
                lines = str(e).splitlines()
                if len(lines) <= 1:
                    msg += f": {e}"
                else:
                    msg += "".join(f"\n    {line}" for line in lines)
            logging.error(msg)
        raised = [t for t in done if t.exception()]
        if raised:
            logging.error(f"{len(raised)} Devices raised an error:")
            for t in raised:
                logging.exception(f"  {tasks[t]}:", exc_info=t.exception())
        if pending or raised:
            raise NotConnected("Not all Devices connected")

    async def __aexit__(self, type, value, traceback):
        self._objects_on_exit = self._caller_locals()
        await self._on_exit()

    def __exit__(self, type_, value, traceback):
        self._objects_on_exit = self._caller_locals()
        return call_in_bluesky_event_loop(self._on_exit())


#: A function that will be called with the Reading and value when the
#: monitor updates
ReadingValueCallback = Callable[[Reading, T], None]


class SignalBackend(Generic[T]):
    """A read/write/monitor backend for a Signals"""

    #: Datatype of the signal value
    datatype: Optional[Type[T]] = None

    #: Like ca://PV_PREFIX:SIGNAL
    source: str = ""

    @abstractmethod
    async def connect(self):
        """Connect to underlying hardware"""

    @abstractmethod
    async def put(self, value: Optional[T], wait=True, timeout=None):
        """Put a value to the PV, if wait then wait for completion for up to timeout"""

    @abstractmethod
    async def get_descriptor(self) -> Descriptor:
        """Metadata like source, dtype, shape, precision, units"""

    @abstractmethod
    async def get_reading(self) -> Reading:
        """The current value, timestamp and severity"""

    @abstractmethod
    async def get_value(self) -> T:
        """The current value"""

    @abstractmethod
    def set_callback(self, callback: Optional[ReadingValueCallback[T]]) -> None:
        """Observe changes to the current value, timestamp and severity"""


_sim_backends: Dict[Signal, SimSignalBackend] = {}


primitive_dtypes: Dict[type, Dtype] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


class SimConverter(Generic[T]):
    def value(self, value: T) -> T:
        return value

    def write_value(self, value: T) -> T:
        return value

    def reading(self, value: T, timestamp: float, severity: int) -> Reading:
        return Reading(
            value=value,
            timestamp=timestamp,
            alarm_severity=-1 if severity > 2 else severity,
        )

    def descriptor(self, source: str, value) -> Descriptor:
        assert (
            type(value) in primitive_dtypes
        ), f"invalid converter for value of type {type(value)}"
        dtype = primitive_dtypes[type(value)]
        return dict(source=source, dtype=dtype, shape=[])

    def make_initial_value(self, datatype: Optional[Type[T]]) -> T:
        if datatype is None:
            return cast(T, None)

        return datatype()


class SimArrayConverter(SimConverter):
    def descriptor(self, source: str, value) -> Descriptor:
        return dict(source=source, dtype="array", shape=[len(value)])

    def make_initial_value(self, datatype: Optional[Type[T]]) -> T:
        if datatype is None:
            return cast(T, None)

        if get_origin(datatype) == abc.Sequence:
            return cast(T, [])

        return cast(T, datatype(shape=0))  # type: ignore


@dataclass
class SimEnumConverter(SimConverter):
    enum_class: Type[Enum]

    def write_value(self, value: Union[Enum, str]) -> Enum:
        if isinstance(value, Enum):
            return value
        else:
            return self.enum_class(value)

    def descriptor(self, source: str, value) -> Descriptor:
        choices = [e.value for e in self.enum_class]
        return dict(source=source, dtype="string", shape=[], choices=choices)  # type: ignore

    def make_initial_value(self, datatype: Optional[Type[T]]) -> T:
        if datatype is None:
            return cast(T, None)

        return cast(T, list(datatype.__members__.values())[0])  # type: ignore


class DisconnectedSimConverter(SimConverter):
    def __getattribute__(self, __name: str) -> Any:
        raise NotImplementedError("No PV has been set as connect() has not been called")


def make_converter(datatype):
    is_array = get_dtype(datatype) is not None
    is_sequence = get_origin(datatype) == abc.Sequence
    is_enum = issubclass(datatype, Enum) if inspect.isclass(datatype) else False

    if is_array or is_sequence:
        return SimArrayConverter()
    if is_enum:
        return SimEnumConverter(datatype)

    return SimConverter()


class SimSignalBackend(SignalBackend[T]):
    """An simulated backend to a Signal, created with ``Signal.connect(sim=True)``"""

    _value: T
    _initial_value: T
    _timestamp: float
    _severity: int

    def __init__(self, datatype: Optional[Type[T]], source: str) -> None:
        pv = re.split(r"://", source)[-1]
        self.source = f"sim://{pv}"
        self.datatype = datatype
        self.pv = source
        self.converter: SimConverter = DisconnectedSimConverter()
        self.put_proceeds = asyncio.Event()
        self.put_proceeds.set()
        self.callback: Optional[ReadingValueCallback[T]] = None

    async def connect(self) -> None:
        self.converter = make_converter(self.datatype)
        self._initial_value = self.converter.make_initial_value(self.datatype)
        self._severity = 0

        await self.put(None)

    async def put(self, value: Optional[T], wait=True, timeout=None):
        write_value = (
            self.converter.write_value(value)
            if value is not None
            else self._initial_value
        )
        self._set_value(write_value)

        if wait:
            await asyncio.wait_for(self.put_proceeds.wait(), timeout)

    def _set_value(self, value: T):
        """Method to bypass asynchronous logic, designed to only be used in tests."""
        self._value = value
        self._timestamp = time.monotonic()
        reading: Reading = self.converter.reading(
            self._value, self._timestamp, self._severity
        )

        if self.callback:
            self.callback(reading, self._value)

    async def get_descriptor(self) -> Descriptor:
        return self.converter.descriptor(self.source, self._value)

    async def get_reading(self) -> Reading:
        return self.converter.reading(self._value, self._timestamp, self._severity)

    async def get_value(self) -> T:
        return self.converter.value(self._value)

    def set_callback(self, callback: Optional[ReadingValueCallback[T]]) -> None:
        if callback:
            assert not self.callback, "Cannot set a callback when one is already set"
            reading: Reading = self.converter.reading(
                self._value, self._timestamp, self._severity
            )
            callback(reading, self._value)
        self.callback = callback


def set_sim_value(signal: Signal[T], value: T):
    """Set the value of a signal that is in sim mode."""
    _sim_backends[signal]._set_value(value)


def set_sim_put_proceeds(signal: Signal[T], proceeds: bool):
    """Allow or block a put with wait=True from proceeding"""
    event = _sim_backends[signal].put_proceeds
    if proceeds:
        event.set()
    else:
        event.clear()


def set_sim_callback(signal: Signal[T], callback: ReadingValueCallback[T]) -> None:
    """Monitor the value of a signal that is in sim mode"""
    return _sim_backends[signal].set_callback(callback)


def _fail(self, other, *args, **kwargs):
    if isinstance(other, Signal):
        raise TypeError(
            "Can't compare two Signals, did you mean await signal.get_value() instead?"
        )
    else:
        return NotImplemented


# Types
# - bool
# - int
# - float
# - str
# - Enum[str]
# - npt.NDArray[np.bool_ | np.uint[8,16,32,64] | np.int[8,16,32,64] | np.float[32,64]
# - Sequence[str | Enum]
# - Table (TypedDict of Sequence or NDArray above), exploded in reading

DEFAULT_TIMEOUT = 10.0


class Signal(Device, Generic[T]):
    """A Device with the concept of a value, with R, RW, W and X flavours"""

    def __init__(
        self, backend: SignalBackend[T], timeout: Optional[float] = DEFAULT_TIMEOUT
    ) -> None:
        self._name = ""
        self._timeout = timeout
        self._init_backend = self._backend = backend

    @property
    def name(self) -> str:
        return self._name

    def set_name(self, name: str = ""):
        self._name = name

    async def connect(self, sim=False):
        if sim:
            self._backend = SimSignalBackend(
                datatype=self._init_backend.datatype, source=self._init_backend.source
            )
            _sim_backends[self] = self._backend
        else:
            self._backend = self._init_backend
            _sim_backends.pop(self, None)
        await self._backend.connect()

    @property
    def source(self) -> str:
        """Like ca://PV_PREFIX:SIGNAL, or "" if not set"""
        return self._backend.source

    __lt__ = __le__ = __eq__ = __ge__ = __gt__ = __ne__ = _fail

    def __hash__(self):
        # Restore the default implementation so we can use in a set or dict
        return hash(id(self))


class _SignalCache(Generic[T]):
    def __init__(self, backend: SignalBackend[T], signal: Signal):
        self._signal = signal
        self._staged = False
        self._listeners: Dict[Callback, bool] = {}
        self._valid = asyncio.Event()
        self._reading: Optional[Reading] = None
        self._value: Optional[T] = None

        self.backend = backend
        backend.set_callback(self._callback)

    def close(self):
        self.backend.set_callback(None)

    async def get_reading(self) -> Reading:
        await self._valid.wait()
        assert self._reading is not None, "Monitor not working"
        return self._reading

    async def get_value(self) -> T:
        await self._valid.wait()
        assert self._value is not None, "Monitor not working"
        return self._value

    def _callback(self, reading: Reading, value: T):
        self._reading = reading
        self._value = value
        self._valid.set()
        for function, want_value in self._listeners.items():
            self._notify(function, want_value)

    def _notify(self, function: Callback, want_value: bool):
        if want_value:
            function(self._value)
        else:
            function({self._signal.name: self._reading})

    def subscribe(self, function: Callback, want_value: bool) -> None:
        self._listeners[function] = want_value
        if self._valid.is_set():
            self._notify(function, want_value)

    def unsubscribe(self, function: Callback) -> bool:
        self._listeners.pop(function)
        return self._staged or bool(self._listeners)

    def set_staged(self, staged: bool):
        self._staged = staged
        return self._staged or bool(self._listeners)


def _add_timeout(func):
    @functools.wraps(func)
    async def wrapper(self: Signal, *args, **kwargs):
        return await asyncio.wait_for(func(self, *args, **kwargs), self._timeout)

    return wrapper


class SignalR(Signal[T], Readable, Stageable, Subscribable):
    """Signal that can be read from and monitored"""

    _cache: Optional[_SignalCache] = None

    def _backend_or_cache(
        self, cached: Optional[bool]
    ) -> Union[_SignalCache, SignalBackend]:
        # If cached is None then calculate it based on whether we already have a cache
        if cached is None:
            cached = self._cache is not None
        if cached:
            assert self._cache, f"{self.source} not being monitored"
            return self._cache
        else:
            return self._backend

    def _get_cache(self) -> _SignalCache:
        if not self._cache:
            self._cache = _SignalCache(self._backend, self)
        return self._cache

    def _del_cache(self, needed: bool):
        if self._cache and not needed:
            self._cache.close()
            self._cache = None

    @_add_timeout
    async def read(self, cached: Optional[bool] = None) -> Dict[str, Reading]:
        """Return a single item dict with the reading in it"""
        return {self.name: await self._backend_or_cache(cached).get_reading()}

    @_add_timeout
    async def describe(self) -> Dict[str, Descriptor]:
        """Return a single item dict with the descriptor in it"""
        return {self.name: await self._backend.get_descriptor()}

    @_add_timeout
    async def get_value(self, cached: Optional[bool] = None) -> T:
        """The current value"""
        return await self._backend_or_cache(cached).get_value()

    def subscribe_value(self, function: Callback[T]):
        """Subscribe to updates in value of a device"""
        self._get_cache().subscribe(function, want_value=True)

    def subscribe(self, function: Callback[Dict[str, Reading]]) -> None:
        """Subscribe to updates in the reading"""
        self._get_cache().subscribe(function, want_value=False)

    def clear_sub(self, function: Callback) -> None:
        """Remove a subscription."""
        self._del_cache(self._get_cache().unsubscribe(function))

    @AsyncStatus.wrap
    async def stage(self) -> None:
        """Start caching this signal"""
        self._get_cache().set_staged(True)

    @AsyncStatus.wrap
    async def unstage(self) -> None:
        """Stop caching this signal"""
        self._del_cache(self._get_cache().set_staged(False))


class SignalW(Signal[T], Movable):
    """Signal that can be set"""

    def set(self, value: T, wait=True, timeout=None) -> AsyncStatus:
        """Set the value and return a status saying when it's done"""
        coro = self._backend.put(value, wait=wait, timeout=timeout or self._timeout)
        return AsyncStatus(coro)


class SignalRW(SignalR[T], SignalW[T]):
    """Signal that can be both read and set"""


class SignalX(Signal):
    """Signal that puts the default value"""

    async def execute(self, wait=True, timeout=None):
        """Execute the action and return a status saying when it's done"""
        await self._backend.put(None, wait=wait, timeout=timeout or self._timeout)


async def observe_value(signal: SignalR[T]) -> AsyncGenerator[T, None]:
    """Subscribe to the value of a signal so it can be iterated from.

    Parameters
    ----------
    signal:
        Call subscribe_value on this at the start, and clear_sub on it at the
        end

    Notes
    -----
    Example usage::

        async for value in observe_value(sig):
            do_something_with(value)
    """
    q: asyncio.Queue[T] = asyncio.Queue()
    signal.subscribe_value(q.put_nowait)
    try:
        while True:
            yield await q.get()
    finally:
        signal.clear_sub(q.put_nowait)


class _ValueChecker(Generic[T]):
    def __init__(self, matcher: Callable[[T], bool], matcher_name: str):
        self._last_value: Optional[T]
        self._matcher = matcher
        self._matcher_name = matcher_name

    async def _wait_for_value(self, signal: SignalR[T]):
        async for value in observe_value(signal):
            self._last_value = value
            if self._matcher(value):
                return

    async def wait_for_value(self, signal: SignalR[T], timeout: float):
        try:
            await asyncio.wait_for(self._wait_for_value(signal), timeout)
        except asyncio.TimeoutError as e:
            raise TimeoutError(
                f"{signal.name} didn't match {self._matcher_name} in {timeout}s, "
                f"last value {self._last_value!r}"
            ) from e


async def wait_for_value(
    signal: SignalR[T], match: Union[T, Callable[[T], bool]], timeout: float
):
    """Wait for a signal to have a matching value.

    Parameters
    ----------
    signal:
        Call subscribe_value on this at the start, and clear_sub on it at the
        end
    match:
        If a callable, it should return True if the value matches. If not
        callable then value will be checked for equality with match.
    timeout:
        How long to wait for the value to match

    Notes
    -----
    Example usage::

        wait_for_value(device.acquiring, 1, timeout=1)

    Or::

        wait_for_value(device.num_captured, lambda v: v > 45, timeout=1)
    """
    if callable(match):
        checker = _ValueChecker(match, match.__name__)
    else:
        checker = _ValueChecker(lambda v: v == match, repr(match))
    await checker.wait_for_value(signal, timeout)


async def set_and_wait_for_value(
    signal: SignalRW[T],
    value: T,
    timeout: float = DEFAULT_TIMEOUT,
    status_timeout: Optional[float] = None,
) -> AsyncStatus:
    """Set a signal and monitor it until it has that value.

    Useful for busy record, or other Signals with pattern:

    - Set Signal with wait=True and stash the Status
    - Read the same Signal to check the operation has started
    - Return the Status so calling code can wait for operation to complete

    Parameters
    ----------
    signal:
        The signal to set and monitor
    value:
        The value to set it to
    timeout:
        How long to wait for the signal to have the value
    status_timeout:
        How long the returned Status will wait for the set to complete

    Notes
    -----
    Example usage::

        set_and_wait_for_value(device.acquire, 1)
    """
    status = signal.set(value, timeout=status_timeout)
    await wait_for_value(signal, value, timeout=timeout)
    return status


async def merge_gathered_dicts(
    coros: Iterable[Awaitable[Dict[str, T]]]
) -> Dict[str, T]:
    """Merge dictionaries produced by a sequence of coroutines.

    Can be used for merging ``read()`` or ``describe``. For instance::

        combined_read = await merge_gathered_dicts(s.read() for s in signals)
    """
    ret: Dict[str, T] = {}
    for result in await asyncio.gather(*coros):
        ret.update(result)
    return ret


class StandardReadable(Device, Readable, Configurable, Stageable):
    """Device that owns its children and provides useful default behavior.

    - When its name is set it renames child Devices
    - Signals can be registered for read() and read_configuration()
    - These signals will be subscribed for read() between stage() and unstage()
    """

    _read_signals: Tuple[SignalR, ...] = ()
    _configuration_signals: Tuple[SignalR, ...] = ()
    _read_uncached_signals: Tuple[SignalR, ...] = ()

    def set_readable_signals(
        self,
        read: Sequence[SignalR] = (),
        config: Sequence[SignalR] = (),
        read_uncached: Sequence[SignalR] = (),
    ):
        """
        Parameters
        ----------
        read:
            Signals to make up `read()`
        conf:
            Signals to make up `read_configuration()`
        read_uncached:
            Signals to make up `read()` that won't be cached
        """
        self._read_signals = tuple(read)
        self._configuration_signals = tuple(config)
        self._read_uncached_signals = tuple(read_uncached)

    @AsyncStatus.wrap
    async def stage(self) -> None:
        for sig in self._read_signals + self._configuration_signals:
            await sig.stage().task

    @AsyncStatus.wrap
    async def unstage(self) -> None:
        for sig in self._read_signals + self._configuration_signals:
            await sig.unstage().task

    async def describe_configuration(self) -> Dict[str, Descriptor]:
        return await merge_gathered_dicts(
            [sig.describe() for sig in self._configuration_signals]
        )

    async def read_configuration(self) -> Dict[str, Reading]:
        return await merge_gathered_dicts(
            [sig.read() for sig in self._configuration_signals]
        )

    async def describe(self) -> Dict[str, Descriptor]:
        return await merge_gathered_dicts(
            [sig.describe() for sig in self._read_signals + self._read_uncached_signals]
        )

    async def read(self) -> Dict[str, Reading]:
        return await merge_gathered_dicts(
            [sig.read() for sig in self._read_signals]
            + [sig.read(cached=False) for sig in self._read_uncached_signals]
        )


VT = TypeVar("VT", bound=Device)


class DeviceVector(Dict[int, VT], Device):
    def set_name(self, parent_name: str):
        self._name = parent_name
        for name, device in self.items():
            device.set_name(f"{parent_name}-{name}")
            device.parent = self

    async def connect(self, sim: bool = False):
        coros = {str(k): d.connect(sim) for k, d in self.items()}
        await wait_for_connection(**coros)


def get_unique(values: Dict[str, T], types: str) -> T:
    """If all values are the same, return that value, otherwise return TypeError

    >>> get_unique({"a": 1, "b": 1}, "integers")
    1
    >>> get_unique({"a": 1, "b": 2}, "integers")
    Traceback (most recent call last):
     ...
    TypeError: Differing integers: a has 1, b has 2
    """
    set_values = set(values.values())
    if len(set_values) != 1:
        diffs = ", ".join(f"{k} has {v}" for k, v in values.items())
        raise TypeError(f"Differing {types}: {diffs}")
    return set_values.pop()


def get_dtype(typ: Type) -> Optional[np.dtype]:
    """Get the runtime dtype from a numpy ndarray type annotation

    >>> import numpy.typing as npt
    >>> import numpy as np
    >>> get_dtype(npt.NDArray[np.int8])
    dtype('int8')
    """
    if getattr(typ, "__origin__", None) == np.ndarray:
        # datatype = numpy.ndarray[typing.Any, numpy.dtype[numpy.float64]]
        # so extract numpy.float64 from it
        return np.dtype(typ.__args__[1].__args__[0])  # type: ignore
    return None
