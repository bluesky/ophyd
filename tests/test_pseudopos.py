

import time
import logging
import unittest
from copy import copy

import epics
from ophyd import (PseudoPositioner, PseudoSingle, EpicsMotor)
from ophyd import (Component as C)


logger = logging.getLogger(__name__)


def setUpModule():
    pass


def tearDownModule():
    if __name__ == '__main__':
        epics.ca.destroy_context()

    logger.debug('Cleaning up')


motor_recs = ['XF:31IDA-OP{Tbl-Ax:X1}Mtr',
              'XF:31IDA-OP{Tbl-Ax:X2}Mtr',
              'XF:31IDA-OP{Tbl-Ax:X3}Mtr',
              'XF:31IDA-OP{Tbl-Ax:X4}Mtr',
              'XF:31IDA-OP{Tbl-Ax:X5}Mtr',
              'XF:31IDA-OP{Tbl-Ax:X6}Mtr',
              ]


class Pseudo3x3(PseudoPositioner):
    pseudo1 = C(PseudoSingle, '', limits=(-10, 10))
    pseudo2 = C(PseudoSingle, '', limits=(-10, 10))
    pseudo3 = C(PseudoSingle, '', limits=(-10, 10))
    real1 = C(EpicsMotor, motor_recs[0])
    real2 = C(EpicsMotor, motor_recs[1])
    real3 = C(EpicsMotor, motor_recs[2])

    def forward(self, pseudo_pos):
        pseudo_pos = self.PseudoPosition(*pseudo_pos)
        logger.debug('forward %s', pseudo_pos)
        return self.RealPosition(real1=-pseudo_pos.pseudo1,
                                 real2=-pseudo_pos.pseudo2,
                                 real3=-pseudo_pos.pseudo3)

    def inverse(self, real_pos):
        real_pos = self.RealPosition(*real_pos)
        logger.debug('inverse %s', real_pos)
        return self.PseudoPosition(pseudo1=real_pos.real1,
                                   pseudo2=real_pos.real2,
                                   pseudo3=real_pos.real3)


class Pseudo1x3(PseudoPositioner):
    pseudo1 = C(PseudoSingle, '', limits=(-10, 10))
    real1 = C(EpicsMotor, motor_recs[0])
    real2 = C(EpicsMotor, motor_recs[1])
    real3 = C(EpicsMotor, motor_recs[2])

    def forward(self, pseudo_pos):
        pseudo_pos = self.PseudoPosition(*pseudo_pos)
        logger.debug('forward %s', pseudo_pos)
        return self.RealPosition(real1=-pseudo_pos.pseudo1,
                                 real2=-pseudo_pos.pseudo1,
                                 real3=-pseudo_pos.pseudo1)

    def inverse(self, real_pos):
        real_pos = self.RealPosition(*real_pos)
        logger.debug('inverse %s', real_pos)
        return self.PseudoPosition(pseudo1=-real_pos.real1)


class PseudoPosTests(unittest.TestCase):
    def test_onlypseudo(self):
        # can't instantiate it on its own
        self.assertRaises(TypeError, PseudoPositioner, 'prefix')

    def test_multi_sequential(self):
        def done(**kwargs):
            logger.debug('** Finished moving (%s)', kwargs)

        pseudo = Pseudo3x3('', name='mypseudo', concurrent=False)
        pseudo.wait_for_connection()

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

    def test_multi_concurrent(self):
        def done(**kwargs):
            logger.debug('** Finished moving (%s)', kwargs)

        pseudo = Pseudo3x3('', name='mypseudo', concurrent=True)
        pseudo.wait_for_connection()
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
        while not ret.done:
            logger.info('Pos=%s %s (err=%s)', pseudo.position, ret, ret.error)
            time.sleep(0.1)

        logger.info('Single pseudo axis: %s', pseudo1)

        pseudo1.move(0, wait=True)

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
