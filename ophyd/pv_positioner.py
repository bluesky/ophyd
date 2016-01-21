# vi: ts=4 sw=4
'''
:mod:`ophyd.control.pvpositioner` - Ophyd PV positioners
========================================================

.. module:: ophyd.control.pvpositioner
   :synopsis:
'''


import logging
import time

from epics.pv import fmt_time

from .utils import TimeoutError
from .positioner import Positioner


logger = logging.getLogger(__name__)


class Unspecified:
    pass


class PVPositioner(Positioner):
    '''A Positioner which is controlled using multiple user-defined signals

    Keyword arguments are passed through to the base class, Positioner

    Parameters
    ----------
    prefix : str
        The device prefix used for all sub-positioners. This is optional as it
        may be desirable to specify full PV names for PVPositioners.
    name : str, optional
        The device name, required unless instantiated as a Component
    settle_time : float, optional
        Time to wait after a move to ensure a move complete callback is received
    limits : 2-element sequence, optional
        (low_limit, high_limit)
    parent : Device, optional
        parent device
    timeout : float, optional
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
    done_value : any, optional
        The value that the done pv should be when motion has completed
    '''

    setpoint = Unspecified  # TODO: should add limits=True
    readback = Unspecified
    actuate = Unspecified
    actuate_value = 1

    stop_signal = Unspecified
    stop_value = 1

    done = Unspecified
    done_value = 1

    def __init__(self, prefix='', *, name=None, settle_time=0.05, limits=None, 
                 timeout=None, read_attrs=None, configuration_attrs=None,
                 monitor_attrs=None, parent=None,
                 **kwargs):
        super().__init__(prefix=prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs,
                         monitor_attrs=monitor_attrs,
                         name=name, parent=parent, timeout=timeout, **kwargs)

        if self.__class__ is PVPositioner:
            raise TypeError('PVPositioner must be subclassed with the correct '
                            'signals set in the class definition.')

        if self.done is Unspecified:
            msg = ('PVPositioner {} is mis-configured. A "done" Signal must be '
                   'provided'.format(self.name))
            raise TypeError(msg)

        self.settle_time = float(settle_time)

        if limits is not None:
            self._limits = tuple(limits)
        else:
            self._limits = None

        if self.readback is not Unspecified:
            self.readback.subscribe(self._pos_changed)
        elif self.setpoint is not Unspecified:
            self.setpoint.subscribe(self._pos_changed)
        else:
            raise TypeError('A setpoint or a readback must be specified')

        if self.done is not Unspecified:
            self.done.subscribe(self._move_changed)

    @property
    def put_complete(self):
        return isinstance(self, PVPositionerPC)

    def check_value(self, pos):
        '''Check that the position is within the soft limits'''
        low, high = self.limits
        if low != high and not (low <= pos <= high):
            raise ValueError('{} outside of user-specified limits'
                                ''.format(pos))

    @property
    def moving(self):
        '''Whether or not the motor is moving

        If a `done` PV is specified, it will be read directly to get the motion
        status. If not, it determined from the internal state of PVPositioner.

        Returns
        -------
        bool
        '''
        if self.done is not Unspecified:
            dval = self.done.get(use_monitor=False)
            return (dval != self.done_value)
        else:
            return super().moving

    def move(self, position, wait=True, moved_cb=None, timeout=None):
        try:
            if wait:
                self._started_moving = False
            self.setpoint.put(position, wait=False)

            logger.debug('Setpoint set: %s = %s',
                        self.setpoint.setpoint_pvname, position)

            if self.actuate is not Unspecifed:
                self.actuate.put(self.actuate_value, wait=False)

                logger.debug('Actuating: %s = %s',
                            self.actuate.setpoint_pvname, self.actuate_value)

            ret = super().move(position, wait=wait, moved_cb=moved_cb,
                            timeout=timeout)
            if not wait:
                self._started_moving = False
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
            logger.debug('[ts=%s] %s started moving: %s', fmt_time(timestamp),
                         self, started)

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
        if self.stop_signal is not Unspecified:
            self.stop_signal.put(self.stop_value, wait=False)
        super().stop()

    # This works for 1D Positioner that has no interactions with others.
    # Needs a re-think for more general case.

    @property
    def limits(self):
        if self._limits is not None:
            # Python limits, if set
            return tuple(self._limits)
        else:
            # EPICS limits
            return self.setpoint.limits

    @limits.setter
    def limits(self, val):
        # TODO Python limits cannot exceed EPICS limits
        # might as well raise right away
        self._limits = val

    @property
    def low_limit(self):
        return self.limits[0]

    @property
    def high_limit(self):
        return self.limits[1]

    def _repr_info(self):
        yield from super()._repr_info()

        yield ('settle_time', self.settle_time)
        yield ('limits', self._limits)


class PVPositionerPC(PVPositioner):
    done = None

    def __init__(self, prefix='', *, name=None, settle_time=0.05, limits=None, 
                 timeout=None, read_attrs=None, configuration_attrs=None,
                 monitor_attrs=None, parent=None,
                 **kwargs):

        if self.__class__ is PVPositionerPC:
            raise TypeError('PVPositionerPC must be subclassed with the '
                            'correct signals set in the class definition.')

        super().__init__(prefix=prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs,
                         monitor_attrs=monitor_attrs,
                         name=name, parent=parent, timeout=timeout, **kwargs)

        # Now that check for done has been performed by init, set to Unspeified.
        if self.done is None:
            self.done = Unspecified

    def _move_wait(self, position, **kwargs):
        '''Move and wait until motion has completed'''
        self._started_moving = False
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

    def _move_async(self, position, **kwargs):
        '''Move and do not wait until motion is complete (asynchronous)'''
        def done_moving(**kwargs):
            logger.debug('%s async motion done', self.name)
            self._done_moving()

        if self.done is None:
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
