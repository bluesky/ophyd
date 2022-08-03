import logging
import time

from .positioner import PositionerBase
from .signal import EpicsSignal
from .status import MoveStatus
from .status import wait as status_wait

logger = logging.getLogger(__name__)


class SignalPositionerMixin(PositionerBase):
    """Mixin to make a Signal a Positioner

    Should be mixed in first, with the Signal second, such that:
        set, move will be from PositionerBase

    Parameters
    ----------
    set_func : callable
        The set() functionality for the class. Must be specified as the mixin
        takes over set() functionality.
    readback_event : str, optional
        Readback value subscription event_type
    egu : str, optional
        Engineering units of positioner
    hold_on_stop : bool, optional
        When stop is called on the positioner
    """

    def __init__(
        self,
        *args,
        set_func,
        readback_event="value",
        egu="",
        hold_on_stop=False,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._egu = egu
        self._hold_on_stop = hold_on_stop
        self._internal_status = None
        self._external_status = None

        # bind method to this class instance:
        self._mixed_set = set_func.__get__(self, self.__class__)

        self.subscribe(self._position_updated, event_type=readback_event)

    def _position_updated(self, value=None, **kwargs):
        # for readback subscriptions
        self._set_position(value)

    @property
    def position(self):
        """The current position of the motor in its engineering units

        Returns
        -------
        position : any
        """
        return self.get()

    @property
    def egu(self):
        """The engineering units (EGU) for positions"""
        return self._egu

    def move(self, position, wait=True, moved_cb=None, timeout=None):
        """Move to a specified position, optionally waiting for motion to
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
        """
        if timeout is None:
            timeout = self._timeout

        self.check_value(position)

        self._run_subs(sub_type=self._SUB_REQ_DONE, success=False)
        self._reset_sub(self._SUB_REQ_DONE)

        self._moving = True
        self._run_subs(sub_type=self.SUB_START, timestamp=time.time())

        def finished(status):
            success = self._internal_status.success
            self._moving = False
            self._done_moving(success=success)

            if moved_cb is not None:
                try:
                    moved_cb(obj=self)
                except Exception as ex:
                    logger.error("Move callback failed", exc_info=ex)

            try:
                self._external_status._finished(success=success)
            except Exception as ex:
                logger.error("Status completion failed", exc_info=ex)

            self._internal_status = None
            self._external_status = None

        # this external status object is fully dependent on the internal status
        # object and does not have its own timeout/settle_time settings:
        self._external_status = MoveStatus(
            self, target=position, settle_time=0.0, timeout=None
        )

        # set() functionality depends on the signal
        self._internal_status = self._mixed_set(
            position, timeout=timeout, settle_time=self.settle_time
        )
        self._internal_status.add_callback(finished)

        if wait:
            try:
                status_wait(self._external_status)
            except RuntimeError:
                raise RuntimeError("Motion did not complete successfully")

        return self._external_status

    def stop(self, *, success=False):
        """Stops motion"""
        if self._hold_on_stop:
            self.move(self.get(), wait=False)
        # TODO status object?
        return super().stop(success=success)

    def _repr_info(self):
        yield from super()._repr_info()
        yield ("egu", self.egu)
        yield ("hold_on_stop", self._hold_on_stop)


class EpicsSignalPositioner(SignalPositionerMixin, EpicsSignal):
    def __init__(self, read_pv, **kwargs):
        super().__init__(read_pv=read_pv, set_func=EpicsSignal.set, **kwargs)
