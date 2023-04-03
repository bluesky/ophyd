import asyncio
import re
from unittest.mock import Mock

import pytest
from bluesky.protocols import Status

from ophyd.v2.core import AsyncStatus, Signal


class MySignal(Signal):
    @property
    def source(self) -> str:
        return "me"

    async def connect(self, prefix: str = "", sim=False):
        pass


def test_signals_equality_raises():
    s1 = MySignal()
    s2 = MySignal()
    with pytest.raises(
        TypeError,
        match=re.escape(
            "Can't compare two Signals, did you mean await signal.get_value() instead?"
        ),
    ):
        s1 == s2
    with pytest.raises(
        TypeError,
        match=re.escape("'>' not supported between instances of 'MySignal' and 'int'"),
    ):
        s1 > 4


async def test_async_status_success():
    st = AsyncStatus(asyncio.sleep(0.1))
    assert isinstance(st, Status)
    assert not st.done
    assert not st.success
    await st
    assert st.done
    assert st.success


async def normal_coroutine(time: float):
    await asyncio.sleep(time)


async def failing_coroutine(time: float):
    await normal_coroutine(time)
    raise ValueError()


async def test_async_status_propagates_exception():
    status = AsyncStatus(failing_coroutine(0.1))
    assert status.exception is None

    with pytest.raises(ValueError):
        await status

    assert type(status.exception) == ValueError


async def test_async_status_propagates_cancelled_error():
    status = AsyncStatus(normal_coroutine(0.1))
    assert status.exception is None

    status.task.exception = Mock(side_effect=asyncio.CancelledError(""))
    await status

    assert type(status.exception) == asyncio.CancelledError


async def test_async_status_has_no_exception_if_coroutine_successful():
    status = AsyncStatus(normal_coroutine(0.1))
    assert status.exception is None

    await status

    assert status.exception is None


async def test_async_status_success_if_cancelled():
    status = AsyncStatus(normal_coroutine(0.1))
    assert status.exception is None

    status.task.result = Mock(side_effect=asyncio.CancelledError(""))
    await status

    assert status.success is False
