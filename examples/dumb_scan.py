#!/usr/bin/env python2.7
'''A simple, dumb scan test which only uses the basic signals'''

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
                dwell_time=1.0):
    '''Run a simple scan outside of the Ophyd framework

    Parameters
    ----------
    motors : a list of positioners
    trajectories : a list of iterables
        Trajectories should match in position to the motors
    triggers : a list of tuples in the format (pv, value)
        Run after motion has finished
    detectors : list of pvs
        Recorded after the dwell time
    dwell_time : float
        time to dwell per point of scan
    '''

    logger = config.logger

    def move_motors():
        end_of_trajectory = []
        status = []
        for motor in motors:
            try:
                _, stat = motor.move_next(wait=False)
            except StopIteration:
                logger.debug('End of trajectory for motor %s' % motor)
                # End of the trajectory
                end_of_trajectory.append(True)
                break
            else:
                logger.debug('Moving motor %s to %s' % (motor, pos))
                end_of_trajectory.append(False)
                status.append(stat)

        if all(end_of_trajectory):
            logger.debug('End of trajectory for all motors')
            return False

        while not all(stat.done for stat in status):
            time.sleep(0.01)

        return True

    def do_triggers():
        for trigger, value in triggers:
            logger.debug('Trigger %s = %s' % (trigger, value))
            trigger.value = value

    def collect_data():
        logger.debug('Collecting data')
        # return [det.read() for det in detectors]
        return [det.value for det in detectors]

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
               )

    config.setup_loggers(loggers)

    fm = config.fake_motors[0]

    if 0:
        pos0 = PVPositioner(fm['setpoint'],
                            readback=fm['readback'],
                            act=fm['actuate'], act_val=1,
                            stop=fm['stop'], stop_val=1,
                            done=fm['moving'], done_val=1,
                            put_complete=False,
                            )
    else:
        motor_record = config.motor_recs[0]
        pos0 = EpicsMotor(motor_record)

    det = [EpicsSignal(pv, rw=False)
           for pv in config.fake_sensors]

    # pos0_traj = [0, 0.1, 0.2]
    pos0_traj = np.linspace(0, 1, 5)
    traj, data = simple_scan(motors=[pos0],
                             trajectories=[pos0_traj],
                             triggers=[],
                             detectors=det,
                             dwell_time=1.0)

    print(traj, data)


if __name__ == '__main__':
    test()
