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

from .signal import (EpicsSignal, EpicsSignalRO)
from ..utils import TimeoutError, DisconnectedError
from ..utils.epics_pvs import raise_if_disconnected
from .ophydobj import MoveStatus
from .device import (OphydDevice, Component as C)


logger = logging.getLogger(__name__)


class Positioner(OphydDevice):
    '''A soft positioner.

    Subclass from this to implement your own positioners.
    '''

    SUB_START = 'start_moving'
    SUB_DONE = 'done_moving'
    SUB_READBACK = 'readback'
    _SUB_REQ_DONE = '_req_done'  # requested move finished subscription
    _default_sub = SUB_READBACK

    def __init__(self, prefix='', timeout=None, egu=None, name=None,
                 read_signals=None):
        super().__init__(prefix, name=name, read_signals=read_signals)

        if timeout is None:
            timeout = 0.0

        if egu is None:
            egu = ''

        self._started_moving = False
        self._moving = False
        self._position = None
        self._timeout = timeout
        self._egu = egu

    @property
    def egu(self):
        return self._egu

    @property
    def limits(self):
        return (0, 0)

    @property
    def low_limit(self):
        return self.limits[0]

    @property
    def high_limit(self):
        return self.limits[1]

    def move(self, position, wait=True, moved_cb=None, timeout=30.0):
        '''Move to a specified position, optionally waiting for motion to
        complete.

        Parameters
        ----------
        position
            Position to move to
        wait : bool
            Wait for move completion
        moved_cb : callable
            Call this callback when movement has finished (not applicable if
            `wait` is set)
        timeout : float
            Timeout in seconds

        Raises
        ------
        TimeoutError, ValueError (on invalid positions)
        '''
        self._run_subs(sub_type=self._SUB_REQ_DONE, success=False)
        self._reset_sub(self._SUB_REQ_DONE)

        is_subclass = (self.__class__ is not Positioner)
        if not is_subclass:
            # When not subclassed, Positioner acts as a soft positioner,
            # immediately 'moving' to the target position when requested.
            self._started_moving = True
            self._moving = False

        status = MoveStatus(self, position)
        if wait:
            t0 = time.time()

            def check_timeout():
                return timeout is not None and (time.time() - t0) > timeout

            while not self._started_moving:
                time.sleep(0.05)

                if check_timeout():
                    raise TimeoutError('Failed to move %s to %s '
                                       'in %s s (no motion)' %
                                       (self.name, position, timeout))

            while self.moving:
                time.sleep(0.05)

                if check_timeout():
                    raise TimeoutError('Failed to move %s to %s in %s s' %
                                       (self.name, position, timeout))

            status._finished()

        else:
            if moved_cb is not None:
                self.subscribe(moved_cb, event_type=self._SUB_REQ_DONE,
                               run=False)

            self.subscribe(status._finished,
                           event_type=self._SUB_REQ_DONE, run=False)

        if not is_subclass:
            self._set_position(position)
            self._done_moving()

        return status

    def _done_moving(self, timestamp=None, value=None, **kwargs):
        '''Call when motion has completed.  Runs SUB_DONE subscription.'''

        self._run_subs(sub_type=self.SUB_DONE, timestamp=timestamp,
                       value=value, **kwargs)

        self._run_subs(sub_type=self._SUB_REQ_DONE, timestamp=timestamp,
                       value=value, success=True,
                       **kwargs)
        self._reset_sub(self._SUB_REQ_DONE)

    def stop(self):
        '''Stops motion'''

        self._run_subs(sub_type=self._SUB_REQ_DONE, success=False)
        self._reset_sub(self._SUB_REQ_DONE)

    @property
    @raise_if_disconnected
    def position(self):
        '''The current position of the motor in its engineering units

        Returns
        -------
        position : float
        '''
        return self._position

    def _set_position(self, value, **kwargs):
        '''Set the current internal position, run the readback subscription'''
        self._position = value

        timestamp = kwargs.pop('timestamp', time.time())
        self._run_subs(sub_type=self.SUB_READBACK, timestamp=timestamp,
                       value=value, **kwargs)

    @property
    def moving(self):
        '''Whether or not the motor is moving

        Returns
        -------
        moving : bool
        '''
        return self._moving

    def set(self, new_position, *, wait=False,
            moved_cb=None, timeout=30.0):
        """
        New API for controlling movers.


        Parameters
        ----------
        new_position : dict
            A dictionary of new positions keyed on axes name.  This is
            symmetric with read such that `mot.set(mot.read())` works as
            as expected.
        """
        return self.move(new_position, wait=wait, moved_cb=moved_cb,
                         timeout=timeout)


class EpicsMotor(Positioner):
    '''An EPICS motor record, wrapped in a :class:`Positioner`

    Keyword arguments are passed through to the base class, Positioner

    Parameters
    ----------
    record : str
        The record to use
    '''
    user_readback = C(EpicsSignalRO, '.RBV')
    user_setpoint = C(EpicsSignal, '.VAL', limits=True)
    motor_egu = C(EpicsSignal, '.EGU')
    _is_moving = C(EpicsSignalRO, '.MOVN')
    _done_move = C(EpicsSignalRO, '.DMOV')
    _stop = C(EpicsSignal, '.STOP')

    def __init__(self, record, settle_time=0.05, read_signals=None, name=None):
        if read_signals is None:
            read_signals = ['user_readback', 'user_setpoint', 'motor_egu']

        super().__init__(record, read_signals=read_signals, name=name)

        self.settle_time = float(settle_time)

        self._done_move.subscribe(self._move_changed)
        self.user_readback.subscribe(self._pos_changed)

    @property
    @raise_if_disconnected
    def precision(self):
        '''The precision of the readback PV, as reported by EPICS'''
        return self.user_readback.precision

    @property
    @raise_if_disconnected
    def egu(self):
        '''Engineering units'''
        return self.motor_egu.get()

    @property
    @raise_if_disconnected
    def limits(self):
        return self.user_setpoint.limits

    @property
    @raise_if_disconnected
    def moving(self):
        '''Whether or not the motor is moving

        Returns
        -------
        moving : bool
        '''
        return bool(self._is_moving.get(use_monitor=False))

    @raise_if_disconnected
    def stop(self):
        self._stop.put(1, wait=False)
        super().stop()

    @raise_if_disconnected
    def move(self, position, wait=True, **kwargs):
        self._started_moving = False

        try:
            self.user_setpoint.put(position, wait=wait)
            return super().move(position, wait=wait, **kwargs)
        except KeyboardInterrupt:
            self.stop()
            raise

    def check_value(self, pos):
        '''Check that the position is within the soft limits'''
        self.user_setpoint.check_value(pos)

    def _pos_changed(self, timestamp=None, value=None, **kwargs):
        '''Callback from EPICS, indicating a change in position'''
        self._set_position(value)

    def _move_changed(self, timestamp=None, value=None, sub_type=None,
                      **kwargs):
        '''Callback from EPICS, indicating that movement status has changed'''
        was_moving = self._moving
        self._moving = (value != 1)

        started = False
        if not self._started_moving:
            started = self._started_moving = (not was_moving and self._moving)

        logger.debug('[ts=%s] %s moving: %s (value=%s)', fmt_time(timestamp),
                     self, self._moving, value)

        if started:
            self._run_subs(sub_type=self.SUB_START, timestamp=timestamp,
                           value=value, **kwargs)

        if was_moving and not self._moving:
            self._done_moving(timestamp=timestamp, value=value)

    @property
    def report(self):
        try:
            position = self.position
        except DisconnectedError:
            position = 'disconnected'

        return {self._name: position,
                'pv': self.user_readback.pvname}


class PVPositioner(Positioner):
    '''A Positioner which is controlled using multiple user-defined signals

    Keyword arguments are passed through to the base class, Positioner

    Parameters
    ----------
    prefix : str, optional
        The device prefix used for all sub-positioners. This is optional as it
        may be desirable to specify full PV names for PVPositioners.
    settle_time : float, optional
        Time to wait after a move to ensure a move complete callback is received
    limits : 2-element sequence, optional
        (low_limit, high_limit)
    name : str
        The device name
    timeout : float
        The motion timeout

    Attributes
    ----------
    setpoint : Signal
        The setpoint (request) signal
    readback : Signal or None
        The readback PV (e.g., encoder position PV)
    actuate : Signal or None
        The actuation PV to set when movement is requested
    actuate_value : any, optional
        The actuation value, sent to the actuate signal when motion is requested
    stop_signal : Signal or None
        The stop PV to set when motion should be stopped
    stop_value : any, optional
        The value sent to stop_signal when a stop is requested
    done : Signal
        A readback value indicating whether motion is finished
    done_val : any, optional
        The value that the done pv should be when motion has completed
    put_complete : bool, optional
        If set, the specified PV should allow for asynchronous put completion to
        indicate motion has finished.  If `actuate` is specified, it will be
        used for put completion.  Otherwise, the `setpoint` will be used.  See
        the `-c` option from `caput` for more information.
    '''

    setpoint = None  # TODO: should add limits=True
    readback = None
    actuate = None
    actuate_value = 1

    stop_signal = None
    stop_value = 1

    done = None
    done_value = 1
    put_complete = False

    def __init__(self, prefix='', *, settle_time=0.05, limits=None, name=None,
                 timeout=None):
        super().__init__(prefix, name=name, timeout=timeout)

        if self.__class__ is PVPositioner:
            raise ValueError('PVPositioner must be subclassed with the correct '
                             'signals set in the class definition.')

        self.settle_time = float(settle_time)

        if limits is not None:
            self._limits = tuple(limits)
        else:
            self._limits = None

        if self.readback is not None:
            self.readback.subscribe(self._pos_changed)
        elif self.setpoint is not None:
            self.setpoint.subscribe(self._pos_changed)
        else:
            raise ValueError('A setpoint or a readback must be specified')

        if self.done is None and not self.put_complete:
            msg = '''Positioner %s is mis-configured. A "done" Signal must be
                     provided or put_complete must be True.''' % self.name
            raise ValueError(msg)

        if self.done is not None:
            self.done.subscribe(self._move_changed)

    def check_value(self, pos):
        '''Check that the position is within the soft limits'''
        if self.limits is not None:
            low, high = self.limits
            if low != high and not (low <= pos <= high):
                raise ValueError('{} outside of user-specified limits'
                                 ''.format(pos))
        else:
            self.setpoint.check_value(pos)

    @property
    def moving(self):
        '''Whether or not the motor is moving

        If a `done` PV is specified, it will be read directly to get the motion
        status. If not, it determined from the internal state of PVPositioner.

        Returns
        -------
        bool
        '''
        if self.done is not None:
            dval = self.done.get(use_monitor=False)
            return (dval != self.done_value)
        else:
            return self._moving

    def _move_wait_pc(self, position, **kwargs):
        '''*put complete* Move and wait until motion has completed'''
        has_done = self.done is not None
        if not has_done:
            moving_val = 1 - self.done_value
            self._move_changed(value=self.done_value)
            self._move_changed(value=moving_val)

        timeout = kwargs.pop('timeout', self._timeout)
        if timeout <= 0.0:
            # TODO pyepics timeout of 0 and None don't mean infinite wait?
            timeout = 1e6

        if self.actuate is None:
            self.setpoint.put(position, wait=True, timeout=timeout)
        else:
            self.setpoint.put(position, wait=False)
            self.actuate.put(self.actuate_value, wait=True, timeout=timeout)

        if has_done:
            time.sleep(self.settle_time)
        else:
            self._move_changed(value=self.done_value)

        if self._started_moving and not self._moving:
            self._done_moving(timestamp=self.setpoint.timestamp)
        elif self._started_moving and self._moving:
            # TODO better exceptions
            raise TimeoutError('Failed to move %s to %s '
                               '(put complete done, still moving)' %
                               (self.name, position))
        else:
            raise TimeoutError('Failed to move %s to %s '
                               '(no motion, put complete)' %
                               (self.name, position))

    def _move_wait(self, position, **kwargs):
        '''Move and wait until motion has completed'''
        self._started_moving = False

        if self.put_complete:
            self._move_wait_pc(position, **kwargs)
        else:
            self.setpoint.put(position, wait=True)
            logger.debug('Setpoint set: %s = %s',
                         self.setpoint.setpoint_pvname, position)

            if self.actuate is not None:
                self.actuate.put(self.actuate_value, wait=True)
                logger.debug('Actuating: %s = %s',
                             self.actuate.setpoint_pvname, self.actuate_value)

    def _move_async(self, position, **kwargs):
        '''Move and do not wait until motion is complete (asynchronous)'''
        self._started_moving = False

        def done_moving(**kwargs):
            if self.put_complete:
                logger.debug('%s async motion done', self.name)
                self._done_moving()

        if self.done is None and self.put_complete:
            # No done signal, so we rely on put completion
            moving_val = 1 - self.done_value
            self._move_changed(value=moving_val)

        if self.actuate is not None:
            self.setpoint.put(position, wait=False)
            self.actuate.put(self.actuate_value, wait=False,
                             callback=done_moving)
        else:
            self.setpoint.put(position, wait=False,
                              callback=done_moving)

    def move(self, position, wait=True, **kwargs):
        try:
            if wait:
                self._move_wait(position, **kwargs)
                return super().move(position, wait=True, **kwargs)
            else:
                # Setup the async retval first
                ret = super().move(position, wait=False, **kwargs)
                self._move_async(position, **kwargs)
                return ret
        except KeyboardInterrupt:
            self.stop()
            raise

    def _move_changed(self, timestamp=None, value=None, sub_type=None,
                      **kwargs):
        was_moving = self._moving
        self._moving = (value != self.done_value)

        started = False
        if not self._started_moving:
            started = self._started_moving = (not was_moving and self._moving)

        logger.debug('[ts=%s] %s moving: %s (value=%s)', fmt_time(timestamp),
                     self, self._moving, value)

        if started:
            self._run_subs(sub_type=self.SUB_START, timestamp=timestamp,
                           value=value, **kwargs)

        if not self.put_complete:
            # In the case of put completion, motion complete
            if was_moving and not self._moving:
                self._done_moving(timestamp=timestamp, value=value)

    def _pos_changed(self, timestamp=None, value=None,
                     **kwargs):
        '''Callback from EPICS, indicating a change in position'''
        self._set_position(value)

    def stop(self):
        if self.stop_signal is not None:
            self.stop_signal.put(self.stop_value, wait=False)
        super().stop()

    @property
    def report(self):
        return {self._name: self.position, 'pv': self.readback.pvname}

    @property
    def limits(self):
        if self._limits is not None:
            return tuple(self._limits)
        else:
            return self.setpoint.limits

    def __repr__(self):
        repr = ['settle_time={0.settle_time!r}'.format(self),
                'limits={0._limits!r}'.format(self)
                ]
        return self._get_repr(repr)
