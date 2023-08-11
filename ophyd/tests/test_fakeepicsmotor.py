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
    fake_motor = make_fake_device(EpicsMotor)(name="fake_motor")
    assert fake_motor.user_readback.get() == 0
    assert_setpoint_and_readback_equal(fake_motor)
    yield fake_motor


def assert_FakeEpicsMotor_set_uses_setpoint_put(motor: EpicsMotor):
    setpoint_put: MagicMock = motor.user_setpoint.put
    setpoint_put.assert_called()
    setpoint_set: MagicMock = motor.user_setpoint.set
    setpoint_set.assert_not_called()


def assert_setpoint_and_readback_equal(motor: EpicsMotor):
    assert motor.user_setpoint.get() == motor.user_readback.get()


def test_make_FakeEpicsMotor_and_set_it(fake_motor: EpicsMotor):
    move_status = fake_motor.set(3)
    assert fake_motor.user_readback.get() == 3
    assert move_status.done
    assert_FakeEpicsMotor_set_uses_setpoint_put(fake_motor)
    assert_setpoint_and_readback_equal(fake_motor)


def test_FakeEpicsMotor_abs_set(RE: RunEngine, fake_motor: EpicsMotor):
    RE(bps.abs_set(fake_motor, 3))
    assert fake_motor.user_readback.get() == 3
    assert_setpoint_and_readback_equal(fake_motor)
    assert_FakeEpicsMotor_set_uses_setpoint_put(fake_motor)


def test_FakeEpicsMotor_rel_set(RE: RunEngine, fake_motor: EpicsMotor):
    RE(bps.rel_set(fake_motor, 3))
    assert fake_motor.user_readback.get() == 3
    assert_setpoint_and_readback_equal(fake_motor)
    RE(bps.rel_set(fake_motor, 3))
    assert fake_motor.user_readback.get() == 6
    assert_setpoint_and_readback_equal(fake_motor)
    RE(bps.rel_set(fake_motor, -1.5))
    assert fake_motor.user_readback.get() == 4.5
    assert_setpoint_and_readback_equal(fake_motor)
    setpoint_put: MagicMock = fake_motor.user_setpoint.put
    assert setpoint_put.call_count == 3
    assert_setpoint_and_readback_equal(fake_motor)
    assert_FakeEpicsMotor_set_uses_setpoint_put(fake_motor)


def test_FakeEpicsMotor_mv(RE: RunEngine, fake_motor: EpicsMotor):
    RE(bps.mv(fake_motor, 3))
    assert fake_motor.user_readback.get() == 3
    assert_setpoint_and_readback_equal(fake_motor)
    assert_FakeEpicsMotor_set_uses_setpoint_put(fake_motor)


def test_FakeEpicsMotor_rd(RE: RunEngine, fake_motor: EpicsMotor):
    def rd_plan(motor):
        pos = yield from bps.rd(fake_motor)
        assert pos == 0
        yield from bps.mv(fake_motor, 3)
        pos = yield from bps.rd(fake_motor)
        assert pos == 3

    RE(rd_plan(fake_motor))
    assert fake_motor.user_readback.get() == 3
    assert_setpoint_and_readback_equal(fake_motor)
    assert_FakeEpicsMotor_set_uses_setpoint_put(fake_motor)


def test_FakeEpicsMotor_read(RE: RunEngine, fake_motor: EpicsMotor):
    from bluesky.callbacks import CallbackBase

    class TestCallback(CallbackBase):
        def event(self, doc):
            assert doc["data"]["fake_motor"] == 3

    def read_plan(motor):
        pos = yield from bps.rd(fake_motor)
        assert pos == 0
        yield from bps.mv(fake_motor, 3)
        yield from bps.open_run()
        yield from bps.create()
        pos = yield from bps.read(fake_motor)
        yield from bps.save()
        yield from bps.close_run()

    RE.subscribe(TestCallback())
    RE(read_plan(fake_motor))
    assert_setpoint_and_readback_equal(fake_motor)


def test_FakeEpicsMotor_still_rejects_nonsense_values(fake_motor: EpicsMotor):
    with pytest.raises(TypeError) as e:
        fake_motor.set("can't set a string")
    assert "not supported between instances" in e.value.args[0]


def test_FakeEpicsMotor_rejects_outside_lims_if_set(fake_motor: EpicsMotor):
    fake_motor.user_setpoint.sim_set_limits([-1, 1])
    from ophyd.utils.errors import LimitError

    with pytest.raises(LimitError) as e:
        fake_motor.set(2)
    assert "not within" in e.value.args[0]
