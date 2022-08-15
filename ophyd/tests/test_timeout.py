import logging

import pytest

from ophyd import Component, Device, EpicsSignal

logger = logging.getLogger(__name__)


def test_timeout():
    class SubSubDevice(Device):
        cpt5 = Component(EpicsSignal, "5")

    class SubDevice(Device):
        cpt4 = Component(EpicsSignal, "4")
        subsub1 = Component(SubSubDevice, "sub_")

    class MyDevice(Device):
        sub1 = Component(EpicsSignal, "1")
        sub2 = Component(SubDevice, "_")
        cpt3 = Component(EpicsSignal, "3")

    device = MyDevice("prefix:", name="dev")

    with pytest.raises(TimeoutError) as cm:
        device.wait_for_connection(timeout=1e-6)

    ex_msg = str(cm.value)
    assert "dev.sub1" in ex_msg
    assert "dev.sub2.cpt4" in ex_msg
    assert "dev.sub2.subsub1.cpt5" in ex_msg
    assert "dev.cpt3" in ex_msg
    assert "prefix:1" in ex_msg
    assert "prefix:_4" in ex_msg
    assert "prefix:_sub_5" in ex_msg
    assert "prefix:3" in ex_msg
