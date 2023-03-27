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
from typing import Any, Literal, Tuple, Type

import numpy as np
import numpy.typing as npt
import pytest
from aioca import purge_channel_caches
from bluesky.protocols import Reading

from ophyd.v2.core import NotConnected
from ophyd.v2.epics import Channel, EpicsTransport

RECORDS = str(Path(__file__).parent / "test_records.db")
PV_PREFIX = "".join(random.choice(string.ascii_lowercase) for _ in range(12))


@dataclass
class IOC:
    process: subprocess.Popen
    protocol: Literal["ca", "pva"]

    def make_channel(self, suffix: str, typ: Type):
        # Calculate the pv
        pv = f"{PV_PREFIX}:{self.protocol}:{suffix}"
        # Make and connect the channel
        cls: Type[Channel] = EpicsTransport[self.protocol].value
        return cls(pv, typ)


# Use a module level fixture per protocol so it's fast to run tests. This means
# we need to add a record for every PV that we will modify in tests to stop
# tests interfering with each other
@pytest.fixture(scope="module", params=["ca", "pva"])
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
    # close channel caches before the event loop
    purge_channel_caches()
    try:
        print(process.communicate("exit")[0])
    except ValueError:
        # Someone else already called communicate
        pass


class MonitorQueue:
    def __init__(self, channel: Channel):
        self.channel = channel
        self.subscription = channel.monitor_reading_value(self.add_reading_value)
        self.updates: asyncio.Queue[Tuple[Reading, Any]] = asyncio.Queue()

    def add_reading_value(self, reading: Reading, value):
        self.updates.put_nowait((reading, value))

    async def check_updates(self, expected_value):
        expected_reading = {
            "value": pytest.approx(expected_value),
            "timestamp": pytest.approx(time.time(), rel=0.1),
            "alarm_severity": 0,
        }
        reading, value = await self.updates.get()
        assert value == pytest.approx(expected_value) == await self.channel.get_value()
        assert reading == expected_reading == await self.channel.get_reading()

    def close(self):
        self.subscription.close()


class MyEnum(Enum):
    a = "Aaa"
    b = "Bbb"
    c = "Ccc"


string_d = dict(dtype="string", shape=[])
number_d = dict(dtype="number", shape=[])
enum_d = dict(dtype="string", shape=[], choices=["Aaa", "Bbb", "Ccc"])
waveform_d = dict(dtype="number", shape=[3])


@pytest.mark.parametrize(
    "typ, suff, initial, put, descriptor",
    [
        (str, "stringout", "hello", "goodbye", string_d),
        (float, "ao", 3.141, 43.5, number_d),
        (int, "longout", 42, 43, number_d),
        (MyEnum, "mbbo", MyEnum.b, MyEnum.c, enum_d),
        (npt.NDArray[np.float64], "waveform", [1.5, 2.5, 3.5], [1.5, 3.5], waveform_d),
    ],
)
async def test_channel_get_put_monitor(ioc: IOC, typ, suff, initial, put, descriptor):
    # Make and connect the channel
    channel = ioc.make_channel(suff, typ)
    await channel.connect()
    # Make a monitor queue that will monitor for updates
    q = MonitorQueue(channel)
    try:
        # Check descriptor
        dict(
            source=f"{ioc.protocol}://{channel.pv}", **descriptor
        ) == await channel.get_descriptor()
        # Check initial value
        await q.check_updates(initial)
        # Put to new value and check that
        await channel.put(put)
        await q.check_updates(put)
    finally:
        q.close()


class BadEnum(Enum):
    a = "Aaa"
    typo = "Baa"


@pytest.mark.parametrize(
    "typ, suff, error",
    [
        (BadEnum, "mbbo", "Enum strings {'Baa'} not in ['Aaa', 'Bbb', 'Ccc']"),
        (int, "stringout", "Not of type int"),
        (str, "ao", "Not of type str"),
        (npt.NDArray[np.int32], "waveform", "Not of type [int32]"),
    ],
)
async def test_channel_wrong_type_errors(ioc: IOC, typ, suff, error):
    channel = ioc.make_channel(suff, typ)
    with pytest.raises(TypeError, match=re.escape(f"{channel.pv}: {error}")):
        await channel.connect()


async def test_channel_put_enum_string_int(ioc: IOC) -> None:
    channel = ioc.make_channel("mbbi", MyEnum)
    int_channel = ioc.make_channel("mbbi", int)
    await asyncio.gather(channel.connect(), int_channel.connect())
    # Don't do this in production code, but allow on CLI
    await channel.put("Ccc")  # type: ignore
    assert MyEnum.c == await channel.get_value()
    assert 2 == await int_channel.get_value()
    await int_channel.put(1)
    assert MyEnum.b == await channel.get_value()


async def test_non_existant_errors(ioc: IOC):
    channel = ioc.make_channel("non-existant", str)
    # Can't use asyncio.wait_for on python3.8 because of
    # https://github.com/python/cpython/issues/84787
    done, pending = await asyncio.wait([channel.connect()], timeout=0.1)
    assert len(done) == 0
    assert len(pending) == 1
    t = pending.pop()
    t.cancel()
    with pytest.raises(NotConnected, match=f"{ioc.protocol}://{channel.pv}"):
        await t
