#!/usr/bin/env python2.7
'''
A simple test for :class:`PVPositioner`
'''

import time
import epics

import config
from ophyd.controls import PVPositioner


def test():
    def callback(sub_type=None, timestamp=None, value=None, **kwargs):
        logger.info('[callback] [%s] (type=%s) value=%s' % (timestamp, sub_type, value))

    def done_moving(**kwargs):
        logger.info('Done moving %s' % (kwargs, ))

    loggers = ('ophyd.controls.signal',
               'ophyd.controls.positioner',
               'ophyd.session',
               )

    config.setup_loggers(loggers)
    logger = config.logger

    fm = config.fake_motors[0]

    # ensure we start at 0 for this simple test
    epics.caput(fm['setpoint'], 0)
    epics.caput(fm['actuate'], 1)
    time.sleep(2)

    pos = PVPositioner(fm['setpoint'],
                       readback=fm['readback'],
                       act=fm['actuate'], act_val=1,
                       stop=fm['stop'], stop_val=1,
                       done=fm['moving'], done_val=1,
                       put_complete=False,
                       )

    pos.subscribe(callback, event_type=pos.SUB_DONE)

    pos.subscribe(callback, event_type=pos.SUB_READBACK)

    logger.info('---- test #1 ----')
    logger.info('--> move to 1')
    pos.move(1)
    logger.info('--> move to 0')
    pos.move(0)

    logger.info('---- test #2 ----')
    logger.info('--> move to 1')
    pos.move(1, wait=False)
    time.sleep(0.5)
    logger.info('--> stop')
    pos.stop()
    logger.info('--> sleep')
    time.sleep(1)
    logger.info('--> move to 0')
    pos.move(0, wait=False, moved_cb=done_moving)
    time.sleep(2)
    # m2.move(1)


if __name__ == '__main__':
    test()
