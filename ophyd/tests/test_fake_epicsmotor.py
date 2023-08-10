from ophyd.sim import make_fake_device
from ophyd.epics_motor import EpicsMotor
from bluesky.run_engine import RunEngine
import pytest
import bluesky.plan_stubs as bps
from unittest.mock import MagicMock


@pytest.fixture
def RE():
    yield RunEngine()


@pytest.fixture
def fake_motor():
    yield make_fake_device(EpicsMotor)(name="fake_motor")


def assert_motor_set_uses_setpoint_put(motor: EpicsMotor):
    setpoint_put: MagicMock = motor.user_setpoint.put
    setpoint_put.assert_called()
    setpoint_set: MagicMock = motor.user_setpoint.set
    setpoint_set.assert_not_called()


def test_make_fake_epicsmotor_and_set_it(fake_motor: EpicsMotor):
    assert fake_motor.user_readback.get() == 0
    move_status = fake_motor.set(3)
    assert fake_motor.user_readback.get() == 3
    assert move_status.done
    assert_motor_set_uses_setpoint_put(fake_motor)


def test_fakeepicsmotor_abs_set(RE, fake_motor: EpicsMotor):
    assert fake_motor.user_readback.get() == 0
    RE(bps.abs_set(fake_motor, 3))
    assert fake_motor.user_readback.get() == 3
    assert_motor_set_uses_setpoint_put(fake_motor)


def test_fakeepicsmotor_rel_set(RE, fake_motor: EpicsMotor):
    assert fake_motor.user_readback.get() == 0
    RE(bps.rel_set(fake_motor, 3))
    assert fake_motor.user_readback.get() == 3
    RE(bps.rel_set(fake_motor, 3))
    assert fake_motor.user_readback.get() == 6
    assert_motor_set_uses_setpoint_put(fake_motor)
