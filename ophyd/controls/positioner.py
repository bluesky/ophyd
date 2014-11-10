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

from .signal import (EpicsSignal, SignalGroup, OpTimeoutError)


logger = logging.getLogger(__name__)


class Positioner(SignalGroup):
    SUB_DONE = 'done_moving'

    def __init__(self, *args, **kwargs):
        '''
        A soft positioner. Subclass from this to implement your own
        positioners.
        '''

        SignalGroup.__init__(self, *args, **kwargs)

        self._default_sub = None
        self._moved_callbacks = []
        self._position = None

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

        :raises: OpTimeoutError
        '''

        # TODO session manager handles ctrl-C to stop move?

        if wait:
            t0 = time.time()
            while self._moving:
                time.sleep(0.05)

                if timeout is not None and (time.time() - t0) > timeout:
                    del self._moved_callbacks[:]

                    raise OpTimeoutError('Failed to move %s to %s in %s s' %
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

        :returns: float
        '''
        return self._position

    @property
    def moving(self):
        '''
        Whether or not the motor is moving

        :returns: bool
        '''
        return self._moving


class EpicsMotor(Positioner):
    # TODO: EpicsMotor could potentially be just a special case of a PVPositioner,
    # but there's a lot of additional info we can grab, knowing that it's a
    # motor record. (the fact that the additional fields are rarely used
    # properly is another story though...)

    def __init__(self, record, **kwargs):
        '''
        An EPICS motor record, wrapped in a :class:`Positioner`

        :param str record: The record to use
        '''

        self._record = record

        Positioner.__init__(self, record, **kwargs)

        signals = [EpicsSignal(self._field_pv('RBV'), rw=False, alias='user_readback'),
                   EpicsSignal(self._field_pv('VAL'), alias='user_request'),
                   EpicsSignal(self._field_pv('MOVN'), alias='is_moving'),
                   EpicsSignal(self._field_pv('DMOV'), alias='done_moving'),
                   EpicsSignal(self._field_pv('EGU'), alias='egu'),
                   EpicsSignal(self._field_pv('STOP'), alias='_stop'),
                   # EpicsSignal(self._field_pv('RDBD'), alias='retry_deadband'),
                   ]

        for signal in signals:
            self.add_signal(signal)

        self._moving = bool(self.is_moving.value)
        self.done_moving.subscribe(self._move_changed)
        self.user_readback.subscribe(self._pos_changed)

    def stop(self):
        self._stop.request = 1

    def _field_pv(self, field):
        '''
        Return a full PV from the field name
        '''
        return '%s.%s' % (self._record, field.upper())

    def move(self, position, wait=True,
             **kwargs):

        # self.user_request.request = position
        self.user_request._set_request(position, wait=wait)

        Positioner.move(self, position, wait=wait,
                        **kwargs)

    def __str__(self):
        return 'EpicsMotor(record={0}, val={1}, rbv={2}, egu={3})'.format(
            self._record, self.user_request.value, self.user_readback.value,
            self.egu.value)

    def _pos_changed(self, timestamp=None, value=None,
                     **kwargs):
        '''
        Callback from EPICS, indicating a change in position
        '''
        self._position = value

    def _move_changed(self, timestamp=None, value=None,
                      **kwargs):
        '''
        Callback from EPICS, indicating that movement status has changed
        '''
        was_moving = self._moving
        self._moving = (value != 1)

        logger.debug('[ts=%s] %s moving: %s (value=%s)' % (fmt_time(timestamp),
                                                           self, self._moving, value))

        if was_moving and not self._moving:
            self._done_moving(timestamp=timestamp, value=value)


class PVPositioner(Positioner):
    # TODO implementation incomplete
    def __init__(self, setpoint, readback=None,
                 act=None, act_val=1,
                 stop=None, stop_val=1,
                 done=None, done_val=1,
                 use_put_complete=False,
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
        :param bool use_put_complete: If set, the setpoint PV should allow
            for asynchronous put completion to indicate motion has finished.
            See the `-c` option from `caput` for more information.
        '''

        Positioner.__init__(self, **kwargs)

        signals = [EpicsSignal(setpoint, alias='setpoint')]

        if readback is not None:
            signals.append(EpicsSignal(readback, alias='readback'))

            self.readback.subscribe(self._position_changed)
        else:
            self.setpoint.subscribe(self._position_changed)

        if act is not None:
            signals.append(EpicsSignal(act, alias='actuate'))

        if stop is not None:
            signals.append(EpicsSignal(stop, alias='stop'))

        if done is not None:
            signals.append(EpicsSignal(done, alias='done'))

            self.done.subscribe(self._move_changed)

        for signal in signals:
            self.add_signal(signal)

    def _field_pv(self, field):
        return '%s.%s' % (self._record, field.upper())

    def move(self, position, wait=True,
             **kwargs):
        self.setpoint.request = position

        Positioner.move(self, position, wait=wait,
                        **kwargs)

    def _move_changed(self, timestamp=None, value=None,
                      **kwargs):
        was_moving = self._moving
        self._moving = (value != 0)

        logger.debug('[ts=%s] %s moving: %s (value=%s)' % (fmt_time(timestamp),
                                                           self, self._moving, value))

        if was_moving and not self._moving:
            self._done_moving(timestamp=timestamp, value=value)

    def _pos_changed(self, timestamp=None, value=None,
                     **kwargs):
        '''
        Callback from EPICS, indicating a change in position
        '''
        self._position = value

    def stop(self):
        # TODO
        pass
