"""Check if a missing value stops program
"""
import pytest
import logging

from ophyd import sim, Device, Component as Cpt
from ophyd.utils.errors import NonPVValue

pvs_varname = 'fake_device'
class ADevice(Device):
    """Just to create a device
    """
    signal = Cpt(sim.FakeEpicsSignalRO, pvs_varname)


def _get_fake_signal():
    return ADevice(name = pvs_varname)

def test_describe_fail():
    """If readback was never set, does describe fail?

    The variable name shall be reported in the exception description
    """
    fs = _get_fake_signal()
    with pytest.raises(NonPVValue) as des:
        fs.describe()

    # check if the variable name is given as quoted string in the description
    msg, =  des.value.args
    assert(f"'{pvs_varname}_signal'" in msg)

def test_describe_after_set():
    """If readback was set does descirbe fail?

    Should work
    """
    fs = _get_fake_signal()
    fs.signal.sim_put(42)
    fs.describe()


def test_describe_after_set_invalid_value():
    """Is error message appropriate if

    lets see
    """
    fs = _get_fake_signal()
    fs.signal.sim_put(ValueError)

    with pytest.raises(NonPVValue) as des:
        fs.describe()

    # check if the variable name is given as quoted string in the description
    msg_signal, =  des.value.args
    assert(f"'{pvs_varname}_signal'" in msg_signal)
