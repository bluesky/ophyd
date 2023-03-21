import asyncio
import re

import pytest

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


async def some_coroutine():
    await asyncio.sleep(0.1)
    raise ValueError()


async def test_async_status_exception():
    status = AsyncStatus(some_coroutine())
    assert status.exception is None

    with pytest.raises(ValueError):
        await status

    assert type(status.exception) == ValueError
