import asyncio
import random
import re
import string
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional, Sequence, Tuple, Type, TypedDict

import numpy as np
import numpy.typing as npt
import pytest
from aioca import purge_channel_caches
from bluesky.protocols import Reading

from ophyd.v2.core import NotConnected, SignalBackend, get_dtype
from ophyd.v2.epics import EpicsTransport, _make_backend

RECORDS = str(Path(__file__).parent / "test_records.db")
PV_PREFIX = "".join(random.choice(string.ascii_lowercase) for _ in range(12))


@dataclass
class IOC:
    process: subprocess.Popen
    protocol: Literal["ca", "pva"]

    async def make_backend(
        self, typ: Optional[Type], suff: str, connect=True
    ) -> SignalBackend:
        # Calculate the pv
        pv = f"{PV_PREFIX}:{self.protocol}:{suff}"
        # Make and connect the backend
        cls = EpicsTransport[self.protocol].value
        backend = cls(typ, pv, pv)
        if connect:
            await asyncio.wait_for(backend.connect(), 10)
        return backend


# Use a module level fixture per protocol so it's fast to run tests. This means
# we need to add a record for every PV that we will modify in tests to stop
# tests interfering with each other
@pytest.fixture(scope="module", params=["pva", "ca"])
def ioc(request):
    protocol = request.param
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "epicscorelibs.ioc",
            "-m",
            f"P={PV_PREFIX}:{protocol}:",
            "-d",
            RECORDS,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    yield IOC(process, protocol)
    # close backend caches before the event loop
    purge_channel_caches()
    try:
        print(process.communicate("exit")[0])
    except ValueError:
        # Someone else already called communicate
        pass


class MonitorQueue:
    def __init__(self, backend: SignalBackend):
        self.backend = backend
        self.subscription = backend.monitor_reading_value(self.add_reading_value)
        self.updates: asyncio.Queue[Tuple[Reading, Any]] = asyncio.Queue()

    def add_reading_value(self, reading: Reading, value):
        self.updates.put_nowait((reading, value))

    async def check_updates(self, expected_value):
        expected_reading = {
            "value": expected_value,
            "timestamp": pytest.approx(time.time(), rel=0.1),
            "alarm_severity": 0,
        }
        reading, value = await self.updates.get()
        assert value == expected_value == await self.backend.get_value()
        assert reading == expected_reading == await self.backend.get_reading()

    def close(self):
        self.subscription.close()


class MyEnum(str, Enum):
    a = "Aaa"
    b = "Bbb"
    c = "Ccc"


integer_d = dict(dtype="integer", shape=[])
number_d = dict(dtype="number", shape=[])
string_d = dict(dtype="string", shape=[])
enum_d = dict(dtype="string", shape=[], choices=["Aaa", "Bbb", "Ccc"])
waveform_d = dict(dtype="array", shape=[2])
ls1 = "a string that is just longer than forty characters"
ls2 = "another string that is just longer than forty characters"

ca_dtype_mapping = {
    np.int8: np.uint8,
    np.uint16: np.int32,
    np.uint32: np.float64,
    np.int64: np.float64,
    np.uint64: np.float64,
}


@pytest.mark.parametrize(
    "typ, suff, initial, put, descriptor",
    [
        (bool, "bool", 1, 0, number_d),
        (int, "int", 42, 43, number_d),
        (float, "float", 3.141, 43.5, number_d),
        (str, "str", "hello", "goodbye", string_d),
        (MyEnum, "enum", MyEnum.b, MyEnum.c, enum_d),
        (npt.NDArray[np.int8], "int8a", [-128, 127], [-8], waveform_d),
        (npt.NDArray[np.uint8], "uint8a", [0, 255], [218], waveform_d),
        (npt.NDArray[np.int16], "int16a", [-32768, 32767], [-855], waveform_d),
        (npt.NDArray[np.uint16], "uint16a", [0, 65535], [5666], waveform_d),
        (npt.NDArray[np.int32], "int32a", [-2147483648, 2147483647], [-2], waveform_d),
        (npt.NDArray[np.uint32], "uint32a", [0, 4294967295], [1022233], waveform_d),
        (npt.NDArray[np.int64], "int64a", [-2147483649, 2147483648], [-3], waveform_d),
        (npt.NDArray[np.uint64], "uint64a", [0, 4294967297], [995444], waveform_d),
        (npt.NDArray[np.float32], "float32a", [0.000002, -123.123], [1.0], waveform_d),
        (npt.NDArray[np.float64], "float64a", [0.1, -12345678.123], [0.2], waveform_d),
        (Sequence[str], "stra", ["five", "six", "seven"], ["nine", "ten"], waveform_d),
        # Can't do long strings until https://github.com/epics-base/pva2pva/issues/17
        # (str, "longstr", ls1, ls2, string_d),
        # (str, "longstr2.VAL$", ls1, ls2, string_d),
    ],
)
async def test_backend_get_put_monitor(ioc: IOC, typ, suff, initial, put, descriptor):
    # ca can't support all the types
    dtype = get_dtype(typ)
    if ioc.protocol == "ca" and dtype and dtype.type in ca_dtype_mapping:
        if dtype == np.int8:
            # CA maps uint8 onto int8 rather than upcasting, so we need to change initial
            # array
            initial, put = [np.array(x).astype(np.uint8) for x in (initial, put)]
        typ = npt.NDArray[ca_dtype_mapping[dtype.type]]  # type: ignore
    # Make and connect the backend
    for t, i, p in [(typ, initial, put), (None, put, initial)]:
        if typ is bool and t is None:
            # IOC can't do bool, we have to tell it explicitly
            continue
        backend = await ioc.make_backend(t, suff)
        # Make a monitor queue that will monitor for updates
        q = MonitorQueue(backend)
        try:
            # Check descriptor
            source = f"{ioc.protocol}://{PV_PREFIX}:{ioc.protocol}:{suff}"
            dict(source=source, **descriptor) == await backend.get_descriptor()
            # Check initial value
            await q.check_updates(pytest.approx(i))
            # Put to new value and check that
            await backend.put(p)
            await q.check_updates(pytest.approx(p))
        finally:
            q.close()


class BadEnum(Enum):
    a = "Aaa"
    b = "B"
    c = "Ccc"


@pytest.mark.parametrize(
    "typ, suff, error",
    [
        (BadEnum, "enum", "has choices ('Aaa', 'Bbb', 'Ccc') not ('Aaa', 'B', 'Ccc')"),
        (int, "str", "has type str not int"),
        (str, "float", "has type float not str"),
        (str, "stra", "has type [str] not str"),
        (int, "uint8a", "has type [uint8] not int"),
        (float, "enum", "has type Enum not float"),
        (npt.NDArray[np.int32], "float64a", "has type [float64] not [int32]"),
    ],
)
async def test_backend_wrong_type_errors(ioc: IOC, typ, suff, error):
    with pytest.raises(
        TypeError, match=re.escape(f"{PV_PREFIX}:{ioc.protocol}:{suff} {error}")
    ):
        await ioc.make_backend(typ, suff)


async def test_backend_put_enum_string(ioc: IOC) -> None:
    backend = await ioc.make_backend(MyEnum, "enum2")
    # Don't do this in production code, but allow on CLI
    await backend.put("Ccc")  # type: ignore
    assert MyEnum.c == await backend.get_value()


def approx_table(table):
    return {k: pytest.approx(v) for k, v in table.items()}


class MyTable(TypedDict):
    bool: npt.NDArray[np.bool_]
    int: npt.NDArray[np.int32]
    float: npt.NDArray[np.float64]
    str: Sequence[str]
    enum: Sequence[MyEnum]


async def test_pva_table(ioc: IOC) -> None:
    if ioc.protocol == "ca":
        # CA can't do tables
        return
    initial = MyTable(
        bool=np.array([False, False, True, True], np.bool_),
        int=np.array([1, 8, -9, 32], np.int32),
        float=np.array([1.8, 8.2, -6, 32.9887], np.float64),
        str=["Hello", "World", "Foo", "Bar"],
        enum=[MyEnum.a, MyEnum.b, MyEnum.a, MyEnum.c],
    )
    put = MyTable(
        bool=np.array([True, False], np.bool_),
        int=np.array([-5, 32], np.int32),
        float=np.array([8.5, -6.97], np.float64),
        str=["Hello", "Bat"],
        enum=[MyEnum.c, MyEnum.b],
    )
    # TODO: what should this be for a variable length table?
    descriptor = dict(dtype="object", shape=[])
    # Make and connect the backend
    for t, i, p in [(MyTable, initial, put), (None, put, initial)]:
        backend = await ioc.make_backend(t, "table")
        # Make a monitor queue that will monitor for updates
        q = MonitorQueue(backend)
        try:
            # Check descriptor
            dict(source=backend.source, **descriptor) == await backend.get_descriptor()
            # Check initial value
            await q.check_updates(approx_table(i))
            # Put to new value and check that
            await backend.put(p)
            await q.check_updates(approx_table(p))
        finally:
            q.close()


async def test_non_existant_errors(ioc: IOC):
    backend = await ioc.make_backend(str, "non-existant", connect=False)
    # Can't use asyncio.wait_for on python3.8 because of
    # https://github.com/python/cpython/issues/84787
    done, pending = await asyncio.wait(
        [asyncio.create_task(backend.connect())], timeout=0.1
    )
    assert len(done) == 0
    assert len(pending) == 1
    t = pending.pop()
    t.cancel()
    with pytest.raises(NotConnected, match=backend.source):
        await t


def test_make_backend_fails_for_different_transports():
    read_pv = "test"
    write_pv = "pva://test"

    with pytest.raises(TypeError) as err:
        _make_backend(str, read_pv, write_pv)
        assert err.args[0] == f"Differing transports: {read_pv} has EpicsTransport.ca,"
        +" {write_pv} has EpicsTransport.pva"
