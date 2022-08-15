import logging
import operator
import time
from copy import copy

import numpy as np
import pytest

from ophyd import Component as C
from ophyd.epics_motor import EpicsMotor
from ophyd.pseudopos import PseudoPositioner, PseudoSingle
from ophyd.utils import ExceptionBundle

logger = logging.getLogger(__name__)


def setUpModule():
    logging.getLogger("ophyd.pseudopos").setLevel(logging.DEBUG)


def tearDownModule():

    logger.debug("Cleaning up")
    logging.getLogger("ophyd.pseudopos").setLevel(logging.INFO)


motor_recs = [
    "XF:31IDA-OP{Tbl-Ax:X1}Mtr",
    "XF:31IDA-OP{Tbl-Ax:X2}Mtr",
    "XF:31IDA-OP{Tbl-Ax:X3}Mtr",
    "XF:31IDA-OP{Tbl-Ax:X4}Mtr",
    "XF:31IDA-OP{Tbl-Ax:X5}Mtr",
    "XF:31IDA-OP{Tbl-Ax:X6}Mtr",
]


class Pseudo3x3(PseudoPositioner):
    pseudo1 = C(PseudoSingle, "", limits=(-10, 10), egu="a")
    pseudo2 = C(PseudoSingle, "", limits=(-10, 10), egu="b")
    pseudo3 = C(PseudoSingle, "", limits=None, egu="c")
    real1 = C(EpicsMotor, motor_recs[0])
    real2 = C(EpicsMotor, motor_recs[1])
    real3 = C(EpicsMotor, motor_recs[2])

    def forward(self, pseudo_pos):
        pseudo_pos = self.PseudoPosition(*pseudo_pos)
        # logger.debug('forward %s', pseudo_pos)
        return self.RealPosition(
            real1=-pseudo_pos.pseudo1,
            real2=-pseudo_pos.pseudo2,
            real3=-pseudo_pos.pseudo3,
        )

    def inverse(self, real_pos):
        real_pos = self.RealPosition(*real_pos)
        # logger.debug('inverse %s', real_pos)
        return self.PseudoPosition(
            pseudo1=real_pos.real1, pseudo2=real_pos.real2, pseudo3=real_pos.real3
        )


class Pseudo1x3(PseudoPositioner):
    pseudo1 = C(PseudoSingle, limits=(-10, 10))
    real1 = C(EpicsMotor, motor_recs[0])
    real2 = C(EpicsMotor, motor_recs[1])
    real3 = C(EpicsMotor, motor_recs[2])

    def forward(self, pseudo_pos):
        pseudo_pos = self.PseudoPosition(*pseudo_pos)
        # logger.debug('forward %s', pseudo_pos)
        return self.RealPosition(
            real1=-pseudo_pos.pseudo1,
            real2=-pseudo_pos.pseudo1,
            real3=-pseudo_pos.pseudo1,
        )

    def inverse(self, real_pos):
        real_pos = self.RealPosition(*real_pos)
        # logger.debug('inverse %s', real_pos)
        return self.PseudoPosition(pseudo1=-real_pos.real1)


class FaultyStopperEpicsMotor(EpicsMotor):
    def stop(self, *, success=False):
        raise RuntimeError("Expected exception")


class FaultyPseudo1x3(Pseudo1x3):
    real1 = C(FaultyStopperEpicsMotor, motor_recs[0])


def test_onlypseudo():
    # can't instantiate it on its own
    with pytest.raises(TypeError):
        PseudoPositioner("prefix")


def test_position_wrapper():
    pseudo = Pseudo3x3("", name="mypseudo", concurrent=False)

    test_pos = pseudo.PseudoPosition(pseudo1=1, pseudo2=2, pseudo3=3)
    extra_kw = dict(a=3, b=4, c=6)

    # positional arguments
    assert pseudo.to_pseudo_tuple(1, 2, 3, **extra_kw) == (test_pos, extra_kw)
    # sequence
    assert pseudo.to_pseudo_tuple((1, 2, 3), **extra_kw) == (test_pos, extra_kw)
    # correct type
    assert pseudo.to_pseudo_tuple(test_pos, **extra_kw) == (test_pos, extra_kw)
    # kwargs
    assert pseudo.to_pseudo_tuple(pseudo1=1, pseudo2=2, pseudo3=3, **extra_kw) == (
        test_pos,
        extra_kw,
    )

    # too many positional arguments
    with pytest.raises(ValueError):
        pseudo.to_pseudo_tuple(1, 2, 3, 4)
    # valid kwargs, but passing in args too
    with pytest.raises(ValueError):
        pseudo.to_pseudo_tuple(1, pseudo1=1, pseudo2=2, pseudo3=3)


@pytest.mark.motorsim
def test_multi_sequential():
    pseudo = Pseudo3x3("", name="mypseudo", concurrent=False)
    pseudo.wait_for_connection()

    assert pseudo.egu == "a, b, c"

    pos2 = pseudo.PseudoPosition(pseudo1=0, pseudo2=0, pseudo3=0)
    pseudo.set(pos2, wait=True)
    time.sleep(1.0)
    pos1 = pseudo.PseudoPosition(pseudo1=0.1, pseudo2=0.2, pseudo3=0.3)
    pseudo.set(pos1, wait=True)

    pseudo.real1.set(0, wait=True)
    pseudo.real2.set(0, wait=True)
    pseudo.real3.set(0, wait=True)

    pseudo.pseudo1.stop()

    pseudo.real3.set(0, wait=True)


@pytest.mark.motorsim
def test_faulty_stopper():
    pseudo = FaultyPseudo1x3("", name="mypseudo", concurrent=False)
    pseudo.wait_for_connection()

    with pytest.raises(ExceptionBundle):
        # smoke-testing for coverage
        pseudo.pseudo1.stop()


def test_limits():
    pseudo = Pseudo3x3("", name="mypseudo", concurrent=True)
    assert pseudo.limits == ((-10, 10), (-10, 10), (0, 0))
    assert pseudo.low_limit == (-10, -10, 0)
    assert pseudo.high_limit == (10, 10, 0)


@pytest.mark.motorsim
def test_read_describe():
    pseudo = Pseudo3x3("", name="mypseudo", concurrent=True)
    pseudo.wait_for_connection()
    desc_dict = pseudo.describe()
    desc_keys = [
        "source",
        "upper_ctrl_limit",
        "lower_ctrl_limit",
        "shape",
        "dtype",
        "units",
    ]

    for key in desc_keys:
        assert key in desc_dict["mypseudo_pseudo3"]

    read_dict = pseudo.read()
    read_keys = ["value", "timestamp"]
    for key in read_keys:
        assert key in read_dict["mypseudo_pseudo3"]

    assert pseudo.read().keys() == pseudo.describe().keys()


@pytest.mark.motorsim
def test_multi_concurrent():
    def done(status, **kwargs):
        logger.debug("** Finished moving (%s, %s)", status, kwargs)

    pseudo = Pseudo3x3(
        "", name="mypseudo", concurrent=True, settle_time=0.1, timeout=25.0
    )
    assert pseudo.sequential is False
    assert pseudo.concurrent is True
    assert pseudo.settle_time == 0.1
    assert pseudo.timeout == 25.0
    pseudo.wait_for_connection()
    assert pseudo.connected
    assert tuple(pseudo.pseudo_positioners) == (
        pseudo.pseudo1,
        pseudo.pseudo2,
        pseudo.pseudo3,
    )
    assert tuple(pseudo.real_positioners) == (pseudo.real1, pseudo.real2, pseudo.real3)

    logger.info("Move to (.2, .2, .2), which is (-.2, -.2, -.2) for real " "motors")
    pseudo.set(pseudo.PseudoPosition(0.2, 0.2, 0.2), wait=True)
    logger.info("Position is: %s (moving=%s)", pseudo.position, pseudo.moving)
    pseudo.check_value((2, 2, 2))
    pseudo.check_value(pseudo.PseudoPosition(2, 2, 2))
    try:
        pseudo.check_value((2, 2, 2, 3))
    except ValueError as ex:
        logger.info("Check value failed, as expected (%s)", ex)
    real1 = pseudo.real1
    pseudo1 = pseudo.pseudo1
    try:
        pseudo.check_value((real1.high_limit + 1, 2, 2))
    except ValueError as ex:
        logger.info("Check value failed, as expected (%s)", ex)

    ret = pseudo.set((2, 2, 2), wait=False, moved_cb=done)
    assert ret.settle_time == 0.1
    count = 0
    while not ret.done:
        logger.info("Pos=%s %s (err=%s)", pseudo.position, ret, ret.error)
        count += 1
        if count > 1000:
            raise Exception
        time.sleep(0.1)
    logger.info("Single pseudo axis: %s", pseudo1)

    pseudo1.set(0, wait=True, timeout=5)
    assert pseudo1.target == 0
    pseudo1.sync()
    assert pseudo1.target == pseudo1.position
    # coverage
    pseudo1._started_moving

    try:
        pseudo1.check_value(real1.high_limit + 1)
    except ValueError as ex:
        logger.info("Check value for single failed, as expected (%s)", ex)

    logger.info("Move pseudo1 to 0, position=%s", pseudo.position)
    logger.info("pseudo1 = %s", pseudo1.position)

    def single_sub(**kwargs):
        # logger.info('Single sub: %s', kwargs)
        pass

    pseudo1.subscribe(single_sub, pseudo1.SUB_READBACK)
    ret = pseudo1.set(1, wait=False)
    assert pseudo.timeout == ret.timeout
    count = 0
    while not ret.done:
        logger.info(
            "pseudo1.pos=%s Pos=%s %s (err=%s)",
            pseudo1.position,
            pseudo.position,
            ret,
            ret.error,
        )
        count += 1
        if count > 20:
            raise Exception
        time.sleep(0.1)

    logger.info(
        "pseudo1.pos=%s Pos=%s %s (err=%s)",
        pseudo1.position,
        pseudo.position,
        ret,
        ret.error,
    )
    copy(pseudo)
    pseudo.read()
    pseudo.describe()
    pseudo.read_configuration()
    pseudo.describe_configuration()
    repr(pseudo)
    str(pseudo)
    pseudo.pseudo1.read()
    pseudo.pseudo1.describe()
    pseudo.pseudo1.read_configuration()
    pseudo.pseudo1.describe_configuration()


@pytest.mark.motorsim
def test_single_pseudo():
    logger.info("------- Sequential, single pseudo positioner")
    pos = Pseudo1x3("", name="mypseudo", concurrent=False)
    pos.wait_for_connection()
    reals = pos._real

    logger.info("Move to .2, which is (-.2, -.2, -.2) for real motors")
    pos.set((0.2,), wait=True)
    logger.info("Position is: %s (moving=%s)", pos.position, pos.moving)
    logger.info("Real positions: %s", [real.position for real in reals])

    logger.info("Move to -.2, which is (.2, .2, .2) for real motors")
    pos.set((-0.2,), wait=True)
    logger.info("Position is: %s (moving=%s)", pos.position, pos.moving)
    logger.info("Real positions: %s", [real.position for real in reals])

    copy(pos)
    pos.read()
    pos.describe()
    repr(pos)
    str(pos)


@pytest.mark.parametrize(
    "inpargs,inpkwargs,expected_position,expected_kwargs",
    [
        ((1, 2, 3), {}, (1, 2, 3), {}),
        ((1, 2), {}, (1, 2, -3), {}),
        ((1,), {}, (1, -2, -3), {}),
        (((1, 2, 3),), {}, (1, 2, 3), {}),
        (([1, 2],), {}, (1, 2, -3), {}),
        (((1,),), {}, (1, -2, -3), {}),
        ((), {"pseudo1": 1, "pseudo2": 2, "pseudo3": 3}, (1, 2, 3), {}),
        ((), {"pseudo1": 1, "pseudo2": 2}, (1, 2, -3), {}),
        ((), {"pseudo1": 1}, (1, -2, -3), {}),
        ((), {"pseudo1": 1, "wait": True}, (1, -2, -3), {"wait": True}),
        (({"pseudo1": 1, "pseudo2": 2, "pseudo3": 3},), {}, (1, 2, 3), {}),
        (({"pseudo1": 1, "pseudo2": 2},), {}, (1, 2, -3), {}),
        (({"pseudo1": 1},), {}, (1, -2, -3), {}),
        (
            ({"pseudo1": 1, "wait": True},),
            {"timeout": None},
            (1, -2, -3),
            {"wait": True, "timeout": None},
        ),
        ((1, 2, 3), {"timeout": 1}, (1, 2, 3), {"timeout": 1}),
        (((1, 2, 3),), {"timeout": 1}, (1, 2, 3), {"timeout": 1}),
    ],
)
def test_pseudo_position_input_3x3(
    hw, inpargs, inpkwargs, expected_position, expected_kwargs
):
    pseudo3x3 = hw.pseudo3x3
    pseudo3x3.real1.set(1)
    pseudo3x3.real2.set(2)
    pseudo3x3.real3.set(3)

    out, extra_kwargs = pseudo3x3.to_pseudo_tuple(*inpargs, **inpkwargs)
    assert out == pseudo3x3.PseudoPosition(*expected_position)
    assert extra_kwargs == expected_kwargs

    pseudo3x3.set(*inpargs, **inpkwargs)
    assert pseudo3x3.position == pseudo3x3.PseudoPosition(*expected_position)


@pytest.mark.parametrize(
    "inpargs,inpkwargs",
    [
        ((1, 2, 3, 5), {}),
        ((1, 2, 3), {"pseudo1": 1}),
        ((1, 2, 3), {"pseudo2": 1}),
        ((1,), {"pseudo2": 1, "pseudo3": 1}),
        ((1, 2), {"pseudo3": 1}),
    ],
)
def test_pseudo_position_fail_3x3(hw, inpargs, inpkwargs):
    pseudo3x3 = hw.pseudo3x3
    with pytest.raises(ValueError):
        pseudo3x3.to_pseudo_tuple(*inpargs, **inpkwargs)


@pytest.mark.parametrize(
    "inpargs,inpkwargs,expected_position,expected_kwargs",
    [
        ((1, 2, 3), {}, (1, 2, 3), {}),
        ((1, 2), {}, (1, 2, 3), {}),
        ((1,), {}, (1, 2, 3), {}),
        (((1, 2, 3),), {}, (1, 2, 3), {}),
        (([1, 2],), {}, (1, 2, 3), {}),
        (((1,),), {}, (1, 2, 3), {}),
        ((), {"real1": 1, "real2": 2, "real3": 3}, (1, 2, 3), {}),
        ((), {"real1": 1, "real2": 2}, (1, 2, 3), {}),
        ((), {"real1": 1}, (1, 2, 3), {}),
        ((), {"real1": 1, "foo": "bar"}, (1, 2, 3), {"foo": "bar"}),
        (({"real1": 1, "real2": 2, "real3": 3},), {}, (1, 2, 3), {}),
        (({"real1": 1, "real2": 2},), {}, (1, 2, 3), {}),
        (({"real1": 1},), {}, (1, 2, 3), {}),
        (
            ({"real1": 1, "foo": "bar"},),
            {"baz": "buz"},
            (1, 2, 3),
            {"foo": "bar", "baz": "buz"},
        ),
        ((1, 2, 3), {"foo": "bar"}, (1, 2, 3), {"foo": "bar"}),
    ],
)
def test_real_position_input_3x3(
    hw, inpargs, inpkwargs, expected_position, expected_kwargs
):
    pseudo3x3 = hw.pseudo3x3
    pseudo3x3.real1.set(1)
    pseudo3x3.real2.set(2)
    pseudo3x3.real3.set(3)

    out, extra_kwargs = pseudo3x3.to_real_tuple(*inpargs, **inpkwargs)
    assert out == pseudo3x3.RealPosition(*expected_position)
    assert extra_kwargs == expected_kwargs


@pytest.mark.parametrize(
    "inpargs,inpkwargs",
    [
        ((1, 2, 3, 5), {}),
        ((1, 2, 3), {"real1": 1}),
        ((1, 2, 3), {"real2": 1}),
        ((1,), {"real2": 1, "real3": 1}),
        ((1, 2), {"real3": 1}),
        (({"real3": 1, "foo": "bar"},), {"foo": "bizz"}),
        ((), {}),
    ],
)
def test_real_position_fail_3x3(hw, inpargs, inpkwargs):
    pseudo3x3 = hw.pseudo3x3
    with pytest.raises(ValueError):
        pseudo3x3.to_real_tuple(*inpargs, **inpkwargs)


def test_single_pseudo_with_sim(hw):
    logger.info("------- Sequential, single pseudo positioner")
    pos = hw.pseudo1x3

    reals = pos._real

    logger.info("Move to .2, which is (-.2, -.2, -.2) for real motors")
    pos.set((0.2,), wait=True)
    logger.info("Position is: %s (moving=%s)", pos.position, pos.moving)
    logger.info("Real positions: %s", [real.position for real in reals])

    logger.info("Move to -.2, which is (.2, .2, .2) for real motors")
    pos.set((-0.2,), wait=True)
    logger.info("Position is: %s (moving=%s)", pos.position, pos.moving)
    logger.info("Real positions: %s", [real.position for real in reals])

    copy(pos)
    pos.read()
    pos.describe()
    repr(pos)
    str(pos)


@pytest.mark.parametrize("typ", ("to_real_tuple", "to_pseudo_tuple"))
@pytest.mark.parametrize("op", (operator.sub, operator.add))
@pytest.mark.parametrize(
    "a,b",
    [((0, 0, 0), (1, 1, 1)), ((1, 0, 1), (1, 1, 1)), ((9, 0, 0.3), (0.3, 0.1, 0.5))],
)
def test_pseudo_math(hw, a, b, op, typ):
    pos = hw.pseudo3x3
    a, _ = getattr(pos, typ)(a)
    b, _ = getattr(pos, typ)(b)

    # TODO switch to np asserts
    expected = op(np.asarray(a), np.asarray(b))
    assert (np.asarray(op(a, b)) == expected).all()
    assert (np.asarray(op(a, tuple(b))) == expected).all()
    assert (np.asarray(op(a, list(b))) == expected).all()
    assert (np.asarray(op(a, b._asdict())) == expected).all()
    assert (np.asarray(op(a, {})) == a).all()
    assert abs(op(a, b)) == np.sqrt(np.sum(expected**2))


def test_pseudo_hints(hw):
    pos = hw.pseudo3x3

    for j in (1, 2, 3):
        p = getattr(pos, "pseudo{}".format(j))
        assert p.hints["fields"] == [p.readback.name]
        p.readback.name = "aardvark{}".format(j)
        assert p.hints["fields"] == [p.readback.name]

    expected_fields = [
        getattr(pos, "pseudo{}".format(j)).readback.name for j in (1, 2, 3)
    ]
    assert pos.hints["fields"] == expected_fields
