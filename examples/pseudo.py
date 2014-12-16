#!/usr/bin/env python2.7
'''
A simple test for :class:`PseudoPositioner`
'''
from __future__ import print_function

import time

import config
from ophyd.controls import (EpicsMotor, PseudoPositioner)


logger = config.logger


def multi_pseudo():
    def calc_fwd(pseudo0=0.0, pseudo1=0.0, pseudo2=0.0):
        return [-pseudo0, -pseudo1, -pseudo2]

    def calc_rev(real0=0.0, real1=0.0, real2=0.0):
        return [-real0, -real1, -real2]

    def done(**kwargs):
        print('** Finished moving (%s)' % (kwargs, ))

    real0 = EpicsMotor(config.motor_recs[0], name='real0')
    real1 = EpicsMotor(config.motor_recs[1], name='real1')
    real2 = EpicsMotor(config.motor_recs[2], name='real2')

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
    ret = pos.move((2, 2, 2), wait=False, moved_cb=done)
    while not ret.done:
        logger.info('Pos=%s %s (err=%s)' % (pos.position, ret, ret.error))
        time.sleep(0.1)

    pseudo0 = pos['pseudo0']
    pseudo0.move(0, wait=True)
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


def single_pseudo():
    def calc_fwd(pseudo=0.0):
        return [-pseudo]

    def calc_rev(real0=0.0, real1=0.0, real2=0.0):
        return [-real0, -real1, -real2]

    def done(**kwargs):
        print('** Finished moving (%s)' % (kwargs, ))

    real0 = EpicsMotor(config.motor_recs[0], name='real0')
    real1 = EpicsMotor(config.motor_recs[1], name='real1')
    real2 = EpicsMotor(config.motor_recs[2], name='real2')

    logger.info('------- Sequential, single pseudo positioner')
    pos = PseudoPositioner('seq',
                           [real0, real1, real2],
                           forward=calc_fwd, reverse=calc_rev,
                           concurrent=False
                           )

    logger.info('Move to .2, which is (-.2, -.2, -.2) for real motors')
    pos.move(.2, wait=True)
    logger.info('Position is: %s (moving=%s)' % (pos.position, pos.moving))


if __name__ == '__main__':
    # multi_pseudo()
    single_pseudo()
