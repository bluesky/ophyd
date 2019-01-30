"""Check if a missing value stops program
"""
import pytest
from ophyd import sim, Device, Component as Cpt

class ADevice(Device):
    """Just to create a device
    """
    signal = Cpt(sim.FakeEpicsSignalRO, 'a_fake_signal')


def _get_fake_signal():
    return ADevice(name = "fake_device")

def test_describe_fail():
    """If readback was never set, does descirbe fail?

    I guess that's a bug
    """
    # self.assertRaises(ValueError, self.fake_signal.describe)
    fs = _get_fake_signal()
    with pytest.raises(AssertionError):
        fs.describe()

def test_describe_after_set():
    """If readback was set does descirbe fail?

    SHould work
    """
    fs = _get_fake_signal()
    fs.signal.sim_put(42)
    fs.describe()
