#!/usr/bin/env python2.7
'''
A simple test for :class:`EpicsMotor`
'''

import time

import config
from ophyd.controls import EpicsMotor


def test():
    def callback(sub_type=None, timestamp=None, value=None, **kwargs):
        config.logger.info('[callback] [%s] (type=%s) value=%s' % (timestamp, sub_type, value))

    def done_moving(**kwargs):
        config.logger.info('Done moving %s' % (kwargs, ))

    loggers = ('ophyd.controls.signal',
               'ophyd.controls.positioner',
               'ophyd.session',
               )

    config.setup_loggers(loggers)
    logger = config.logger

    motor_record = config.motor_recs[0]

    m1 = EpicsMotor(motor_record)
    # m2 = EpicsMotor('MLL:bad_record')
    m1.subscribe(callback, event_type=m1.SUB_DONE)

    m1.user_readback.subscribe(callback)
    # print(m1.user_readback.read())
    # print(m1.read())

    logger.info('--> move to 1')
    m1.move(1)
    time.sleep(1)
    logger.info('--> move to 0')
    m1.move(0, moved_cb=done_moving)

    # m2.move(1)
    # time.sleep(1)


if __name__ == '__main__':
    test()
