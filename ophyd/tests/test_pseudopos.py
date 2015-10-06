from __future__ import print_function

import time
import logging
import unittest
from copy import copy

import epics
from ophyd.controls import (PseudoPositioner, EpicsMotor)

reload(epics)

logger = logging.getLogger(__name__)


def setUpModule():
    pass


def tearDownModule():
    if __name__ == '__main__':
        epics.ca.destroy_context()

    logger.debug('Cleaning up')


class PseudoPosTests(unittest.TestCase):
    motor_recs = ['XF:31IDA-OP{Tbl-Ax:X1}Mtr',
                  'XF:31IDA-OP{Tbl-Ax:X2}Mtr',
                  'XF:31IDA-OP{Tbl-Ax:X3}Mtr',
                  'XF:31IDA-OP{Tbl-Ax:X4}Mtr',
                  'XF:31IDA-OP{Tbl-Ax:X5}Mtr',
                  'XF:31IDA-OP{Tbl-Ax:X6}Mtr',
                  ]

    def test_multi_pseudo(self):
        def calc_fwd(pseudo0=0.0, pseudo1=0.0, pseudo2=0.0):
            return [-pseudo0, -pseudo1, -pseudo2]

        def calc_rev(real0=0.0, real1=0.0, real2=0.0):
            return [-real0, -real1, -real2]

        def done(**kwargs):
            logger.debug('** Finished moving (%s)' % (kwargs, ))

        real0 = EpicsMotor(self.motor_recs[0], name='real0')
        real1 = EpicsMotor(self.motor_recs[1], name='real1')
        real2 = EpicsMotor(self.motor_recs[2], name='real2')

        logger.info('------- Sequential pseudo positioner')
        pos = PseudoPositioner('seq',
                               [real0, real1, real2],
                               forward=calc_fwd, reverse=calc_rev,
                               pseudo=['pseudo0', 'pseudo1', 'pseudo2'],
                               concurrent=False
                               )

        logger.info('Move to (.2, .2, .2), which is (-.2, -.2, -.2) for real motors')
        pos.move((.2, .2, .2), wait=True)
        logger.info('Position is: %s (moving=%s)' % (pos.position, pos.moving))

        if 0:
            logger.info('Move to (-.2, -.2, -.2), which is (.2, .2, .2) for real motors')
            pos.move((-.2, -.2, -.2), wait=True, moved_cb=done)

            logger.info('Position is: %s (moving=%s)' % (pos.position, pos.moving))

            # No such thing as a non-blocking move for a sequential
            # pseudo positioner

            # Create another one and give that a try

        pos = PseudoPositioner('conc',
                               [real0, real1, real2],
                               forward=calc_fwd, reverse=calc_rev,
                               pseudo=['pseudo0', 'pseudo1', 'pseudo2'],
                               concurrent=True
                               )

        logger.info('------- concurrent pseudo positioner')
        logger.info('Move to (2, 2, 2), which is (-2, -2, -2) for real motors')

        pos.check_value((2, 2, 2))
        try:
            pos.check_value((2, 2, 2, 3))
        except ValueError as ex:
            logger.info('Check value failed, as expected (%s)' % ex)

        try:
            pos.check_value((real0.high_limit + 1, 2, 2))
        except ValueError as ex:
            logger.info('Check value failed, as expected (%s)' % ex)

        ret = pos.move((2, 2, 2), wait=False, moved_cb=done)
        while not ret.done:
            logger.info('Pos=%s %s (err=%s)' % (pos.position, ret, ret.error))
            time.sleep(0.1)

        pseudo0 = pos['pseudo0']
        logger.info('Single pseudo axis: %s' % pseudo0)

        pseudo0.move(0, wait=True)

        try:
            pseudo0.check_value(real0.high_limit + 1)
        except ValueError as ex:
            logger.info('Check value for single failed, as expected (%s)' % ex)

        logger.info('Move pseudo0 to 0, position=%s' % (pos.position, ))
        logger.info('pseudo0 = %s' % pseudo0.position)

        def single_sub(**kwargs):
            # logger.info('Single sub: %s' % (kwargs, ))
            pass

        pseudo0.subscribe(single_sub, pseudo0.SUB_READBACK)

        ret = pseudo0.move(1, wait=False)
        while not ret.done:
            logger.info('Pseudo0.pos=%s Pos=%s %s (err=%s)' % (pseudo0.position,
                                                               pos.position, ret, ret.error))
            time.sleep(0.1)

        logger.info('Pseudo0.pos=%s Pos=%s %s (err=%s)' % (pseudo0.position,
                                                           pos.position, ret, ret.error))

        # pos['pseudo0'] = 2
        assert('pseudo0' in pos)
        assert('real0' in pos)

        copy(pos)
        pos.report
        pos.read()
        repr(pos)
        str(pos)

    def test_single_pseudo(self):
        def calc_fwd(pseudo=0.0):
            return [-pseudo, -pseudo, -pseudo]

        def calc_rev(real0=0.0, real1=0.0, real2=0.0):
            return -real0

        def done(**kwargs):
            logger.debug('** Finished moving (%s)' % (kwargs, ))

        real0 = EpicsMotor(self.motor_recs[0], name='real0')
        real1 = EpicsMotor(self.motor_recs[1], name='real1')
        real2 = EpicsMotor(self.motor_recs[2], name='real2')

        reals = [real0, real1, real2]

        logger.info('------- Sequential, single pseudo positioner')
        pos = PseudoPositioner('seq',
                               reals,
                               forward=calc_fwd, reverse=calc_rev,
                               concurrent=False
                               )

        logger.info('Move to .2, which is (-.2, -.2, -.2) for real motors')
        pos.move(.2, wait=True)
        logger.info('Position is: %s (moving=%s)' % (pos.position, pos.moving))
        logger.info('Real positions: %s' % ([real.position for real in reals], ))

        logger.info('Move to -.2, which is (.2, .2, .2) for real motors')
        pos.move(-.2, wait=True)
        logger.info('Position is: %s (moving=%s)' % (pos.position, pos.moving))
        logger.info('Real positions: %s' % ([real.position for real in reals], ))

        copy(pos)
        pos.report
        pos.read()
        repr(pos)
        str(pos)

from . import main
is_main = (__name__ == '__main__')
main(is_main)
