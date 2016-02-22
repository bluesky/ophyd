# vi: ts=4 sw=4
'''
:mod:`ophyd.control.positioner` - Ophyd positioners
===================================================

.. module:: ophyd.control.positioner
   :synopsis:
'''


import logging
import time
from functools import partial

from .ophydobj import OphydObject
from .status import (MoveStatus, wait as status_wait)

logger = logging.getLogger(__name__)


class PositionerBase(OphydObject):
    '''The positioner base class

    Subclass from this to implement your own positioners.
    '''

    SUB_START = 'start_moving'
    SUB_DONE = 'done_moving'
    SUB_READBACK = 'readback'
    _SUB_REQ_DONE = '_req_done'  # requested move finished subscription
    _default_sub = SUB_READBACK

    def __init__(self, *, name=None, parent=None, **kwargs):
        super().__init__(name=name, parent=parent, **kwargs)

        self._started_moving = False
        self._moving = False
        self._position = None

    @property
    def egu(self):
        '''The engineering units (EGU) for positions'''
        raise NotImplementedError('Subclass must implement egu')

    @property
    def limits(self):
        return (0, 0)

    @property
    def low_limit(self):
        return self.limits[0]

    @property
    def high_limit(self):
        return self.limits[1]

    def move(self, position, moved_cb=None, timeout=30.0):
        '''Move to a specified position, optionally waiting for motion to
        complete.

        Parameters
        ----------
        position
            Position to move to
        moved_cb : callable
            Call this callback when movement has finished
        timeout : float, optional
            Maximum time to wait for the motion

        Returns
        -------
        status : MoveStatus

        Raises
        ------
        TimeoutError, ValueError (on invalid positions)
        '''
        self.check_value(position)

        self._run_subs(sub_type=self._SUB_REQ_DONE, success=False)
        self._reset_sub(self._SUB_REQ_DONE)

        status = MoveStatus(self, position, timeout=timeout)

        if moved_cb is not None:
            status.finished_cb = partial(moved_cb, obj=self)
            # the status object will run this callback when finished

        self.subscribe(status._finished, event_type=self._SUB_REQ_DONE,
                       run=False)

        return status

    def _done_moving(self, success=True, timestamp=None, value=None, **kwargs):
        '''Call when motion has completed.  Runs SUB_DONE subscription.'''
        if success:
            self._run_subs(sub_type=self.SUB_DONE, timestamp=timestamp,
                           value=value)

        self._run_subs(sub_type=self._SUB_REQ_DONE, success=success,
                       timestamp=timestamp)
        self._reset_sub(self._SUB_REQ_DONE)

    def stop(self):
        '''Stops motion'''
        self._done_moving(success=False)

    @property
    def position(self):
        '''The current position of the motor in its engineering units

        Returns
        -------
        position : any
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
        Bluesky-compatible API for controlling movers.

        Parameters
        ----------
        new_position : dict
            A dictionary of new positions keyed on axes name.  This is
            symmetric with read such that `mot.set(mot.read())` works as
            as expected.
        """
        return self.move(new_position, wait=wait, moved_cb=moved_cb,
                         timeout=timeout)


class SoftPositioner(PositionerBase):
    '''A positioner which does not communicate with any hardware

    SoftPositioner 'moves' immediately to the target position when commanded to
    do so.

    Parameters
    ----------
    limits : (low_limit, high_limit)
        Soft limits to use
    egu : str, optional
        Engineering units (EGU) for a position
    '''

    def __init__(self, *, egu='', limits=None, **kwargs):
        super().__init__(**kwargs)

        self._egu = egu
        if limits is None:
            limits = (0, 0)

        self._limits = tuple(limits)

    @property
    def limits(self):
        return self._limits

    @property
    def egu(self):
        '''The engineering units (EGU) for positions'''
        return self._egu

    def move(self, position, wait=True, timeout=30.0, moved_cb=None):
        '''Move to a specified position, optionally waiting for motion to
        complete.

        Parameters
        ----------
        position
            Position to move to
        moved_cb : callable
            Call this callback when movement has finished
        wait : bool, optional
            Wait until motion has completed
        timeout : float, optional
            Maximum time to wait for a motion

        Returns
        -------
        status : MoveStatus

        Raises
        ------
        TimeoutError, ValueError (on invalid positions)
        '''
        # A soft positioner immediately 'moves' to the target position when
        # requested.
        self._started_moving = True
        self._moving = False
        self._run_subs(sub_type=self.SUB_START, timestamp=time.time())

        status = super().move(position, moved_cb=moved_cb, timeout=timeout)

        self._set_position(position)
        self._done_moving()

        if wait:
            try:
                status_wait(status)
            except RuntimeError:
                raise RuntimeError('Motion did not complete successfully')

        return status

    def _repr_info(self):
        yield from super()._repr_info()
        yield ('egu', self._egu)
        yield ('limits', self._limits)
