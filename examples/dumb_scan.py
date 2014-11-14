#!/usr/bin/env python2.7
'''
A simple, dumb scan test which only uses the basic signals
'''

from __future__ import print_function
import time
import numpy as np

import config
from ophyd.controls import (PVPositioner, EpicsSignal, EpicsMotor)


def simple_scan(motors=[],
                trajectories=[],
                triggers=[],
                detectors=[],
                pos_settle_time=0.01,
                trigger_settle_time=0.01,
                det_settle_time=0.01,
                dwell_time=1.0):
    '''
    motors: a list of positioners
    trajectories: a list of iterables, corresponding to each motor
    triggers: a list of tuples in the format (pv, value) to run after
              motion has finished
    detectors: pvs to record after the dwell time
    dwell_time: time to dwell per point of scan
    '''

    logger = config.logger

    def wait_motor(m):
        logger.debug('Waiting on motor %s' % m)
        while m.moving:
            time.sleep(0.01)

    def move_motors():
        status = []
        for motor in motors:
            try:
                pos = motor.move_next(wait=False)
            except StopIteration:
                logger.debug('End of trajectory for motor %s' % motor)
                # End of the trajectory
                status.append(True)
                break
            else:
                logger.debug('Moving motor %s to %s' % (motor, pos))
                status.append(False)

        if all(status):
            logger.debug('End of trajectory for all motors')
            return False

        for motor in motors:
            wait_motor(motor)

        return True

    def do_triggers():
        for trigger, value in triggers:
            logger.debug('Trigger %s = %s' % (trigger, value))
            trigger.request = value

    def collect_data():
        logger.debug('Collecting data')
        # return [det.read() for det in detectors]
        a = [det.readback for det in detectors]
        print(a)
        return a

    for motor, pos in zip(motors, trajectories):
        logger.debug('Setting trajectory for motor %s' % motor)
        motor.set_trajectory(pos)

    all_data = []
    try:
        while True:
            if not move_motors():
                break

            time.sleep(pos_settle_time)
            do_triggers()
            time.sleep(trigger_settle_time)

            time.sleep(dwell_time)
            time.sleep(det_settle_time)
            all_data.append(collect_data())

    except KeyboardInterrupt:
        logger.error('Scan interrupted by KeyboardInterrupt')
        for m in motors:
            logger.debug('Stopping motor %s' % m._alias)
            m.stop()

    trajectories = [m._followed for m in motors]
    return trajectories, all_data


def test():
    loggers = ('ophyd.controls.signal',
               'ophyd.controls.positioner',
               'ophyd.session',
               )

    config.setup_loggers(loggers)

    fm = config.fake_motors[0]

    if 1:
        mono = 'XF:23ID1-OP{Mono}'
        pos0 = PVPositioner('%sEnrgy-SP' % mono,
                            readback='%sEnrgy-I' % mono,
                            # act=actuate_pv, act_val=1,
                            stop='%sCmd:Stop-Cmd.PROC' % mono, stop_val=1,
                            done='%sSts:Scan-Sts', done_val=0,
                            put_complete=False,
                            alias='mono',
                            )
        pos0_traj = np.linspace(500, 530, 5)
    else:
        motor_record = 'XF:23ID1-OP{Slt:1-Ax:T}Mtr'
        pos0 = EpicsMotor(motor_record)
        pos0_traj = np.linspace(5, 6, 5)

    # det = [EpicsSignal(pv, rw=False)
    #        for pv in config.fake_sensors]
    scaler_prefix = 'XF:23ID1-ES{Sclr:1}'

    scaler_count = EpicsSignal('%s.CNT' % scaler_prefix)
    det = [EpicsSignal('%s.S%d' % (scaler_prefix, i), rw=False)
           for i in range(1, 8)]

    # pos0_traj = [0, 0.1, 0.2]
    traj, data = simple_scan(motors=[pos0],
                             trajectories=[pos0_traj],
                             triggers=[(scaler_count, 1),
                                       ],
                             detectors=det,
                             dwell_time=1.0)

    print(traj, data)


if __name__ == '__main__':
    test()
