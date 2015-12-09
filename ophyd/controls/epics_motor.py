# vi: ts=4 sw=4
'''
:mod:`ophyd.control.epicsmotor` - Ophyd epics motors
====================================================

.. module:: ophyd.control.epicsmotor
   :synopsis:
'''

from __future__ import print_function
import logging

from epics.pv import fmt_time

from .signal import (EpicsSignal, EpicsSignalRO)
from ..utils import DisconnectedError
from ..utils.epics_pvs import raise_if_disconnected
from .positioner import Positioner
from .device import (OphydDevice, Component as Cpt)


logger = logging.getLogger(__name__)


class EpicsMotor(OphydDevice, Positioner):
    '''An EPICS motor record, wrapped in a :class:`Positioner`

    Keyword arguments are passed through to the base class, Positioner

    Parameters
    ----------
    record : str
        The record to use
    '''
    user_readback = Cpt(EpicsSignalRO, '.RBV')
    user_setpoint = Cpt(EpicsSignal, '.VAL', limits=True)
    motor_egu = Cpt(EpicsSignal, '.EGU')
    _is_moving = Cpt(EpicsSignalRO, '.MOVN')
    _done_move = Cpt(EpicsSignalRO, '.DMOV')
    _stop = Cpt(EpicsSignal, '.STOP')

    def __init__(self, record, settle_time=0.05, read_signals=None, name=None):
        if read_signals is None:
            read_signals = ['user_readback', 'user_setpoint', 'motor_egu']

        OphydDevice.__init__(self, record, read_signals=read_signals,
                             name=name)
        Positioner.__init__(self)

        self.settle_time = float(settle_time)
        # TODO: settle_time is unused?

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

    @property
    @raise_if_disconnected
    def position(self):
        '''The current position of the motor in its engineering units

        Returns
        -------
        position : float
        '''
        return self._position

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
