import logging

import pytest

from ophyd import Component, Device, EpicsSignal
from ophyd.signal import EpicsSignalBase

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


def test_epics_signal_base_connection_timeout():
    EpicsSignalBase.set_defaults(connection_timeout=1e-6)
    class MyDevice(Device):
        # Should timeout using default connection timeout
        cpt1 = Component(EpicsSignal, "1")
        # Should *not* timeout using custom connection timeout
        cpt2 = Component(EpicsSignal, "2", connection_timeout=1.0)

    device = MyDevice("prefix:", name="dev")
    with pytest.raises(TimeoutError) as cm:
        device.cpt1.kind = "hinted"
    device.cpt2.kind = "hinted"

    ex_msg = str(cm.value)
    print(ex_msg)