import logging
import threading
import time
from copy import copy

import pytest
from numpy.testing import assert_allclose

from ophyd import Component as Cpt
from ophyd import EpicsMotor, MotorBundle
from ophyd.utils import UnknownStatusFailure
from ophyd.utils.epics_pvs import AlarmSeverity, AlarmStatus

logger = logging.getLogger(__name__)


@pytest.mark.motorsim
def test_timeout(motor):
    assert motor.timeout == 10.0
    motor.timeout = 20.0
    assert motor.timeout == 20.0


@pytest.mark.motorsim
def test_connected(motor):
    assert motor.connected


@pytest.mark.motorsim
def test_limits(motor):
    device_limits = (motor.low_limit_value.get(), motor.high_limit_value.get())
    assert motor.limits == device_limits


@pytest.mark.motorsim
def test_checkvalue(motor):
    motor.check_value(0)


@pytest.mark.motorsim
def test_move(motor):
    motor.stop()
    motor.move(0.1, timeout=5, wait=True)

    logger.debug("Move to 0.0")
    motor.move(0.0, timeout=5, wait=True)
    time.sleep(0.1)
    assert_allclose(motor.position, 0.0)

    assert motor.settle_time == 0.1

    logger.debug("Move to 0.1")
    motor.move(0.1, timeout=5, wait=True)
    time.sleep(0.1)
    assert_allclose(motor.position, 0.1)

    logger.debug("Move to 0.1, again")
    motor.move(0.1, timeout=5, wait=True)
    time.sleep(0.1)
    assert_allclose(motor.position, 0.1)

    logger.debug("Move to 0.0")
    motor.move(0.0, timeout=5, wait=True)
    time.sleep(0.1)
    assert_allclose(motor.position, 0.0)


@pytest.mark.motorsim
def test_copy(motor):
    repr(motor)
    str(motor)

    mc = copy(motor)
    assert mc.prefix == motor.prefix

    res = motor.move(0.2, wait=False)

    while not res.done:
        time.sleep(0.1)

    time.sleep(0.1)
    assert res.settle_time == 0.1
    assert_allclose(motor.position, 0.2)

    motor.settle_time = 0.2
    assert motor.settle_time == 0.2

    assert res.done
    assert_allclose(res.error, 0, atol=1e-6)
    assert res.elapsed > 0


@pytest.mark.motorsim
def test_read(motor):
    motor.read()


@pytest.mark.motorsim
def test_report(motor):
    motor.report


@pytest.mark.motorsim
def test_calibration(motor):
    motor.user_offset.put(0, wait=True)

    # Calibration
    old_position = motor.position
    expected_offset = 10 - motor.position
    motor.set_current_position(10)
    assert motor.offset_freeze_switch.get() == 0
    assert_allclose(motor.position, 10)
    assert motor.user_offset.get() == expected_offset
    motor.set_current_position(old_position)


@pytest.mark.motorsim
def test_high_limit_switch(motor):
    # limit switch status
    motor.direction_of_travel.put(1)
    motor.high_limit_switch.put(1)
    res = motor.move(1, wait=False)
    repr(res)
    assert res.timeout == 10.0

    with pytest.raises(UnknownStatusFailure):
        res.wait(11)
    assert motor.high_limit_switch.get() == 1

    motor.high_limit_switch.put(0)


@pytest.mark.motorsim
def test_low_limit_switch(motor):
    motor.direction_of_travel.put(0)
    motor.low_limit_switch.put(1)
    res = motor.move(0, wait=False)

    with pytest.raises(UnknownStatusFailure):
        res.wait(11)
    assert motor.low_limit_switch.get() == 1
    motor.low_limit_switch.put(0)


@pytest.mark.motorsim
def test_low_limit_switch_while_moving_out(motor):
    # If the Motor is at the Low Limit Switch
    # all the movements in the opposite
    # direction must be success=True
    motor.direction_of_travel.put(1)
    motor.low_limit_switch.put(1)
    res = motor.move(1, wait=False)

    while not res.done:
        time.sleep(0.1)

    assert motor.low_limit_switch.get() == 1
    assert res.success
    motor.low_limit_switch.put(0)


@pytest.mark.motorsim
def test_high_limit_switch_while_moving_out(motor):
    # If the Motor is at the High Limit Switch
    # all the movements in the opposite
    # direction must be success=True
    motor.direction_of_travel.put(0)
    motor.high_limit_switch.put(1)
    res = motor.move(0, wait=False)

    while not res.done:
        time.sleep(0.1)

    assert motor.high_limit_switch.get() == 1
    assert res.success
    motor.high_limit_switch.put(0)


# @pytest.mark.skip(reason="This has become flaky, not sure why")
@pytest.mark.motorsim
def test_homing_forward(motor):
    # homing forward
    motor.wait_for_connection(all_signals=True, timeout=2)
    motor.move(-1, wait=True)
    res = motor.home("forward", timeout=2, wait=False)

    while not res.done:
        time.sleep(0.1)

    # MotorSim is unable to execute homing
    assert not res.success
    motor.stop()


# @pytest.mark.skip(reason="This has become flaky, not sure why")
@pytest.mark.motorsim
def test_homing_reverse(motor):
    # homing reverse
    motor.move(1, wait=True)
    res = motor.home("reverse", timeout=2, wait=False)

    while not res.done:
        time.sleep(0.1)

    assert not res.success
    motor.stop()


@pytest.mark.motorsim
def test_homing_invalid(motor):
    with pytest.raises(ValueError):
        # homing reverse
        motor.move(1, wait=True)
        res = motor.home("foobar", timeout=2, wait=False)

        while not res.done:
            time.sleep(0.1)

        assert not res.success
        motor.stop()


@pytest.mark.motorsim
def test_move_alarm(motor):
    try:
        motor.user_readback.alarm_status = AlarmStatus.COMM
        motor.user_readback.alarm_severity = AlarmSeverity.MAJOR

        if motor.position + 1 < motor.high_limit_value.get():
            target_pos = motor.position + 1
        else:
            target_pos = motor.position - 1

        st = motor.move(target_pos, wait=False)

        while not st.done:
            time.sleep(0.1)

        assert not st.success
    finally:
        motor.user_readback.alarm_status = AlarmStatus.NO_ALARM
        motor.user_readback.alarm_severity = AlarmSeverity.NO_ALARM


@pytest.mark.motorsim
def test_hints(motor):
    assert motor.hints == {"fields": list(motor.user_readback.read())}

    motor.user_setpoint.kind = "hinted"
    motor.user_readback.kind = "normal"
    assert motor.hints == {"fields": list(motor.user_setpoint.read())}


@pytest.mark.motorsim
def test_watchers(motor):

    st = motor.set(0)
    while not st.done:
        continue

    collector = []

    def collect(fraction, **kwargs):
        collector.append(fraction)

    def callback(status):
        ev.set()

    st = motor.set(1)
    st.watch(collect)
    ev = threading.Event()
    st.add_callback(callback)
    ev.wait()
    assert collector
    assert collector[-1] == 0.0
    assert len(collector) > 1


@pytest.mark.motorsim
def test_str_smoke(motor):
    str(motor)


@pytest.mark.motorsim
def test_read_in_motor_callback(motor):
    out_cache = []
    motor.set(0, wait=True)

    def cb(**kwargs):
        v = motor.read()
        out_cache.append(v)

    motor.subscribe(cb)
    motor.set(0.1, wait=True)
    assert len(out_cache) > 0


def test_motor_bundle():
    class Bundle(MotorBundle):
        a = Cpt(EpicsMotor, ":mtr1")
        b = Cpt(EpicsMotor, ":mtr2")
        c = Cpt(EpicsMotor, ":mtr3")

    bundle = Bundle("sim", name="bundle")

    assert bundle.hints["fields"] == ["bundle_{}".format(k) for k in "abc"]

    # Test old-style attributes.
    assert set(bundle.read_attrs) == set(
        list("abc")
        + [".".join([p, c]) for p in "abc" for c in ["user_readback", "user_setpoint"]]
    )
    assert set(bundle.configuration_attrs) == set(
        list("abc")
        + [
            ".".join([p, c])
            for p in "abc"
            for c in [
                "user_offset",
                "user_offset_dir",
                "velocity",
                "acceleration",
                "motor_egu",
            ]
        ]
    )
