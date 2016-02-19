# vi: ts=4 sw=4
'''
:mod:`ophyd.control.positioner` - Ophyd positioners
===================================================

.. module:: ophyd.control.positioner
   :synopsis:
'''


import logging
import time

from .utils import TimeoutError
from .utils.epics_pvs import (data_type, data_shape)
from .ophydobj import (MoveStatus, OphydObject)


logger = logging.getLogger(__name__)


class Positioner(OphydObject):
    '''A soft positioner.

    Subclass from this to implement your own positioners.
    '''

    SUB_START = 'start_moving'
    SUB_DONE = 'done_moving'
    SUB_READBACK = 'readback'
    _SUB_REQ_DONE = '_req_done'  # requested move finished subscription
    _default_sub = SUB_READBACK

    def __init__(self, *, timeout=None, egu=None, name=None, parent=None,
                 **kwargs):
        super().__init__(name=name, parent=parent, **kwargs)

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

    def describe(self):
        """Return the description as a dictionary

        Returns
        -------
        dict
            Dictionary of name and formatted description string
        """
        desc = {'source': 'SIM:{}'.format(self.name), }

        val = self.position
        desc['dtype'] = data_type(val)
        desc['shape'] = data_shape(val)

        desc['units'] = self.egu if len(self.egu) > 0 else str(None)

        desc['lower_ctrl_limit'] = self.low_limit
        desc['upper_ctrl_limit'] = self.high_limit

        return {self.name: desc}

    def read(self):
        """Read the signal and format for data collection

        Returns
        -------
        dict
            Dictionary of value timestamp pairs
        """

        return {self.name: {'value': self.position,
                            'timestamp': time.time()}}

    def _repr_info(self):
        yield from super()._repr_info()
        yield ('egu', self._egu)
        yield ('timeout', self._timeout)
