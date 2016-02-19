# vi: ts=4 sw=4
'''
:mod:`ophyd.control.epicsmotor` - Ophyd epics motors
====================================================

.. module:: ophyd.control.epicsmotor
   :synopsis:
'''


import logging

from epics.pv import fmt_time

from .signal import (EpicsSignal, EpicsSignalRO)
from .utils import DisconnectedError
from .utils.epics_pvs import raise_if_disconnected
from .positioner import PositionerBase
from .device import (Device, Component as Cpt)


logger = logging.getLogger(__name__)


class EpicsMotor(Device, PositionerBase):
    '''An EPICS motor record, wrapped in a :class:`Positioner`

    Keyword arguments are passed through to the base class, Positioner

    Parameters
    ----------
    prefix : str
        The record to use
    read_attrs : sequence of attribute names
        The signals to be read during data acquisition (i.e., in read() and
        describe() calls)
    name : str, optional
        The name of the device
    parent : instance or None
        The instance of the parent device, if applicable
    '''
    user_readback = Cpt(EpicsSignalRO, '.RBV')
    user_setpoint = Cpt(EpicsSignal, '.VAL', limits=True)
    motor_egu = Cpt(EpicsSignal, '.EGU')
    motor_is_moving = Cpt(EpicsSignalRO, '.MOVN')
    motor_done_move = Cpt(EpicsSignalRO, '.DMOV')
    motor_stop = Cpt(EpicsSignal, '.STOP')

    def __init__(self, prefix, *, read_attrs=None, configuration_attrs=None,
                 monitor_attrs=None, name=None, parent=None, **kwargs):
        if read_attrs is None:
            read_attrs = ['user_readback', 'user_setpoint']

        if configuration_attrs is None:
            configuration_attrs = ['motor_egu', ]

        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs,
                         monitor_attrs=monitor_attrs,
                         name=name, parent=parent, **kwargs)

        # Make the default alias for the user_readback the name of the
        # motor itself.
        self.user_readback.name = self.name

        self.motor_done_move.subscribe(self._move_changed)
        self.user_readback.subscribe(self._pos_changed)

    @property
    @raise_if_disconnected
    def precision(self):
        '''The precision of the readback PV, as reported by EPICS'''
        return self.user_readback.precision

    @property
    @raise_if_disconnected
    def egu(self):
        '''The engineering units (EGU) for a position'''
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
        return bool(self.motor_is_moving.get(use_monitor=False))

    @raise_if_disconnected
    def stop(self):
        self.motor_stop.put(1, wait=False)
        super().stop()

    @raise_if_disconnected
    def move(self, position, wait=True, **kwargs):
        self._started_moving = False

        status = super().move(position, **kwargs)
        self.user_setpoint.put(position, wait=False)

        try:
            if wait:
                status.wait()
        except KeyboardInterrupt:
            self.stop()
            raise

        return status

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

        return {self.name: position,
                'pv': self.user_readback.pvname}

    def _repr_info(self):
        yield from super()._repr_info()
