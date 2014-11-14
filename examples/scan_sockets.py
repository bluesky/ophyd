from __future__ import (absolute_import, division,
                        unicode_literals, print_function)
import six
from six.moves import zip

import time
import numpy as np

import config
from ophyd.controls import (PVPositioner, EpicsSignal, EpicsMotor)
from collections import deque
from datetime import datetime
from broker import config as cfg
from broker.client import write_json_to_socket

# just to set up the loggers

loggers = ('ophyd.controls.signal',
               'ophyd.controls.positioner',
               'ophyd.session',
               )

config.setup_loggers(loggers)
logger = config.logger


def simple_scan(motors,
                trajectories,
                detectors,
                triggers,
                pos_settle_time=0.01,
                trigger_settle_time=0.01,
                dwell_time=1.0,
                host=None,
                port=None,
                ):
    '''
    A demo scan script

    Parameters
    ----------
    motors : list of Positioners
        List of motors to move as ophyd.controls.Positioner objects

    trajectories : list of iterables of values
        Length of trajectories must match length of motors, all trajectories
        must be the same length

    detectors : dict
        Keyed on alias, values are EpicsSignals that represent
        dectectors

    triggers : list of tuples
        a list of tuples in the format (pv, value) to run after
        motion has finished

    pos_settle_time : float, optional
        settle time after all the motors are done moving.  Defaults
        to 0.01

    trigger_settle_time : float, optional
        Settling time to make sure all the triggers go out before
        starting collection

    dwell_time : float, optional
        How long to dwell before starting collection

    host : str, optional
        ip address or name of host to push data to.  Defaults
        to broker.configure.HOST

    port : int, optional
        The port to push data to on host.  Defaults to
        broker.configure.PORT

    Returns
    -------
    data : list of tuples
        List tuples of form (time_stamp, data_dict).  The data dictionaries
        are keyed on the keys from `detectors` and the values are what ever
        the detectors return when read.

    '''
    # default values for socket, maybe let these be None to suppress output
    # in the future
    if host is None:
        host = cfg.HOST
    if port is None:
        port = cfg.PORT

    # validation on motors + trajectories
    if len(motors) != len(trajectories):
        raise ValueError(("motors and trajectories must be coupled 1:1 "
                         "You passed in {} motors and {} trajectories"
                         ).format(len(motors), len(trajectories)
                         ))

    if not len(motors):
        raise ValueError("you must pass in at least one motor to scan")

    traj_len = len(trajectories[0])
    if not all(len(t) == traj_len for t in trajectories[1:]):
        t_lens = [len(t) for t in trajectories]
        raise ValueError("All trajectories must be the same length. "
                         "Your trajectories have lengths {}".format(t_lens))

    # create closure over triggers
    def do_triggers():
        """
        Hits all of the triggers.  This is a closure over the input trigger
        list so no inputs.  No returns
        """
        for trigger, value in triggers:
            logger.debug('Trigger %s = %s' % (trigger, value))
            trigger.request = value

    # closure over detectors
    def collect_data():
        logger.debug('Collecting data')
        return {n: det.readback for n, det
                in six.iteritems(detectors)}

    # closure over motors
    def move_motors(positions):
        """
        Moves the motors to the given positions and waits
        till they have all finished moving

        Parameters
        ----------
        positions : tuple
            positions to move the motors to, must be same
            length as motors
        """
        print('positions: {}'.format(positions))
        for m, p in zip(motors, positions):
            print('p: {}'.format(p))
            logger.debug('Moving motor %s to %s', m, p)
            m.move(p, wait=False)

        # this will catch on the slowest one
        for m in motors:
            logger.debug('Waiting on motor %s', m)
            while m.moving:
                time.sleep(0.01)

    # collection point for the data
    all_data = deque()
    try:
        # loop over all of the positions
        for j, positions in enumerate(zip(*trajectories)):
            print(j, positions)
            # move the motors
            move_motors(positions)
            # sleep for a bit to make sure they are settled
            time.sleep(pos_settle_time)
            # kick all of the triggers
            do_triggers()
            # let the triggers settle for a bit and dwell
            time.sleep(trigger_settle_time + dwell_time)
            # collect the data from the detectors
            data = collect_data()
            p = {"p{}".format(j):_p for j, _p in enumerate(positions)}
            data.update(p)
            # grab the time stamp
            ts = datetime.now().isoformat()
            # make a list of tuples (time_stamp, data_dict)
            a = [(ts, data)]
            # push data across the wire
            print('a', a)
            write_json_to_socket(a, host, port, json_encoder=None)

            time.sleep(1)
            all_data.append((ts, data))

    except KeyboardInterrupt:
        logger.error('Scan interrupted by KeyboardInterrupt')
        for m in motors:
            logger.debug('Stopping motor %s' % m._alias)
            m.stop()

    return list(all_data)


def test():
    """
    Keeping this function around for reference
    """
    fm = config.fake_motors[0]


    motor_record = 'XF:23ID1-OP{Slt:3-Ax:X}Mtr'
    pos0 = EpicsMotor(motor_record)
    pos0_traj = np.linspace(5.75, 5.95, 51)

    #scaler_prefix = 'XF:23ID1-ES{Sclr:1}'
    ad_prefix = 'XF:23ID1-ES{Dif-Cam:Beam}'
    ad_count = EpicsSignal('%scam1:Acquire' % ad_prefix)
    #scaler_count = EpicsSignal('%s.CNT' % scaler_prefix)
    #dets = {"s{}".format(i): EpicsSignal('%s.S%d' % (scaler_prefix, i), rw=False)
    #       for i in range(1, 8)}
    dets = {"s{}".format(i): EpicsSignal('%sStats%d:Total_RBV' % (ad_prefix, i), rw=False)
           for i in range(1, 6)}

    data = simple_scan(motors=[pos0],
                             trajectories=[pos0_traj],
                             triggers=[(ad_count, 1),],
                             detectors=dets,
                             dwell_time=1.0)

    print(data)


if __name__ == '__main__':
    test()

# this is here in case I really don't understand something
if 0:
    # create local closure over motor
    def move_motors_old():
        """
        Move all of the motors and wait for them all to be done.

        Returns
        -------
        done : bool
            Returns True if the trajectory is exhausted, False if there
            are more points
        """

        for motor in motors:
            try:
                pos = motor.move_next(wait=False)
            except StopIteration:
                logger.debug('End of trajectory for motor %s' % motor)
                # End of the trajectory
                return True
            else:
                logger.debug('Moving motor %s to %s' % (motor, pos))

        # this will catch on the slowest one
        for motor in motors:
            logger.debug('Waiting on motor {}'.format(motor))
            while motor.moving:
                time.sleep(0.01)

        return False

        # #### DEDENT THIS TO USE IT
        # assign the trajectories to the motors.
        for motor, pos in zip(motors, trajectories):
            logger.debug('Setting trajectory for motor %s' % motor)
            motor.set_trajectory(pos)
