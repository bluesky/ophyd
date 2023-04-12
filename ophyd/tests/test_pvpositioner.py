import logging
import time
from copy import copy

import pytest

from ophyd import Component as Cpt
from ophyd import (
    EpicsSignal,
    EpicsSignalRO,
    Kind,
    PVPositioner,
    PVPositionerDone,
    PVPositionerIsClose,
    PVPositionerPC,
    get_cl,
)
from ophyd.utils.epics_pvs import _wait_for_value

logger = logging.getLogger(__name__)


def setUpModule():
    logging.getLogger("ophyd.pv_positioner").setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)


def tearDownModule():
    logger.debug("Cleaning up")
    logging.getLogger("ophyd.pv_positioner").setLevel(logging.INFO)
    logger.setLevel(logging.INFO)


def test_not_subclassed():
    # can't instantiate it on its own
    with pytest.raises(TypeError):
        PVPositioner("prefix")

    with pytest.raises(TypeError):
        PVPositionerPC("prefix")


def test_no_setpoint_or_readback():
    class MyPositioner(PVPositioner):
        pass

    with pytest.raises(ValueError):
        MyPositioner()


def test_setpoint_but_no_done():
    class MyPositioner(PVPositioner):
        setpoint = Cpt(EpicsSignal, ".VAL")

    with pytest.raises(ValueError):
        MyPositioner()


@pytest.mark.motorsim
def test_pvpos(motor):
    class MyPositioner(PVPositioner):
        """Setpoint, readback, done, stop. No put completion"""

        setpoint = Cpt(EpicsSignal, ".VAL")
        readback = Cpt(EpicsSignalRO, ".RBV")
        done = Cpt(EpicsSignalRO, ".MOVN")
        stop_signal = Cpt(EpicsSignal, ".STOP")

        stop_value = 1
        done_value = 0

    m = MyPositioner(motor.prefix, name="pos_no_put_compl")
    m.wait_for_connection()

    m.read()

    motor.move(0.1, wait=True)
    time.sleep(1)
    assert m.position == pytest.approx(0.1)

    m.stop()
    m.limits

    repr(m)
    str(m)

    mc = copy(m)
    assert mc.describe() == m.describe()

    m.read()


@pytest.mark.motorsim
def test_put_complete_setpoint_only(motor):
    logger.info("--> PV Positioner, using put completion and a DONE pv")

    class MyPositioner(PVPositionerPC):
        """Setpoint only"""

        setpoint = Cpt(EpicsSignal, ".VAL")

    pos = MyPositioner(motor.prefix, name="pc_setpoint_done")
    print(pos.describe())
    pos.wait_for_connection()

    pos.read()
    high_lim = pos.setpoint.high_limit
    try:
        pos.check_value(high_lim + 1)
    except ValueError as ex:
        logger.info("Check value for single failed, as expected (%s)", ex)
    else:
        raise ValueError("check_value should have failed")

    stat = pos.move(1, wait=False)
    logger.info("--> post-move request, moving=%s", pos.moving)

    while not stat.done:
        logger.info("--> moving... %s error=%s", stat, stat.error)
        time.sleep(0.1)

    pos.move(-1, wait=True)
    assert not pos.moving


@pytest.mark.motorsim
def test_put_complete_setpoint_readback_done(motor):
    class MyPositioner(PVPositionerPC):
        """Setpoint, readback, done, stop. Put completion"""

        setpoint = Cpt(EpicsSignal, ".VAL")
        readback = Cpt(EpicsSignalRO, ".RBV")
        done = Cpt(EpicsSignalRO, ".MOVN")
        done_value = 0

    pos = MyPositioner(
        motor.prefix, name="pos_no_put_compl", settle_time=0.1, timeout=25.0
    )
    print(pos.describe())
    pos.wait_for_connection()

    assert pos.settle_time == 0.1
    assert pos.timeout == 25.0
    pos.read()
    high_lim = pos.setpoint.high_limit
    try:
        pos.check_value(high_lim + 1)
    except ValueError as ex:
        logger.info("Check value for single failed, as expected (%s)", ex)
    else:
        raise ValueError("check_value should have failed")

    stat = pos.move(1, wait=False)
    assert stat.timeout == pos.timeout
    logger.info("--> post-move request, moving=%s", pos.moving)

    while not stat.done:
        logger.info("--> moving... %s error=%s", stat, stat.error)
        time.sleep(0.1)

    pos.move(-1, wait=True)
    assert not pos.moving


@pytest.mark.motorsim
def test_put_complete_setpoint_readback(motor):
    class MyPositioner(PVPositionerPC):
        """Setpoint, readback, put completion. No done pv."""

        setpoint = Cpt(EpicsSignal, ".VAL")
        readback = Cpt(EpicsSignalRO, ".RBV")

    pos = MyPositioner(motor.prefix, name="pos_put_compl")
    print(pos.describe())
    pos.wait_for_connection()

    stat = pos.move(2, wait=False)
    logger.info("--> post-move request, moving=%s", pos.moving)

    while not stat.done:
        logger.info("--> moving... %s", stat)
        time.sleep(0.1)

    pos.move(0, wait=True)
    logger.info("--> synchronous move request, moving=%s", pos.moving)

    time.sleep(0.1)
    print("read", pos.read())
    assert not pos.moving


def test_pvpositioner_with_fake_motor(fake_motor_ioc):
    def callback(sub_type=None, timestamp=None, value=None, **kwargs):
        logger.info("[callback] [%s] (type=%s) value=%s", timestamp, sub_type, value)

    def done_moving(value=0.0, **kwargs):
        logger.info("Done moving %s", kwargs)

    cl = get_cl()
    # ensure we start at 0 for this simple test
    cl.caput(fake_motor_ioc.pvs["setpoint"], 0)
    cl.caput(fake_motor_ioc.pvs["actuate"], 1)
    time.sleep(0.5)

    class MyPositioner(PVPositioner):
        """Setpoint, readback, no put completion. No done pv."""

        setpoint = Cpt(EpicsSignal, fake_motor_ioc.pvs["setpoint"])
        readback = Cpt(EpicsSignalRO, fake_motor_ioc.pvs["readback"])
        actuate = Cpt(EpicsSignal, fake_motor_ioc.pvs["actuate"])
        stop_signal = Cpt(EpicsSignal, fake_motor_ioc.pvs["stop"])
        done = Cpt(EpicsSignal, fake_motor_ioc.pvs["moving"])

        actuate_value = 1
        stop_value = 1
        done_value = 0

    pos = MyPositioner("", name="pv_pos_fake_mtr")
    print("fake mtr", pos.describe())
    pos.wait_for_connection()

    pos.subscribe(callback, event_type=pos.SUB_DONE)
    pos.subscribe(callback, event_type=pos.SUB_READBACK)

    logger.info("---- test #1 ----")
    logger.info("--> move to 1")
    pos.move(1, timeout=5)
    assert pos.position == 1
    logger.info("--> move to 0")
    pos.move(0, timeout=5)
    assert pos.position == 0

    logger.info("---- test #2 ----")
    logger.info("--> move to 1")
    pos.move(1, wait=False)
    time.sleep(0.5)
    logger.info("--> stop")
    pos.stop()
    logger.info("--> sleep")
    time.sleep(1)
    logger.info("--> move to 0")
    pos.move(0, wait=False, moved_cb=done_moving)
    logger.info("--> post-move request, moving=%s", pos.moving)
    time.sleep(2)

    pos.read()
    repr(pos)
    str(pos)


def test_hints(fake_motor_ioc):
    class MyPositioner(PVPositioner):
        """Setpoint, readback, no put completion. No done pv."""

        setpoint = Cpt(EpicsSignal, fake_motor_ioc.pvs["setpoint"])
        readback = Cpt(EpicsSignalRO, fake_motor_ioc.pvs["readback"])
        actuate = Cpt(EpicsSignal, fake_motor_ioc.pvs["actuate"])
        stop_signal = Cpt(EpicsSignal, fake_motor_ioc.pvs["stop"])
        done = Cpt(EpicsSignal, fake_motor_ioc.pvs["moving"])

        actuate_value = 1
        stop_value = 1
        done_value = 1

    motor = MyPositioner("", name="pv_pos_fake_mtr")

    desc = motor.describe()
    f_hints = motor.hints["fields"]
    assert len(f_hints) > 0
    for k in f_hints:
        assert k in desc

    motor.readback.kind = Kind.hinted
    assert motor.hints == {"fields": ["pv_pos_fake_mtr_readback"]}

    assert motor.hints["fields"] == f_hints


def test_pv_positioner_is_close(signal_test_ioc):
    class MyPositioner(PVPositionerIsClose):
        setpoint = Cpt(EpicsSignal, signal_test_ioc.pvs["read_write"])
        readback = Cpt(EpicsSignal, signal_test_ioc.pvs["pair_set"])

        atol = 0.1

    motor = MyPositioner("", name="pv_pos_is_close_fake_motor")
    setpoint_status = motor.setpoint.set(0)
    readback_status = motor.readback.set(0)
    setpoint_status.wait(timeout=1)
    readback_status.wait(timeout=1)
    goal = motor.position + 10
    status = motor.set(goal)
    _wait_for_value(motor.setpoint, goal, atol=0.01, timeout=1)
    _wait_for_value(motor.done, 0, timeout=1)
    with pytest.raises(TimeoutError):
        _wait_for_value(motor.done, 1, timeout=1)
    motor.readback.put(goal / 2)
    with pytest.raises(TimeoutError):
        _wait_for_value(motor.done, 1, timeout=1)
    motor.readback.put(goal + motor.atol / 2)
    status.wait(timeout=1)
    assert status.done
    assert status.success
    assert motor.done.get() == 1


def test_pv_positioner_done(signal_test_ioc):
    # Catch done going to 0 and back to 1
    motor = PVPositionerDone(
        signal_test_ioc.pvs["read_write"], name="pv_pos_done_fake_motor"
    )
    motor.setpoint.set(0).wait(timeout=1)
    done_values = []

    def accumulate_done_values(value, **kwargs):
        done_values.append(value)

    motor.done.subscribe(accumulate_done_values, run=False)
    motor.set(motor.position + 10).wait()
    assert done_values == [0, 1]
