# vi: ts=4 sw=4
'''
:mod:`ophyd.control.positioner` - Ophyd positioners
===================================================

.. module:: ophyd.control.positioner
   :synopsis:

'''

from __future__ import print_function
import logging
import time

from epics.pv import fmt_time

from .signal import (EpicsSignal, SignalGroup)
from ..utils import TimeoutError
from ..utils.epics_pvs import record_field

logger = logging.getLogger(__name__)


class Positioner(SignalGroup):
    SUB_START = 'start_moving'
    SUB_DONE = 'done_moving'
    SUB_READBACK = 'readback'

    def __init__(self, *args, **kwargs):
        '''
        A soft positioner. Subclass from this to implement your own
        positioners.
        '''

        SignalGroup.__init__(self, *args, **kwargs)

        self._started_moving = False
        self._moving = False
        self._default_sub = None
        self._moved_callbacks = []
        self._position = None
        self._move_timeout = kwargs.get('move_timeout', 0.0)
        self._trajectory = None
        self._trajectory_idx = None
        self._followed = []

    def set_trajectory(self, traj):
        '''
        Set the trajectory of the motion

        :param iterable traj: Iterable sequence
        '''
        self._trajectory = iter(traj)
        self._followed = []

    @property
    def next_pos(self):
        '''
        Get the next point in the trajectory
        '''

        if self._trajectory is None:
            raise ValueError('Trajectory unset')

        try:
            next_pos = next(self._trajectory)
        except StopIteration:
            return None

        self._followed.append(next_pos)
        return next_pos

    def move_next(self, **kwargs):
        '''
        Move to the next point in the trajectory
        '''
        pos = self.next_pos
        if pos is None:
            raise StopIteration('End of trajectory')

        self.move(pos, **kwargs)

        return pos

    def move(self, position, wait=True,
             moved_cb=None, timeout=10.0):
        '''
        Move to a specified position, optionally waiting for motion to
        complete.

        :param position: Position to move to
        :param bool wait: Wait for move completion
        :param callable moved_cb: Call this callback when movement has
            finished (not applicable if `wait` is set)
        :param float timeout: Timeout in seconds

        :raises: TimeoutError
        '''

        # TODO session manager handles ctrl-C to stop move?

        if wait:
            t0 = time.time()

            def check_timeout():
                return timeout is not None and (time.time() - t0) > timeout

            while not self._started_moving:
                time.sleep(0.05)

                if check_timeout():
                    del self._moved_callbacks[:]

                    raise TimeoutError('Failed to move %s to %s in %s s (no motion)' %
                                       (self, position, timeout))

            while self._moving:
                time.sleep(0.05)

                if check_timeout():
                    del self._moved_callbacks[:]

                    raise TimeoutError('Failed to move %s to %s in %s s' %
                                       (self, position, timeout))

        elif moved_cb is not None:
            self._moved_callbacks.append(moved_cb)

    def _done_moving(self, timestamp=None, value=None, **kwargs):
        '''
        Called when motion has completed.
        Runs SUB_DONE subscription.
        '''

        self._run_sub(sub_type=self.SUB_DONE, timestamp=timestamp,
                      value=value, **kwargs)

        if self._moved_callbacks:
            for cb in self._moved_callbacks:
                cb(timestamp=timestamp, value=value, **kwargs)

            del self._moved_callbacks[:]

    def stop(self):
        '''
        Stops motion
        '''
        raise NotImplementedError('')

    @property
    def position(self):
        '''
        The current position of the motor in its engineering units

        :rtype: float
        '''
        return self._position

    def _set_position(self, value, **kwargs):
        '''
        Set the current internal position and run the
        SUB_READBACK subscription
        '''
        self._position = value

        timestamp = kwargs.pop('timestamp', time.time())
        self._run_sub(sub_type=self.SUB_READBACK, timestamp=timestamp,
                      value=value, **kwargs)

    @property
    def moving(self):
        '''
        Whether or not the motor is moving

        :rtype: bool
        '''
        return self._moving


class EpicsMotor(Positioner):

    def __init__(self, record, **kwargs):
        '''
        An EPICS motor record, wrapped in a :class:`Positioner`

        :param str record: The record to use
        '''

        self._record = record

        name = kwargs.pop('name', record)
        Positioner.__init__(self, name=name, **kwargs)

        signals = [EpicsSignal(self.field_pv('RBV'), rw=False, alias='_user_readback'),
                   EpicsSignal(self.field_pv('VAL'), alias='_user_request'),
                   EpicsSignal(self.field_pv('MOVN'), alias='_is_moving'),
                   EpicsSignal(self.field_pv('DMOV'), alias='_done_move'),
                   EpicsSignal(self.field_pv('EGU'), alias='_egu'),
                   EpicsSignal(self.field_pv('STOP'), alias='_stop'),
                   # EpicsSignal(self.field_pv('RDBD'), alias='retry_deadband'),
                   ]

        for signal in signals:
            self.add_signal(signal)

        self._moving = bool(self._is_moving.value)
        self._done_move.subscribe(self._move_changed)
        self._user_readback.subscribe(self._pos_changed)

    @property
    def moving(self):
        '''
        whether or not the motor is moving

        :rtype: bool
        '''
        return bool(self._is_moving._get_readback(use_monitor=False))

    def stop(self):
        self._stop._set_request(1, wait=False)

    @property
    def record(self):
        '''
        The EPICS record name
        '''
        return self._record

    def field_pv(self, field):
        '''
        Return a full PV from the field name
        '''
        return record_field(self._record, field)

    def move(self, position, wait=True,
             **kwargs):

        try:
            # self._user_request.request = position
            self._user_request._set_request(position, wait=wait)

            Positioner.move(self, position, wait=wait,
                            **kwargs)
        except KeyboardInterrupt:
            self.stop()

    def __str__(self):
        return 'EpicsMotor(record={0}, val={1}, rbv={2}, egu={3})'.format(
            self._record, self._user_request.value, self._user_readback.value,
            self._egu.value)

    def _pos_changed(self, timestamp=None, value=None,
                     **kwargs):
        '''
        Callback from EPICS, indicating a change in position
        '''
        self._set_position(value)

    def _move_changed(self, timestamp=None, value=None, sub_type=None,
                      **kwargs):
        '''
        Callback from EPICS, indicating that movement status has changed
        '''
        was_moving = self._moving
        self._moving = (value != 1)

        if not self._started_moving:
            self._started_moving = (not was_moving and self._moving)

        logger.debug('[ts=%s] %s moving: %s (value=%s)' % (fmt_time(timestamp),
                                                           self, self._moving, value))

        if self._started_moving:
            self._run_sub(sub_type=self.SUB_START, timestamp=timestamp,
                          value=value, **kwargs)

        if was_moving and not self._moving:
            self._done_moving(timestamp=timestamp, value=value)

    @property
    def report(self):
        #return {self._user_readback.read_pvname: self._user_readback.value}
        return {self._name: self.position,
                'pv': self._user_readback.read_pvname}


# TODO: make Signal aliases uniform between EpicsMotor and PVPositioner
class PVPositioner(Positioner):
    def __init__(self, setpoint, readback=None,
                 act=None, act_val=1,
                 stop=None, stop_val=1,
                 done=None, done_val=1,
                 put_complete=False,
                 **kwargs):
        '''
        A :class:`Positioner`, comprised of multiple :class:`EpicsSignal`s.

        :param str setpoint: The setpoint (request) PV
        :param str readback: The readback PV (e.g., encoder position PV)
        :param str act: The actuation PV to set when movement is requested
        :param act_val: The actuation value
        :param str stop: The stop PV to set when motion should be stopped
        :param stop_val: The stop value
        :param str done: A readback value indicating whether motion is finished
        :param done_val: The value of the done pv when motion has completed
        :param bool put_complete: If set, the specified PV should allow
            for asynchronous put completion to indicate motion has finished.
            If `act` is specified, it will be used for put completion.
            Otherwise, the `setpoint` will be used.

            See the `-c` option from `caput` for more information.
        '''

        Positioner.__init__(self, **kwargs)

        self._stop_val = stop_val
        self._done_val = done_val
        self._act_val = act_val
        self._put_complete = bool(put_complete)

        self._actuate = None
        self._stop = None
        self._done = None

        signals = []
        self.add_signal(EpicsSignal(setpoint, alias='_setpoint'))

        if readback is not None:
            self.add_signal(EpicsSignal(readback, alias='_readback'))

            self._readback.subscribe(self._pos_changed)
        else:
            self._setpoint.subscribe(self._pos_changed)

        if act is not None:
            self.add_signal(EpicsSignal(act, alias='_actuate'))

        if stop is not None:
            self.add_signal(EpicsSignal(stop, alias='_stop'))

        if done is not None:
            self.add_signal(EpicsSignal(done, alias='_done'))

            self._done.subscribe(self._move_changed)

        for signal in signals:
            self.add_signal(signal)

    def _move_wait(self, position, **kwargs):
        self._started_moving = False

        if self._put_complete:
            # TODO timeout setting with put completion; untested
            if self._put_complete:
                if self._actuate is None:
                    self._setpoint._set_request(position, wait=True,
                                                timeout=self._move_timeout)
                else:
                    self._setpoint._set_request(position, wait=False)
                    self._actuate._set_request(self._act_val, wait=True,
                                               timeout=self._move_timeout)

            if self._started_moving and not self._moving:
                self._done_moving(timestamp=self._setpoint.readback_timestamp)
            elif self._started_moving and self._moving:
                # TODO better exceptions
                raise TimeoutError('Failed to move %s to %s s (put complete done, still moving)' %
                                   (self, position))
            else:
                raise TimeoutError('Failed to move %s to %s s (no motion, put complete)' %
                                   (self, position))
        else:
            self._setpoint._set_request(position, wait=True)
            logger.debug('Setpoint set: %s = %s' % (self._setpoint.write_pvname,
                                                    position))

            if self._actuate is not None:
                self._actuate._set_request(self._act_val, wait=True)
                logger.debug('Actuating: %s = %s' % (self._actuate.write_pvname,
                                                     self._act_val))

        Positioner.move(self, position, wait=True,
                        **kwargs)

    def _move_async(self, position, **kwargs):
        self._started_moving = False

        self._setpoint.request = position

        logger.debug('Setpoint set: %s = %s' % (self._setpoint.write_pvname,
                                                self._act_val))
        if self._actuate is not None:
            self._actuate._set_request(self._act_val, wait=False)
            logger.debug('Actuating: %s = %s' % (self._actuate.write_pvname,
                                                 self._act_val))

        Positioner.move(self, position, wait=False,
                        **kwargs)

    def move(self, position, wait=True,
             **kwargs):
        try:
            if wait:
                self._move_wait(position, **kwargs)

            else:
                self._move_async(position, **kwargs)
        except KeyboardInterrupt:
            self.stop()

    def _move_changed(self, timestamp=None, value=None, sub_type=None,
                      **kwargs):
        was_moving = self._moving
        self._moving = (value != self._done_val)

        if not self._started_moving:
            self._started_moving = (not was_moving and self._moving)

        logger.debug('[ts=%s] %s moving: %s (value=%s)' % (fmt_time(timestamp),
                                                           self, self._moving, value))

        if self._started_moving:
            self._run_sub(sub_type=self.SUB_START, timestamp=timestamp,
                          value=value, **kwargs)

        if not self._put_complete:
            # In the case of put completion, motion complete
            if was_moving and not self._moving:
                self._done_moving(timestamp=timestamp, value=value)

    def _pos_changed(self, timestamp=None, value=None,
                     **kwargs):
        '''
        Callback from EPICS, indicating a change in position
        '''
        self._set_position(value)

    def stop(self):
        self._stop._set_request(self._stop_val, wait=False)

    # TODO: this will fail if no readback is provided to initializer
    @property
    def report(self):
        #return {self._readback.read_pvname: self._readback.value}
        return {self._name: self.position, 'pv': self._readback.read_pvname}
