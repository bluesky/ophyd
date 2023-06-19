import sys
from asyncio import CancelledError
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Sequence, Type, Union

from aioca import (
    FORMAT_CTRL,
    FORMAT_RAW,
    FORMAT_TIME,
    Subscription,
    caget,
    camonitor,
    caput,
)
from aioca.types import AugmentedValue, Dbr, Format
from bluesky.protocols import Descriptor, Dtype, Reading
from epicscorelibs.ca import dbr

from .core import (
    NotConnected,
    ReadingValueCallback,
    SignalBackend,
    T,
    get_dtype,
    get_unique,
    wait_for_connection,
)

dbr_to_dtype: Dict[Dbr, Dtype] = {
    dbr.DBR_STRING: "string",
    dbr.DBR_SHORT: "integer",
    dbr.DBR_FLOAT: "number",
    dbr.DBR_CHAR: "string",
    dbr.DBR_LONG: "integer",
    dbr.DBR_DOUBLE: "number",
}


@dataclass
class CaConverter:
    read_dbr: Optional[Dbr]
    write_dbr: Optional[Dbr]

    def write_value(self, value) -> Any:
        return value

    def value(self, value: AugmentedValue):
        return value

    def reading(self, value: AugmentedValue):
        return dict(
            value=self.value(value),
            timestamp=value.timestamp,
            alarm_severity=-1 if value.severity > 2 else value.severity,
        )

    def descriptor(self, source: str, value: AugmentedValue) -> Descriptor:
        return dict(source=source, dtype=dbr_to_dtype[value.datatype], shape=[])


class CaArrayConverter(CaConverter):
    def descriptor(self, source: str, value: AugmentedValue) -> Descriptor:
        return dict(source=source, dtype="array", shape=[len(value)])


@dataclass
class CaEnumConverter(CaConverter):
    enum_class: Type[Enum]

    def write_value(self, value: Union[Enum, str]):
        if isinstance(value, Enum):
            return value.value
        else:
            return value

    def value(self, value: AugmentedValue):
        return self.enum_class(value)

    def descriptor(self, source: str, value: AugmentedValue) -> Descriptor:
        choices = [e.value for e in self.enum_class]
        return dict(source=source, dtype="string", shape=[], choices=choices)  # type: ignore


class DisconnectedCaConverter(CaConverter):
    def __getattribute__(self, __name: str) -> Any:
        raise NotImplementedError("No PV has been set as connect() has not been called")


def make_converter(
    datatype: Optional[Type], values: Dict[str, AugmentedValue]
) -> CaConverter:
    pv = list(values)[0]
    pv_dbr = get_unique({k: v.datatype for k, v in values.items()}, "datatypes")
    is_array = bool([v for v in values.values() if v.element_count > 1])
    if is_array and datatype is str and pv_dbr == dbr.DBR_CHAR:
        # Override waveform of chars to be treated as string
        return CaConverter(dbr.DBR_CHAR_STR, dbr.DBR_CHAR_STR)
    elif is_array and pv_dbr == dbr.DBR_STRING:
        # Waveform of strings, check we wanted this
        if datatype and datatype != Sequence[str]:
            raise TypeError(f"{pv} has type [str] not {datatype.__name__}")
        return CaArrayConverter(pv_dbr, None)
    elif is_array:
        pv_dtype = get_unique({k: v.dtype for k, v in values.items()}, "dtypes")
        # This is an array
        if datatype:
            # Check we wanted an array of this type
            dtype = get_dtype(datatype)
            if not dtype:
                raise TypeError(f"{pv} has type [{pv_dtype}] not {datatype.__name__}")
            if dtype != pv_dtype:
                raise TypeError(f"{pv} has type [{pv_dtype}] not [{dtype}]")
        return CaArrayConverter(pv_dbr, None)
    elif pv_dbr == dbr.DBR_ENUM and datatype is bool:
        # Database can't do bools, so are often representated as enums, CA can do int tho
        pv_choices_len = get_unique(
            {k: len(v.enums) for k, v in values.items()}, "number of choices"
        )
        if pv_choices_len != 2:
            raise TypeError(f"{pv} has {pv_choices_len} choices, can't map to bool")
        return CaConverter(dbr.DBR_SHORT, dbr.DBR_SHORT)
    elif pv_dbr == dbr.DBR_ENUM:
        # This is an Enum
        pv_choices = get_unique(
            {k: tuple(v.enums) for k, v in values.items()}, "choices"
        )
        if datatype:
            if not issubclass(datatype, Enum):
                raise TypeError(f"{pv} has type Enum not {datatype.__name__}")
            choices = tuple(v.value for v in datatype)
            if set(choices) != set(pv_choices):
                raise TypeError(f"{pv} has choices {pv_choices} not {choices}")
            enum_class = datatype
        else:
            enum_class = Enum("GeneratedChoices", {x: x for x in pv_choices}, type=str)  # type: ignore
        return CaEnumConverter(dbr.DBR_STRING, None, enum_class)
    else:
        value = list(values.values())[0]
        # Done the dbr check, so enough to check one of the values
        if datatype and not isinstance(value, datatype):
            raise TypeError(
                f"{pv} has type {type(value).__name__.replace('ca_', '')} not {datatype.__name__}"
            )
        return CaConverter(pv_dbr, None)


_tried_pyepics = False


def _use_pyepics_context_if_imported():
    global _tried_pyepics
    if not _tried_pyepics:
        ca = sys.modules.get("epics.ca", None)
        if ca:
            ca.use_initial_context()
        _tried_pyepics = True


class CaSignalBackend(SignalBackend[T]):
    def __init__(self, datatype: Optional[Type[T]], read_pv: str, write_pv: str):
        self.datatype = datatype
        self.read_pv = read_pv
        self.write_pv = write_pv
        self.initial_values: Dict[str, AugmentedValue] = {}
        self.converter: CaConverter = DisconnectedCaConverter(None, None)
        self.source = f"ca://{self.read_pv}"
        self.subscription: Optional[Subscription] = None

    async def _store_initial_value(self, pv):
        try:
            self.initial_values[pv] = await caget(pv, format=FORMAT_CTRL, timeout=None)
        except CancelledError:
            raise NotConnected(self.source)

    async def connect(self):
        _use_pyepics_context_if_imported()
        if self.read_pv != self.write_pv:
            # Different, need to connect both
            await wait_for_connection(
                read_pv=self._store_initial_value(self.read_pv),
                write_pv=self._store_initial_value(self.write_pv),
            )
        else:
            # The same, so only need to connect one
            await self._store_initial_value(self.read_pv)
        self.converter = make_converter(self.datatype, self.initial_values)

    async def put(self, value: Optional[T], wait=True, timeout=None):
        if value is None:
            write_value = self.initial_values[self.write_pv]
        else:
            write_value = self.converter.write_value(value)
        await caput(
            self.write_pv,
            write_value,
            datatype=self.converter.write_dbr,
            wait=wait,
            timeout=timeout,
        )

    async def _caget(self, format: Format) -> AugmentedValue:
        return await caget(
            self.read_pv,
            datatype=self.converter.read_dbr,
            format=format,
            timeout=None,
        )

    async def get_descriptor(self) -> Descriptor:
        value = await self._caget(FORMAT_CTRL)
        return self.converter.descriptor(self.source, value)

    async def get_reading(self) -> Reading:
        value = await self._caget(FORMAT_TIME)
        return self.converter.reading(value)

    async def get_value(self) -> T:
        value = await self._caget(FORMAT_RAW)
        return self.converter.value(value)

    def set_callback(self, callback: Optional[ReadingValueCallback[T]]) -> None:
        if callback:
            assert (
                not self.subscription
            ), "Cannot set a callback when one is already set"
            self.subscription = camonitor(
                self.read_pv,
                lambda v: callback(self.converter.reading(v), self.converter.value(v)),
                datatype=self.converter.read_dbr,
                format=FORMAT_TIME,
            )
        else:
            if self.subscription:
                self.subscription.close()
            self.subscription = None
