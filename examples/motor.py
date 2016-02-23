#!/usr/bin/env python2.7
'''A simple test for :class:`EpicsMotor`'''

import time

import config
from ophyd import EpicsMotor
from ophyd.utils.errors import LimitError


def callback(sub_type=None, timestamp=None, value=None, **kwargs):
    logger.info('[callback] [%s] (type=%s) value=%s', timestamp, sub_type, value)

def done_moving(**kwargs):
    logger.info('Done moving %s', kwargs)

logger = config.logger

motor_record = config.motor_recs[0]

m1 = EpicsMotor(motor_record)
m1.wait_for_connection()

m1.subscribe(callback, event_type=m1.SUB_DONE)
m1.subscribe(callback, event_type=m1.SUB_READBACK)

logger.info('---- test #1 ----')
logger.info('--> move to 1')
m1.move(1)
logger.info('--> move to 0')
m1.move(0)
