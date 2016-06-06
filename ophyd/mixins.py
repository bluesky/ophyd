from .signal import EpicsSignal
from .positioner import PositionerBase
from .status import wait as status_wait


class SignalPositionerMixin(PositionerBase):
    '''Mixin to make a Signal a Positioner

    Should be mixed in first, with the Signal second, such that:
        set, move will be from PositionerBase

    Parameters
    ----------
    set_func : callable
        The set() functionality for the class. Must be specified as the mixin
        takes over set() functionality.
    egu : str, optional
        Engineering units of positioner
    hold_on_stop : bool, optional
        When stop is called on the positioner
    '''
    def __init__(self, *args, set_func, egu='', hold_on_stop=False, **kwargs):
        super().__init__(*args, **kwargs)
        self._egu = egu
        self._hold_on_stop = hold_on_stop
        self._status = None

        # bind method to this class instance:
        self._mixed_set = set_func.__get__(self, self.__class__)

        self.subscribe(self._position_updated)

    def _position_updated(self, value=None, **kwargs):
        # for readback subscriptions
        self._set_position(value)

    @property
    def position(self):
        '''The current position of the motor in its engineering units

        Returns
        -------
        position : any
        '''
        return self.get()

    @property
    def egu(self):
        '''The engineering units (EGU) for positions'''
        return self._egu

    def move(self, position, wait=True, moved_cb=None, timeout=None):
        '''Move to a specified position, optionally waiting for motion to
        complete.

        Parameters
        ----------
        position
            Position to move to
        wait : bool, optional
            Wait until motion has completed before returning
        moved_cb : callable
            Call this callback when movement has finished. This callback
            must accept one keyword argument: 'obj' which will be set to
            this positioner instance.
        timeout : float, optional
            Maximum time to wait for the motion. If None, the default timeout
            for this positioner is used.

        Returns
        -------
        status : Status

        Raises
        ------
        TimeoutError
            When motion takes longer than `timeout`
        ValueError
            On invalid positions
        RuntimeError
            If motion fails other than timing out
        '''
        if timeout is None:
            timeout = self._timeout

        self.check_value(position)

        self._run_subs(sub_type=self._SUB_REQ_DONE, success=False)
        self._reset_sub(self._SUB_REQ_DONE)

        self._moving = True
        self._run_subs(sub_type=self.SUB_START)

        def finished():
            self._done_moving(success=self._status.success)

            if moved_cb is not None:
                moved_cb(obj=self)

            self._status = None

        # set() functionality depends on the signal
        self._status = self._mixed_set(position, timeout=timeout,
                                       settle_time=self.settle_time)
        self._status.finished_cb = finished

        if wait:
            try:
                status_wait(self._status)
            except RuntimeError:
                raise RuntimeError('Motion did not complete successfully')

        return self._status

    def stop(self):
        '''Stops motion'''
        if self._hold_on_stop:
            self.move(self.get(), wait=False)
        # TODO status object?
        return super().stop()

    def _repr_info(self):
        yield from super()._repr_info()
        yield ('egu', self.egu)
        yield ('hold_on_stop', self._hold_on_stop)


class EpicsSignalPositioner(SignalPositionerMixin, EpicsSignal):
    def __init__(self, read_pv, **kwargs):
        super().__init__(read_pv=read_pv, set_func=EpicsSignal.set, **kwargs)
