import asyncio
import random
import string
import subprocess
import sys
import time
from enum import Enum
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pytest
from softioc import asyncio_dispatcher, builder, softioc
from softioc.builder import records

from ophyd.v2.core import NotConnected
from ophyd.v2.epics import ChannelP4p

RECORDS = str(Path(__file__).parent / "test_records.db")
PV_PREFIX = "".join(random.choice(string.ascii_uppercase) for _ in range(12))
LONGOUT = "longout"
AO = "ao"
MBBO = "mbbo"
MBBI = "mbbi"
WAVEFORM = "waveform"
NE = "nonexistant"
PV_LONGOUT = PV_PREFIX + ":" + LONGOUT
PV_AO = PV_PREFIX + ":" + AO
PV_MBBO = PV_PREFIX + ":" + MBBO
PV_MBBI = PV_PREFIX + ":" + MBBI
PV_WAVEFORM = PV_PREFIX + ":" + WAVEFORM
PV_NE = PV_PREFIX + ":" + NE

# Use a module level fixture so it's fast to run tests. This means we need to
# add a record for every PV that we will modify in tests to stop tests
# interfering with each other
@pytest.fixture(scope="module")
def ioc():
    # Create an asyncio dispatcher, the event loop is now running
    dispatcher = asyncio_dispatcher.AsyncioDispatcher()

    # Set the record prefix
    builder.SetDeviceName(PV_PREFIX)

    # Create some records
    ao = records.ao(AO, PREC="1", EGU="mm", VAL="3.141", PINI="YES")

    lo = records.longout(
        LONGOUT,
        HOPR="100",
        HIHI="98",
        HIGH="96",
        DRVH="90",
        DRVL="10",
        LOW="5",
        LOLO="2",
        LOPR="0",
        VAL="42",
        PINI="YES"
        )

    mbbo = records.mbbo(
        MBBO,
        ZRST="Aaa",
        ZRVL="5",
        ONST="Bbb",
        ONVL="6",
        TWST="Ccc",
        TWVL="7",
        VAL="1",
        PINI="YES"
        )

    mbbi = records.mbbi(
        MBBI,
        ZRST="Aaa",
        ONST="Bbb",
        TWST="Ccc",
        VAL="1",
        PINI="YES"
        )

    waveform = records.waveform(
        WAVEFORM,
        NELM="3",
        FTVL="DOUBLE",
        INP="[1.5, 2.5, 3.5]",
        PINI="YES"
        )


    # Boilerplate get the IOC started
    builder.LoadDatabase()
    softioc.iocInit(dispatcher)


async def test_p4p_signal_get_put_long(ioc):
    pv = ChannelP4p(PV_AO, float)
    await pv.connect()
    assert (await pv.get_value()) == 3.141
    await pv.put(43.5)
    assert (await pv.get_value()) == 43.5
    await pv.put(44.1)
    assert (await pv.get_descriptor()) == {
        "source": f"pva://{PV_AO}",
        "dtype": "number",
        "shape": [],
    }
    assert (await pv.get_reading()) == {
        "value": 44.1,
        "timestamp": pytest.approx(time.time(), rel=0.1),
        "alarm_severity": 0,
    }


async def test_p4p_signal_monitoring(ioc):
    pv = ChannelP4p(PV_LONGOUT, int)
    await pv.connect()

    async def prod_pv():
        for i in range(43, 46):
            await asyncio.sleep(0.2)
            await pv.put(i)

    t = asyncio.create_task(prod_pv())

    q = asyncio.Queue()
    m = pv.monitor_reading_value(lambda r, v: q.put_nowait(v))
    for expected in range(42, 46):
        v = await asyncio.wait_for(q.get(), timeout=0.5)
        assert v == expected

    m.close()
    await t


class MyEnum(Enum):
    a = "Aaa"
    b = "Bbb"
    c = "Ccc"


async def test_p4p_signal_get_put_enum(ioc) -> None:
    pv = ChannelP4p(PV_MBBO, MyEnum)
    await pv.connect()
    assert (await pv.get_value()) == MyEnum.b
    await pv.put(MyEnum.c)
    assert (await pv.get_value()) == MyEnum.c
    # Don't do this in production code, but allow on CLI
    await pv.put("Aaa")  # type: ignore
    assert (await pv.get_value()) == MyEnum.a


class BadEnum(Enum):
    a = "Aaa"
    typo = "Baa"


async def test_p4p_signal_with_bad_enum(ioc):
    pv = ChannelP4p(PV_MBBO, BadEnum)
    with pytest.raises(ValueError) as cm:
        await pv.connect()
    assert str(cm.value) == "Enum strings {'Baa'} not in ['Aaa', 'Bbb', 'Ccc']"


async def test_p4p_enum_monitor_reading(ioc):
    pv = ChannelP4p(PV_MBBI, MyEnum)
    pv_int = ChannelP4p(PV_MBBI, int)
    await asyncio.gather(pv.connect(), pv_int.connect())

    q = asyncio.Queue()
    m = pv.monitor_reading_value(lambda r, v: q.put_nowait((r, v)))
    v1 = await q.get()
    assert v1[0] == {
        "value": MyEnum.b,
        "timestamp": pytest.approx(time.time(), rel=0.1),
        "alarm_severity": 0,
    }

    await pv_int.put(2)
    v2 = await q.get()
    assert v2[1] == MyEnum.c

    m.close()


async def test_p4p_signal_get_put_waveform(ioc) -> None:
    pv = ChannelP4p(PV_WAVEFORM, npt.NDArray[np.float64])
    await pv.connect()
    assert (await pv.get_descriptor()) == {
        "source": f"pva://{PV_WAVEFORM}",
        "dtype": "array",
        "shape": [3],
    }
    assert (await pv.get_value()) == pytest.approx([1.5, 2.5, 3.5])
    await pv.put(np.array([1.5, 3.5]))
    assert (await pv.get_value()) == pytest.approx([1.5, 3.5])


async def test_non_existant_errors():
    pv = ChannelP4p(PV_NE, str)
    # Can't use asyncio.wait_for on python3.8 because of
    # https://github.com/python/cpython/issues/84787
    done, pending = await asyncio.wait([pv.connect()], timeout=0.1)
    assert len(done) == 0
    assert len(pending) == 1
    t = pending.pop()
    t.cancel()
    with pytest.raises(NotConnected, match=f"pva://{PV_NE}"):
        await t
