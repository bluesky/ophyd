# vi: ts=4 sw=4

import logging

from .utils.epics_pvs import fmt_time

from .device import (Device, required_for_connection)
from .ophydobj import Kind
from .positioner import PositionerBase
from .status import wait as status_wait

logger = logging.getLogger(__name__)


class PVPositioner(Device, PositionerBase):
    '''A Positioner which is controlled using multiple user-defined signals

    Keyword arguments are passed through to the base class, Positioner

    Parameters
    ----------
    prefix : str, optional
        The device prefix used for all sub-positioners. This is optional as it
        may be desirable to specify full PV names for PVPositioners.
    limits : 2-element sequence, optional
        (low_limit, high_limit)
    name : str
        The device name
    egu : str, optional
        The engineering units (EGU) for the position
    settle_time : float, optional
        The amount of time to wait after moves to report status completion
    timeout : float, optional
        The default timeout to use for motion requests, in seconds.

    Attributes
    ----------
    setpoint : Signal
        The setpoint (request) signal
    readback : Signal or None
        The readback PV (e.g., encoder position PV)
    actuate : Signal or None
        The actuation PV to set when movement is requested
    actuate_value : any, optional
        The actuation value, sent to the actuate signal when motion is
        requested
    stop_signal : Signal or None
        The stop PV to set when motion should be stopped
    stop_value : any, optional
        The value sent to stop_signal when a stop is requested
    done : Signal
        A readback value indicating whether motion is finished
    done_value : any, optional
        The value that the done pv should be when motion has completed
    put_complete : bool, optional
        If set, the specified PV should allow for asynchronous put completion
        to indicate motion has finished.  If `actuate` is specified, it will be
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

    def __init__(self, prefix='', *, limits=None, name=None, read_attrs=None,
                 configuration_attrs=None, parent=None, egu='', **kwargs):
        super().__init__(prefix=prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs,
                         name=name, parent=parent, **kwargs)

        if self.__class__ is PVPositioner:
            raise TypeError('PVPositioner must be subclassed with the correct '
                            'signals set in the class definition.')

        self._egu = egu

        if limits is not None:
            self._limits = tuple(limits)
        else:
            self._limits = None

        if self.readback is not None:
            self.readback.subscribe(self._pos_changed)
            self.readback.kind = Kind.hinted
        elif self.setpoint is not None:
            self.setpoint.subscribe(self._pos_changed)
        else:
            raise ValueError('A setpoint or a readback must be specified')

        if self.done is None and not self.put_complete:
            msg = ('PVPositioner {} is mis-configured. A "done" Signal must be'
                   ' provided or use PVPositionerPC (which uses put completion'
                   ' to determine when motion has completed).'
                   ''.format(self.name))
            raise ValueError(msg)

        if self.done is not None:
            self.done.subscribe(self._move_changed)
        else:
            # If there is not a `move_changed` signal, indicate that the
            # positioner is not moving frm the start:
            self._move_changed(value=self.done_value)

    @property
    def egu(self):
        '''The engineering units (EGU) for a position'''
        return self._egu

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

    def _setup_move(self, position):
        '''Move and do not wait until motion is complete (asynchronous)'''
        self.log.debug('%s.setpoint = %s', self.name, position)
        self.setpoint.put(position, wait=True)
        if self.actuate is not None:
            self.log.debug('%s.actuate = %s', self.name, self.actuate_value)
            self.actuate.put(self.actuate_value, wait=False)

    def move(self, position, wait=True, timeout=None, moved_cb=None):
        '''Move to a specified position, optionally waiting for motion to
        complete.

        Parameters
        ----------
        position
            Position to move to
        moved_cb : callable
            Call this callback when movement has finished. This callback must
            accept one keyword argument: 'obj' which will be set to this
            positioner instance.
        timeout : float, optional
            Maximum time to wait for the motion. If None, the default timeout
            for this positioner is used.

        Returns
        -------
        status : MoveStatus

        Raises
        ------
        TimeoutError
            When motion takes longer than `timeout`
        ValueError
            On invalid positions
        RuntimeError
            If motion fails other than timing out
        '''
        # Before moving, ensure we can stop (if a stop_signal is configured).
        if self.stop_signal is not None:
            self.stop_signal.wait_for_connection()
        status = super().move(position, timeout=timeout, moved_cb=moved_cb)

        has_done = self.done is not None
        if not has_done:
            moving_val = 1 - self.done_value
            self._move_changed(value=self.done_value)
            self._move_changed(value=moving_val)

        try:
            self._setup_move(position)
            if wait:
                status_wait(status)
        except KeyboardInterrupt:
            self.stop()
            raise

        return status

    @required_for_connection
    def _move_changed(self, timestamp=None, value=None, sub_type=None,
                      **kwargs):
        was_moving = self._moving
        self._moving = (value != self.done_value)

        started = False
        if not self._started_moving:
            started = self._started_moving = (not was_moving and self._moving)
            self.log.debug('[ts=%s] %s started moving: %s', fmt_time(timestamp),
                           self.name, started)

        self.log.debug('[ts=%s] %s moving: %s (value=%s)', fmt_time(timestamp),
                       self.name, self._moving, value)

        if started:
            self._run_subs(sub_type=self.SUB_START, timestamp=timestamp,
                           value=value, **kwargs)

        if not self.put_complete:
            # In the case of put completion, motion complete
            if was_moving and not self._moving:
                self._done_moving(success=True, timestamp=timestamp,
                                  value=value)

    @required_for_connection
    def _pos_changed(self, timestamp=None, value=None, **kwargs):
        '''Callback from EPICS, indicating a change in position'''
        self._set_position(value)

    def stop(self, *, success=False):
        if self.stop_signal is not None:
            self.stop_signal.put(self.stop_value, wait=False)
        super().stop(success=success)

    @property
    def report(self):
        rep = super().report
        rep['pv'] = self.readback.pvname
        return rep

    @property
    def limits(self):
        if self._limits is not None:
            return tuple(self._limits)
        else:
            return self.setpoint.limits

    def _repr_info(self):
        yield from super()._repr_info()

        yield ('limits', self._limits)
        yield ('egu', self._egu)

    def _done_moving(self, **kwargs):
        has_done = self.done is not None
        if not has_done:
            self._move_changed(value=self.done_value)

        super()._done_moving(**kwargs)


class PVPositionerPC(PVPositioner):
    def __init__(self, *args, **kwargs):
        if self.__class__ is PVPositionerPC:
            raise TypeError('PVPositionerPC must be subclassed with the '
                            'correct signals set in the class definition.')

        super().__init__(*args, **kwargs)

    def _setup_move(self, position):
        '''Move and do not wait until motion is complete (asynchronous)'''
        def done_moving(**kwargs):
            self.log.debug('%s async motion done', self.name)
            self._done_moving(success=True)

        if self.done is None:
            # No done signal, so we rely on put completion
            moving_val = 1 - self.done_value
            self._move_changed(value=moving_val)

        self.log.debug('%s.setpoint = %s', self.name, position)

        if self.actuate is not None:
            self.setpoint.put(position, wait=True)

            self.log.debug('%s.actuate = %s', self.name, self.actuate_value)
            self.actuate.put(self.actuate_value, wait=False,
                             callback=done_moving)
        else:
            self.setpoint.put(position, wait=False,
                              callback=done_moving)
