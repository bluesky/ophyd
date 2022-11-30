from asyncio import CancelledError
from enum import Enum
from functools import partial
from typing import Any, Dict, Sequence, Tuple, Type, Union
from numpy import ndarray

from p4p.client.asyncio import Context
from p4p.client.thread import Subscription
from p4p.wrapper import Value
from p4p.nt.enum import ntenum
from p4p.nt.scalar import NTScalar, ntnumericarray, ntstringarray
from bluesky.protocols import Descriptor, Dtype, Reading
from epicscorelibs.ca import dbr

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
    async def validate(self, value: Value):
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


class EnumConverter(PvaValueConverter):
    def __init__(self, enum_cls: Type[Enum]) -> None:
        self.enum_cls = enum_cls

    async def validate(self, value: Value):
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

    def from_pva(self, value: object):
        return self.enum_cls(value.choice)


def make_pva_descriptor(source: str, value: object) -> Descriptor:
    try:
        dtype = dbr_to_dtype[type(value)]
        shape = []
    except (KeyError, TypeError):
        assert (
            isinstance(value, list) 
            or isinstance(value, ndarray)
        ), f"Can't get dtype for {value} with datatype {type(value)}"
        dtype = "array"
        shape = [len(value)]
    return dict(source=source, dtype=dtype, shape=shape)


def make_pva_reading(
    value: object, converter: PvaValueConverter
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
    converter: PvaValueConverter

    _context = None

    def __init__(self, pv: str, datatype: Type[T]):
        super().__init__(pv, datatype)
        self._converter = NullConverter()
        self.p4p_datatype: type = datatype
        self._channel = None
        self._callback = None
        if issubclass(datatype, Enum):
            self._converter = EnumConverter(datatype)


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
            await self._converter.validate(value)
        except CancelledError:
            raise NotConnected(self.source)

    async def put(self, value: T, wait=True):
        await self.context.put(self.pv, self._converter.to_pva(value))

    async def get_descriptor(self) -> Descriptor:
        value = await self.context.get(self.pv,request='field(value,alarm,timestamp)')
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
