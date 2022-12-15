import re

import pytest

from ophyd.v2.core import Signal


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
