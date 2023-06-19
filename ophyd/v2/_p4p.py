import asyncio
import atexit
from asyncio import CancelledError
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Sequence, Type, Union

from bluesky.protocols import Descriptor, Dtype, Reading
from p4p.client.asyncio import Context, Subscription

from .core import (
    NotConnected,
    ReadingValueCallback,
    SignalBackend,
    T,
    get_dtype,
    get_unique,
    wait_for_connection,
)

# https://mdavidsaver.github.io/p4p/values.html
specifier_to_dtype: Dict[str, Dtype] = {
    "?": "integer",  # bool
    "b": "integer",  # int8
    "B": "integer",  # uint8
    "h": "integer",  # int16
    "H": "integer",  # uint16
    "i": "integer",  # int32
    "I": "integer",  # uint32
    "l": "integer",  # int64
    "L": "integer",  # uint64
    "f": "number",  # float32
    "d": "number",  # float64
    "s": "string",
}


class PvaConverter:
    def write_value(self, value):
        return value

    def value(self, value):
        return value["value"]

    def reading(self, value):
        ts = value["timeStamp"]
        sv = value["alarm"]["severity"]
        return dict(
            value=self.value(value),
            timestamp=ts["secondsPastEpoch"] + ts["nanoseconds"] * 1e-9,
            alarm_severity=-1 if sv > 2 else sv,
        )

    def descriptor(self, source: str, value) -> Descriptor:
        dtype = specifier_to_dtype[value.type().aspy("value")]
        return dict(source=source, dtype=dtype, shape=[])


class PvaArrayConverter(PvaConverter):
    def descriptor(self, source: str, value) -> Descriptor:
        return dict(source=source, dtype="array", shape=[len(value["value"])])


@dataclass
class PvaEnumConverter(PvaConverter):
    enum_class: Type[Enum]

    def write_value(self, value: Union[Enum, str]):
        if isinstance(value, Enum):
            return value.value
        else:
            return value

    def value(self, value):
        return list(self.enum_class)[value["value"]["index"]]

    def descriptor(self, source: str, value) -> Descriptor:
        choices = [e.value for e in self.enum_class]
        return dict(source=source, dtype="string", shape=[], choices=choices)  # type: ignore


class PvaEnumBoolConverter(PvaConverter):
    def value(self, value):
        return value["value"]["index"]

    def descriptor(self, source: str, value) -> Descriptor:
        return dict(source=source, dtype="integer", shape=[])


class PvaTableConverter(PvaConverter):
    def value(self, value):
        return value["value"].todict()

    def descriptor(self, source: str, value) -> Descriptor:
        # This is wrong, but defer until we know how to actually describe a table
        return dict(source=source, dtype="object", shape=[])  # type: ignore


class DisconnectedPvaConverter(PvaConverter):
    def __getattribute__(self, __name: str) -> Any:
        raise NotImplementedError("No PV has been set as connect() has not been called")


def make_converter(datatype: Optional[Type], values: Dict[str, Any]) -> PvaConverter:
    pv = list(values)[0]
    typeid = get_unique({k: v.getID() for k, v in values.items()}, "typeids")
    typ = get_unique({k: type(v["value"]) for k, v in values.items()}, "value types")
    if "NTScalarArray" in typeid and typ == list:
        # Waveform of strings, check we wanted this
        if datatype and datatype != Sequence[str]:
            raise TypeError(f"{pv} has type [str] not {datatype.__name__}")
        return PvaArrayConverter()
    elif "NTScalarArray" in typeid:
        pv_dtype = get_unique(
            {k: v["value"].dtype for k, v in values.items()}, "dtypes"
        )
        # This is an array
        if datatype:
            # Check we wanted an array of this type
            dtype = get_dtype(datatype)
            if not dtype:
                raise TypeError(f"{pv} has type [{pv_dtype}] not {datatype.__name__}")
            if dtype != pv_dtype:
                raise TypeError(f"{pv} has type [{pv_dtype}] not [{dtype}]")
        return PvaArrayConverter()
    elif "NTEnum" in typeid and datatype is bool:
        # Wanted a bool, but database represents as an enum
        pv_choices_len = get_unique(
            {k: len(v["value"]["choices"]) for k, v in values.items()},
            "number of choices",
        )
        if pv_choices_len != 2:
            raise TypeError(f"{pv} has {pv_choices_len} choices, can't map to bool")
        return PvaEnumBoolConverter()
    elif "NTEnum" in typeid:
        # This is an Enum
        pv_choices = get_unique(
            {k: tuple(v["value"]["choices"]) for k, v in values.items()}, "choices"
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
        return PvaEnumConverter(enum_class)
    elif "NTScalar" in typeid:
        if datatype and not issubclass(typ, datatype):
            raise TypeError(f"{pv} has type {typ.__name__} not {datatype.__name__}")
        return PvaConverter()
    elif "NTTable" in typeid:
        return PvaTableConverter()
    else:
        raise TypeError(f"{pv}: Unsupported typeid {typeid}")


class PvaSignalBackend(SignalBackend[T]):
    _ctxt: Optional[Context] = None

    def __init__(self, datatype: Optional[Type[T]], read_pv: str, write_pv: str):
        self.datatype = datatype
        self.read_pv = read_pv
        self.write_pv = write_pv
        self.initial_values: Dict[str, Any] = {}
        self.converter: PvaConverter = DisconnectedPvaConverter()
        self.source = f"pva://{self.read_pv}"
        self.subscription: Optional[Subscription] = None

    @property
    def ctxt(self) -> Context:
        if PvaSignalBackend._ctxt is None:
            PvaSignalBackend._ctxt = Context("pva", nt=False)

            @atexit.register
            def _del_ctxt():
                # If we don't do this we get messages like this on close:
                #   Error in sys.excepthook:
                #   Original exception was:
                PvaSignalBackend._ctxt = None

        return PvaSignalBackend._ctxt

    async def _store_initial_value(self, pv):
        try:
            self.initial_values[pv] = await self.ctxt.get(pv)
        except CancelledError:
            raise NotConnected(self.source)

    async def connect(self):
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
        coro = self.ctxt.put(self.write_pv, dict(value=write_value), wait=wait)
        await asyncio.wait_for(coro, timeout)

    async def get_descriptor(self) -> Descriptor:
        value = await self.ctxt.get(self.read_pv)
        return self.converter.descriptor(self.source, value)

    async def get_reading(self) -> Reading:
        value = await self.ctxt.get(
            self.read_pv, request="field(value,alarm,timestamp)"
        )
        return self.converter.reading(value)

    async def get_value(self) -> T:
        value = await self.ctxt.get(self.read_pv, "field(value)")
        return self.converter.value(value)

    def set_callback(self, callback: Optional[ReadingValueCallback[T]]) -> None:
        if callback:
            assert (
                not self.subscription
            ), "Cannot set a callback when one is already set"

            async def async_callback(v):
                callback(self.converter.reading(v), self.converter.value(v))

            self.subscription = self.ctxt.monitor(
                self.read_pv, async_callback, request="field(value,alarm,timestamp)"
            )
        else:
            if self.subscription:
                self.subscription.close()
            self.subscription = None
