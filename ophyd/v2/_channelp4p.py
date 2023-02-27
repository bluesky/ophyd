from asyncio import CancelledError
from enum import Enum
from typing import Any, Dict, Tuple, Type, Union

import numpy as np

from bluesky.protocols import Descriptor, Dtype, Reading
from p4p.client.asyncio import Context
from p4p.nt.enum import ntenum
from p4p.nt.ndarray import ntndarray
from p4p.nt.scalar import (NTScalar, ntfloat, ntint, ntnumericarray, ntstr,
                           ntstringarray)
from p4p.wrapper import Value

from ._channel import Channel, Monitor, ReadingValueCallback
from .core import NotConnected, T

dbr_to_dtype: Dict[NTScalar, Dtype] = {
    NTScalar.typeMap[bool]: "integer",
    NTScalar.typeMap[int]: "integer",
    NTScalar.typeMap[float]: "number",
    NTScalar.typeMap[str]: "string",
    ntenum: "integer"
}


class PvaValueConverter:
    async def validate(self, pv: str, value: Value):
        ...

    def to_pva(self, value):
        ...

    def from_pva(self, value):
        ...


class NullConverter(PvaValueConverter):
    def to_pva(self, value):
        return value

    def from_pva(self, value):
        return value


class TypeCheckConverter(NullConverter):
    def __init__(self, datatype):
        self._type = datatype

    async def validate(self, pv: str, value: Value):
        if isinstance(value, np.ndarray):
            if not np.issubdtype(value.dtype, self._type):
                raise TypeError(f"{pv} is not type {self._type}")

        elif not isinstance(value, self._type):
            raise TypeError(f"{pv} is not type {self._type}")


class EnumConverter(PvaValueConverter):
    def __init__(self, enum_cls: Type[Enum]) -> None:
        self.enum_cls = enum_cls

    async def validate(self, pv: str, value: Value):
        if not isinstance(value, ntenum):
            raise TypeError(f"{pv} is not an enum")
        unrecognized = set(v.value for v in self.enum_cls) - set(value.raw.value.choices)
        if unrecognized:
            raise ValueError(f"Enum strings {unrecognized} not in {value.raw.value.choices}")

    def to_pva(self, value: Union[Enum, str]):
        if isinstance(value, Enum):
            return value.value
        else:
            return value

    def from_pva(self, value: ntenum):
        return self.enum_cls(value.choice)


def make_pva_descriptor(source: str, value: object) -> Descriptor:
    try:
        dtype = dbr_to_dtype[type(value)]
        shape = []
    except (KeyError, TypeError):
        assert (
            isinstance(value, list)
            or isinstance(value, np.ndarray)
        ), f"Can't get dtype for {value} with datatype {type(value)}"
        dtype = "array"
        shape = [len(value)]
    return dict(source=source, dtype=dtype, shape=shape)


def make_pva_reading(
    value: Union[ntfloat, ntint, ntstr, ntnumericarray, ntstringarray, ntndarray], converter: PvaValueConverter
) -> Tuple[Reading, Any]:
    conv_value = converter.from_pva(value)
    return (
        dict(
            value=conv_value,
            timestamp=value.timestamp,
            alarm_severity=-1 if value.severity > 2 else value.severity,
        ),
        conv_value,
    )


class ChannelP4p(Channel[T]):
    _converter: PvaValueConverter
    _callback: ReadingValueCallback[T]

    _context = None

    def __init__(self, pv: str, datatype: Type[T]):
        super().__init__(pv, datatype)
        self._p4p_datatype: type = datatype
        # Can't do get_origin() as numpy has its own GenericAlias class on py<3.9
        if getattr(datatype, "__origin__", None) == np.ndarray:
            # datatype = numpy.ndarray[typing.Any, numpy.dtype[numpy.float64]]
            # so extract numpy.float64 from it
            self._p4p_datatype = datatype.__args__[1].__args__[0]  # type: ignore
        self._converter = TypeCheckConverter(self._p4p_datatype)
        if issubclass(datatype, Enum):
            self._converter = EnumConverter(datatype)
        self._channel = None

    @staticmethod
    def get_context():
        if ChannelP4p._context is None:
            ChannelP4p._context = Context('pva', nt=None)
        return ChannelP4p._context

    @property
    def context(self):
        return ChannelP4p.get_context()

    @property
    def source(self) -> str:
        return f"pva://{self.pv}"

    async def connect(self):
        try:
            value = await self.context.get(self.pv)
            await self._converter.validate(self.pv, value)
        except CancelledError:
            raise NotConnected(self.source)

    async def put(self, value: T, wait=True):
        await self.context.put(self.pv, self._converter.to_pva(value))

    async def get_descriptor(self) -> Descriptor:
        value = await self.context.get(self.pv, request='field(value,alarm,timestamp)')
        return make_pva_descriptor(self.source, value)

    async def get_reading(self) -> Reading:
        value = await self.context.get(self.pv)
        return make_pva_reading(value, self._converter)[0]

    async def get_value(self) -> T:
        value = await self.context.get(self.pv)
        return self._converter.from_pva(value)

    def monitor_reading_value(self, callback: ReadingValueCallback[T]) -> Monitor:
        self._callback = callback
        return self.context.monitor(
            self.pv,
            self.async_callback,
            request='field(value,alarm,timestamp)'
        )

    async def async_callback(self, value):
        self._callback(*make_pva_reading(value, self._converter))
