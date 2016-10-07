import time
import logging
import unittest
import pytest

from copy import copy

import epics
from ophyd import (PseudoPositioner, PseudoSingle, EpicsMotor)
from ophyd import (Component as C)
from ophyd.utils import ExceptionBundle


logger = logging.getLogger(__name__)


def setUpModule():
    logging.getLogger('ophyd.pseudopos').setLevel(logging.DEBUG)


def tearDownModule():
    if __name__ == '__main__':
        epics.ca.destroy_context()

    logger.debug('Cleaning up')
    logging.getLogger('ophyd.pseudopos').setLevel(logging.INFO)


motor_recs = ['XF:31IDA-OP{Tbl-Ax:X1}Mtr',
              'XF:31IDA-OP{Tbl-Ax:X2}Mtr',
              'XF:31IDA-OP{Tbl-Ax:X3}Mtr',
              'XF:31IDA-OP{Tbl-Ax:X4}Mtr',
              'XF:31IDA-OP{Tbl-Ax:X5}Mtr',
              'XF:31IDA-OP{Tbl-Ax:X6}Mtr',
              ]


class Pseudo3x3(PseudoPositioner):
    pseudo1 = C(PseudoSingle, '', limits=(-10, 10), egu='a')
    pseudo2 = C(PseudoSingle, '', limits=(-10, 10), egu='b')
    pseudo3 = C(PseudoSingle, '', limits=None, egu='c')
    real1 = C(EpicsMotor, motor_recs[0])
    real2 = C(EpicsMotor, motor_recs[1])
    real3 = C(EpicsMotor, motor_recs[2])

    def forward(self, pseudo_pos):
        pseudo_pos = self.PseudoPosition(*pseudo_pos)
        # logger.debug('forward %s', pseudo_pos)
        return self.RealPosition(real1=-pseudo_pos.pseudo1,
                                 real2=-pseudo_pos.pseudo2,
                                 real3=-pseudo_pos.pseudo3)

    def inverse(self, real_pos):
        real_pos = self.RealPosition(*real_pos)
        # logger.debug('inverse %s', real_pos)
        return self.PseudoPosition(pseudo1=real_pos.real1,
                                   pseudo2=real_pos.real2,
                                   pseudo3=real_pos.real3)


class Pseudo1x3(PseudoPositioner):
    pseudo1 = C(PseudoSingle, limits=(-10, 10))
    real1 = C(EpicsMotor, motor_recs[0])
    real2 = C(EpicsMotor, motor_recs[1])
    real3 = C(EpicsMotor, motor_recs[2])

    def forward(self, pseudo_pos):
        pseudo_pos = self.PseudoPosition(*pseudo_pos)
        # logger.debug('forward %s', pseudo_pos)
        return self.RealPosition(real1=-pseudo_pos.pseudo1,
                                 real2=-pseudo_pos.pseudo1,
                                 real3=-pseudo_pos.pseudo1)

    def inverse(self, real_pos):
        real_pos = self.RealPosition(*real_pos)
        # logger.debug('inverse %s', real_pos)
        return self.PseudoPosition(pseudo1=-real_pos.real1)


class FaultyStopperEpicsMotor(EpicsMotor):
    def stop(self, *, success=False):
        raise RuntimeError('Expected exception')


class FaultyPseudo1x3(Pseudo1x3):
    real1 = C(FaultyStopperEpicsMotor, motor_recs[0])


class PseudoPosTests(unittest.TestCase):
    def test_onlypseudo(self):
        # can't instantiate it on its own
        self.assertRaises(TypeError, PseudoPositioner, 'prefix')

    def test_position_wrapper(self):
        pseudo = Pseudo3x3('', name='mypseudo', concurrent=False)

        test_pos = pseudo.PseudoPosition(pseudo1=1, pseudo2=2, pseudo3=3)
        extra_kw = dict(a=3, b=4, c=6)

        # positional arguments
        self.assertEqual(pseudo.to_pseudo_tuple(1, 2, 3, **extra_kw),
                         (test_pos, extra_kw))
        # sequence
        self.assertEqual(pseudo.to_pseudo_tuple((1, 2, 3), **extra_kw),
                         (test_pos, extra_kw))
        # correct type
        self.assertEqual(pseudo.to_pseudo_tuple(test_pos, **extra_kw),
                         (test_pos, extra_kw))
        # kwargs
        self.assertEqual(pseudo.to_pseudo_tuple(pseudo1=1, pseudo2=2,
                                                pseudo3=3, **extra_kw),
                         (test_pos, extra_kw))

        # too many positional arguments
        self.assertRaises(ValueError, pseudo.to_pseudo_tuple, 1, 2, 3, 4)
        # too few positional arguments
        self.assertRaises(ValueError, pseudo.to_pseudo_tuple, 1, 2)
        # too few kwargs
        self.assertRaises(ValueError, pseudo.to_pseudo_tuple, pseudo1=1,
                          pseudo2=2)
        # valid kwargs, but passing in args too
        self.assertRaises(ValueError, pseudo.to_pseudo_tuple, 1, pseudo1=1,
                          pseudo2=2, pseudo3=3)

    def test_multi_sequential(self):
        def done(**kwargs):
            logger.debug('** Finished moving (%s)', kwargs)

        pseudo = Pseudo3x3('', name='mypseudo', concurrent=False)
        pseudo.wait_for_connection()

        self.assertEqual(pseudo.egu, 'a, b, c')

        print('real1', pseudo.real1.prefix)
        print('real2', pseudo.real2.prefix)
        print('real3', pseudo.real3.prefix)

        print('real position is made of', pseudo.RealPosition._fields)
        print('pseudo position is made of', pseudo.PseudoPosition._fields)
        print('current pseudo position', pseudo.position)
        print(repr(pseudo))
        print(str(pseudo))

        pos2 = pseudo.PseudoPosition(pseudo1=0, pseudo2=0, pseudo3=0)
        pseudo.move(pos2, wait=True)
        print('moved to', pseudo.position)
        print('-----------------')
        time.sleep(1.0)
        pos1 = pseudo.PseudoPosition(pseudo1=.1, pseudo2=.2, pseudo3=.3)
        pseudo.move(pos1, wait=True)
        print('moved to', pseudo.position)

        pseudo.real1.move(0, wait=True)
        pseudo.real2.move(0, wait=True)
        pseudo.real3.move(0, wait=True)

        pseudo.pseudo1.stop()

        pseudo.real3.move(0, wait=True)

    def test_faulty_stopper(self):
        pseudo = FaultyPseudo1x3('', name='mypseudo', concurrent=False)
        pseudo.wait_for_connection()

        with pytest.raises(ExceptionBundle):
            # smoke-testing for coverage
            pseudo.pseudo1.stop()

    def test_limits(self):
        pseudo = Pseudo3x3('', name='mypseudo', concurrent=True)
        self.assertEquals(pseudo.limits, ((-10, 10), (-10, 10), (0, 0)))
        self.assertEquals(pseudo.low_limit, (-10, -10, 0))
        self.assertEquals(pseudo.high_limit, (10, 10, 0))

    def test_read_describe(self):
        pseudo = Pseudo3x3('', name='mypseudo', concurrent=True)
        desc_dict = pseudo.describe()
        print(desc_dict)
        desc_keys = ['source', 'upper_ctrl_limit', 'lower_ctrl_limit', 'shape',
                     'dtype', 'units']

        for key in desc_keys:
            self.assertIn(key, desc_dict['mypseudo_pseudo3'])

        read_dict = pseudo.read()
        print(read_dict)
        read_keys = ['value', 'timestamp']
        for key in read_keys:
            self.assertIn(key, read_dict['mypseudo_pseudo3'])

        self.assertEqual(pseudo.read().keys(), pseudo.describe().keys())

    def test_multi_concurrent(self):
        def done(**kwargs):
            logger.debug('** Finished moving (%s)', kwargs)

        pseudo = Pseudo3x3('', name='mypseudo', concurrent=True,
                           settle_time=0.1, timeout=25.0)
        self.assertIs(pseudo.sequential, False)
        self.assertIs(pseudo.concurrent, True)
        self.assertEqual(pseudo.settle_time, 0.1)
        self.assertEqual(pseudo.timeout, 25.0)
        pseudo.wait_for_connection()

        self.assertTrue(pseudo.connected)
        self.assertEqual(tuple(pseudo.pseudo_positioners),
                         (pseudo.pseudo1, pseudo.pseudo2, pseudo.pseudo3))
        self.assertEqual(tuple(pseudo.real_positioners),
                         (pseudo.real1, pseudo.real2, pseudo.real3))

        logger.info('Move to (.2, .2, .2), which is (-.2, -.2, -.2) for real '
                    'motors')
        pseudo.move(pseudo.PseudoPosition(.2, .2, .2), wait=True)
        logger.info('Position is: %s (moving=%s)', pseudo.position,
                    pseudo.moving)

        pseudo.check_value((2, 2, 2))
        pseudo.check_value(pseudo.PseudoPosition(2, 2, 2))
        try:
            pseudo.check_value((2, 2, 2, 3))
        except ValueError as ex:
            logger.info('Check value failed, as expected (%s)', ex)

        real1 = pseudo.real1
        pseudo1 = pseudo.pseudo1

        try:
            pseudo.check_value((real1.high_limit + 1, 2, 2))
        except ValueError as ex:
            logger.info('Check value failed, as expected (%s)', ex)

        ret = pseudo.move((2, 2, 2), wait=False, moved_cb=done)
        self.assertEqual(ret.settle_time, 0.1)
        while not ret.done:
            logger.info('Pos=%s %s (err=%s)', pseudo.position, ret, ret.error)
            time.sleep(0.1)

        logger.info('Single pseudo axis: %s', pseudo1)

        pseudo1.move(0, wait=True)

        self.assertEquals(pseudo1.target, 0)
        pseudo1.sync()
        self.assertEquals(pseudo1.target, pseudo1.position)

        # coverage
        pseudo1._started_moving

        try:
            pseudo1.check_value(real1.high_limit + 1)
        except ValueError as ex:
            logger.info('Check value for single failed, as expected (%s)', ex)

        logger.info('Move pseudo1 to 0, position=%s', pseudo.position)
        logger.info('pseudo1 = %s', pseudo1.position)

        def single_sub(**kwargs):
            # logger.info('Single sub: %s', kwargs)
            pass

        pseudo1.subscribe(single_sub, pseudo1.SUB_READBACK)

        ret = pseudo1.move(1, wait=False)
        self.assertEqual(pseudo.timeout, ret.timeout)
        while not ret.done:
            logger.info('pseudo1.pos=%s Pos=%s %s (err=%s)', pseudo1.position,
                        pseudo.position, ret, ret.error)
            time.sleep(0.1)

        logger.info('pseudo1.pos=%s Pos=%s %s (err=%s)', pseudo1.position,
                    pseudo.position, ret, ret.error)

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

    def test_single_pseudo(self):
        def done(**kwargs):
            logger.debug('** Finished moving (%s)', kwargs)

        logger.info('------- Sequential, single pseudo positioner')
        pos = Pseudo1x3('', name='mypseudo', concurrent=False)

        reals = pos._real

        logger.info('Move to .2, which is (-.2, -.2, -.2) for real motors')
        pos.move((.2, ), wait=True)
        logger.info('Position is: %s (moving=%s)', pos.position, pos.moving)
        logger.info('Real positions: %s', [real.position for real in reals])

        logger.info('Move to -.2, which is (.2, .2, .2) for real motors')
        pos.move((-.2, ), wait=True)
        logger.info('Position is: %s (moving=%s)', pos.position, pos.moving)
        logger.info('Real positions: %s', [real.position for real in reals])

        copy(pos)
        pos.read()
        pos.describe()
        repr(pos)
        str(pos)


from . import main
is_main = (__name__ == '__main__')
main(is_main)
