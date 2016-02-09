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
from .device import Device
from .positioner import Positioner


logger = logging.getLogger(__name__)


class PVPositioner(Device, Positioner):
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
            msg = ('PVPositioner %s is mis-configured. A "done" Signal must be '
                   'provided or use PVPositionerPC (which uses put completion '
                   'to determine when motion has completed).'
                   ''.format(self.name))
            raise ValueError(msg)

        if self.done is not None:
            self.done.subscribe(self._move_changed)

    @property
    def put_complete(self):
        return isinstance(self, PVPositionerPC)

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

    def _move_wait(self, position, **kwargs):
        '''Move and wait until motion has completed'''
        self._started_moving = False

        self.setpoint.put(position, wait=True)
        logger.debug('Setpoint set: %s = %s',
                     self.setpoint.setpoint_pvname, position)

        if self.actuate is not None:
            self.actuate.put(self.actuate_value, wait=True)
            logger.debug('Actuating: %s = %s',
                         self.actuate.setpoint_pvname, self.actuate_value)

    def _move_async(self, position, **kwargs):
        '''Move and do not wait until motion is complete (asynchronous)'''
        if self.actuate is not None:
            self.setpoint.put(position, wait=True)
            self.actuate.put(self.actuate_value, wait=False)
        else:
            self.setpoint.put(position, wait=False)

    def move(self, position, wait=True, **kwargs):
        try:
            if wait:
                self._move_wait(position, **kwargs)
                return super().move(position, wait=True, **kwargs)
            else:
                # Setup the async retval first
                ret = super().move(position, wait=False, **kwargs)
                self._started_moving = False
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
        if self.stop_signal is not None:
            self.stop_signal.put(self.stop_value, wait=False)
        super().stop()

    @property
    def report(self):
        return {self.name: self.position, 'pv': self.readback.pvname}

    @property
    def limits(self):
        if self._limits is not None:
            return tuple(self._limits)
        else:
            return self.setpoint.limits

    def _repr_info(self):
        yield from super()._repr_info()

        yield ('settle_time', self.settle_time)
        yield ('limits', self._limits)


class PVPositionerPC(PVPositioner):
    def __init__(self, *args, **kwargs):
        if self.__class__ is PVPositionerPC:
            raise TypeError('PVPositionerPC must be subclassed with the '
                            'correct signals set in the class definition.')

        super().__init__(*args, **kwargs)

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
