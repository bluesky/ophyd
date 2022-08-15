import logging
import time

import pytest
from numpy.testing import assert_almost_equal

from ophyd import EpicsSignal, EpicsSignalRO

logger = logging.getLogger(__name__)


@pytest.mark.motorsim
def test_read_pv_timestamp_no_monitor(motor):
    motor.set(0, wait=True)
    sp = EpicsSignal(motor.user_setpoint.pvname, name="test")
    rbv = EpicsSignalRO(motor.user_readback.pvname, name="test")

    assert rbv.get() == sp.get()
    rbv_value0 = rbv.get()
    ts0 = rbv.timestamp
    sp.put(sp.get() + 0.1)
    time.sleep(0.5)
    rbv_value1 = rbv.get()
    ts1 = rbv.timestamp
    assert ts1 > ts0
    assert_almost_equal(rbv_value0 + 0.1, rbv_value1)

    sp.put(sp.get() - 0.1)


@pytest.mark.motorsim
def test_write_pv_timestamp_no_monitor(motor):
    motor.set(0, wait=True)
    sp = EpicsSignal(motor.user_setpoint.pvname, name="test")

    sp_value0 = sp.get()
    ts0 = sp.timestamp
    sp.put(sp_value0 + 0.1, wait=True)
    time.sleep(0.1)

    sp_value1 = sp.get()
    ts1 = sp.timestamp
    assert ts1 > ts0
    assert_almost_equal(sp_value0 + 0.1, sp_value1)

    sp.put(sp.get() - 0.1, wait=True)


@pytest.mark.motorsim
def test_read_pv_timestamp_monitor(motor):
    motor.set(0, wait=True)

    sp = EpicsSignal(motor.user_setpoint.pvname, auto_monitor=True, name="test")
    rbv = EpicsSignalRO(motor.user_readback.pvname, auto_monitor=True, name="test")

    rbv_value0 = rbv.get()
    ts0 = rbv.timestamp
    sp.put(rbv_value0 + 0.1, wait=True)
    time.sleep(0.2)

    rbv_value1 = rbv.value
    ts1 = rbv.timestamp
    assert ts1 > ts0
    assert_almost_equal(rbv_value0 + 0.1, rbv_value1)

    sp.put(sp.value - 0.1, wait=True)


@pytest.mark.motorsim
def test_write_pv_timestamp_monitor(motor):
    motor.set(0, wait=True)
    sp = EpicsSignal(motor.user_setpoint.pvname, auto_monitor=True, name="test")

    sp_value0 = sp.get()
    ts0 = sp.timestamp
    sp.put(sp_value0 + 0.1, wait=True)
    time.sleep(0.1)

    sp_value1 = sp.value
    ts1 = sp.timestamp
    assert ts1 > ts0
    assert_almost_equal(sp_value0 + 0.1, sp_value1)

    sp.put(sp.value - 0.1, wait=True)
