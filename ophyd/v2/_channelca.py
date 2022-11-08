from asyncio import CancelledError
from enum import Enum
from typing import Any, Dict, Tuple, Type, Union

import numpy as np
from aioca import FORMAT_CTRL, FORMAT_TIME, caget, camonitor, caput, connect
from aioca.types import AugmentedValue, Dbr
from bluesky.protocols import Descriptor, Dtype, Reading
from epicscorelibs.ca import dbr

from ._channel import Channel, Monitor, ReadingValueCallback
from .core import NotConnected, T

dbr_to_dtype: Dict[Dbr, Dtype] = {
    dbr.DBR_STRING: "string",
    dbr.DBR_SHORT: "integer",
    dbr.DBR_FLOAT: "number",
    dbr.DBR_ENUM: "integer",
    dbr.DBR_CHAR: "string",
    dbr.DBR_LONG: "integer",
    dbr.DBR_DOUBLE: "number",
    dbr.DBR_ENUM_STR: "string",
    dbr.DBR_CHAR_BYTES: "string",
    dbr.DBR_CHAR_UNICODE: "string",
    dbr.DBR_CHAR_STR: "string",
}


class CaValueConverter:
    async def validate(self, pv: str):
        ...

    def to_ca(self, value):
        ...

    def from_ca(self, value):
        ...


class NullConverter(CaValueConverter):
    def to_ca(self, value):
        return value

    def from_ca(self, value):
        return value


class EnumConverter(CaValueConverter):
    def __init__(self, enum_cls: Type[Enum]) -> None:
        self.enum_cls = enum_cls

    async def validate(self, pv: str):
        value = await caget(pv, format=FORMAT_CTRL)
        if not hasattr(value, "enums"):
            raise TypeError(f"{pv} is not an enum")
        unrecognized = set(v.value for v in self.enum_cls) - set(value.enums)
        if unrecognized:
            raise ValueError(f"Enum strings {unrecognized} not in {value.enums}")

    def to_ca(self, value: Union[Enum, str]):
        if isinstance(value, Enum):
            return value.value
        else:
            return value

    def from_ca(self, value: AugmentedValue):
        return self.enum_cls(value)


def make_ca_descriptor(source: str, value: AugmentedValue) -> Descriptor:
    dtype = dbr_to_dtype[value.datatype]
    shape = []
    if value.element_count > 1:
        dtype = "array"
        shape = [value.element_count]
    return dict(source=source, dtype=dtype, shape=shape)


def make_ca_reading(
    value: AugmentedValue, converter: CaValueConverter
) -> Tuple[Reading, Any]:
    conv_value = converter.from_ca(value)
    return (
        dict(
            value=conv_value,
            timestamp=value.timestamp,
            alarm_severity=-1 if value.severity > 2 else value.severity,
        ),
        conv_value,
    )


class ChannelCa(Channel[T]):
    _converter: CaValueConverter

    def __init__(self, pv: str, datatype: Type[T]):
        super().__init__(pv, datatype)
        self._converter = NullConverter()
        #: The CA datatype that will be requested
        self.ca_datatype: type = datatype
        if issubclass(datatype, Enum):
            self._converter = EnumConverter(datatype)
            self.ca_datatype = str
        # Can't do get_origin() as numpy has its own GenericAlias class on py<3.9
        elif getattr(datatype, "__origin__", None) == np.ndarray:
            # datatype = numpy.ndarray[typing.Any, numpy.dtype[numpy.float64]]
            # so extract numpy.float64 from it
            self.ca_datatype = datatype.__args__[1].__args__[0]  # type: ignore

    @property
    def source(self) -> str:
        return f"ca://{self.pv}"

    async def connect(self):
        try:
            await connect(self.pv, timeout=None)
            await self._converter.validate(self.pv)
        except CancelledError:
            raise NotConnected(self.source)

    async def put(self, value: T, wait=True):
        await caput(self.pv, self._converter.to_ca(value), wait=wait, timeout=None)

    async def get_descriptor(self) -> Descriptor:
        value = await caget(self.pv, datatype=self.ca_datatype, format=FORMAT_CTRL)
        return make_ca_descriptor(self.source, value)

    async def get_reading(self) -> Reading:
        value = await caget(self.pv, datatype=self.ca_datatype, format=FORMAT_TIME)
        return make_ca_reading(value, self._converter)[0]

    async def get_value(self) -> T:
        value = await caget(self.pv, datatype=self.ca_datatype)
        return self._converter.from_ca(value)

    def monitor_reading_value(self, callback: ReadingValueCallback[T]) -> Monitor:
        return camonitor(
            self.pv,
            lambda v: callback(*make_ca_reading(v, self._converter)),
            datatype=self.ca_datatype,
            format=FORMAT_TIME,
        )
