import functools
import logging
import time
from collections import OrderedDict
from typing import Any, Callable

from .ophydobj import Kind, OphydObject
from .status import MoveStatus, StatusBase
from .status import wait as status_wait
from .utils.epics_pvs import data_shape, data_type
from .utils.errors import LimitError

logger = logging.getLogger(__name__)


class PositionerBase(OphydObject):
    """The positioner base class

    Subclass from this to implement your own positioners.

    .. note ::

       Subclasses should add an additional 'wait' keyword argument on
       the move method. The `MoveStatus` object returned from
       `PositionerBase` can then be waited on after the subclass
       finishes the motion configuration.

    """

    SUB_START = "start_moving"
    SUB_DONE = "done_moving"
    SUB_READBACK = "readback"
    _SUB_REQ_DONE = "_req_done"  # requested move finished subscription
    _default_sub = SUB_READBACK

    def __init__(
        self, *, name=None, parent=None, settle_time=0.0, timeout=None, **kwargs
    ):
        super().__init__(name=name, parent=parent, **kwargs)

        self._started_moving = False
        self._moving = False
        self._position = None
        self._settle_time = settle_time
        self._timeout = timeout

    # High level
    def set(
        self,
        new_position: Any,
        *,
        timeout: float = None,
        moved_cb: Callable = None,
        wait: bool = False,
    ) -> StatusBase:
        """Set a value and return a Status object


        Parameters
        ----------
        new_position : object

            The input here is whatever the device requires (this
            should be over-ridden by the implementation.  For example
            a motor would take a float, a shutter the strings {'Open',
            'Close'}, and a goineometer (h, k, l) tuples

        timeout : float, optional

            Maximum time to wait for the motion. If None, the default timeout
            for this positioner is used.

        moved_cb : callable, optional
            Deprecated

            Call this callback when movement has finished. This callback
            must accept one keyword argument: 'obj' which will be set to
            this positioner instance.

        wait : bool, optional
            Deprecated

            If the method should block until the Status object reports
            it is done.

            Defaults to False

        Returns
        -------
        status : StatusBase
            Status object to indicate when the motion / set is done.
        """
        return self.move(new_position, wait=wait, moved_cb=moved_cb, timeout=timeout)

    def stop(self, *, success: bool = False):
        """Stops motion.

        Sub-classes must extend this method to _actually_ stop the device.

        Parameters
        ----------
        success : bool, optional
            If the move should be considered a success despite the stop.

            Defaults to False
        """
        self._done_moving(success=success)

    # Suggested properties
    @property
    def settle_time(self):
        """Amount of time to wait after moves to report status completion"""
        return self._settle_time

    @settle_time.setter
    def settle_time(self, settle_time):
        self._settle_time = settle_time

    @property
    def timeout(self):
        """Amount of time to wait before to considering a motion as failed"""
        return self._timeout

    @timeout.setter
    def timeout(self, timeout):
        if timeout is None:
            self._timeout = None
        else:
            self._timeout = float(timeout)

    # low level
    @property
    def report(self):
        rep = super().report
        rep["position"] = self.position
        return rep

    @property
    def egu(self):
        """The engineering units (EGU) for positions"""
        raise NotImplementedError("Subclass must implement egu")

    @property
    def limits(self):
        return (0, 0)

    @property
    def low_limit(self):
        return self.limits[0]

    @property
    def high_limit(self):
        return self.limits[1]

    def move(self, position, moved_cb=None, timeout=None):
        """Move to a specified position, optionally waiting for motion to
        complete.

        Parameters
        ----------
        position
            Position to move to
        moved_cb : callable
            Call this callback when movement has finished. This callback
            must accept one keyword argument: 'obj' which will be set to
            this positioner instance. It should also accept a positional
            argument 'status', the Status object.

            .. versionchanged:: 1.5.0

               The expected signature changed from ``moved_cb(*, obj)`` to
               ``moved_cb(status, *, obj)``. The old signature is still
               supported, but a warning will be issued.

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
        """

        if timeout is None:
            timeout = self._timeout

        self.check_value(position)

        self._run_subs(sub_type=self._SUB_REQ_DONE, success=False)
        self._reset_sub(self._SUB_REQ_DONE)

        status = MoveStatus(
            self, position, timeout=timeout, settle_time=self._settle_time
        )

        if moved_cb is not None:
            status.add_callback(functools.partial(moved_cb, obj=self))
            # the status object will run this callback when finished

        self.subscribe(status._finished, event_type=self._SUB_REQ_DONE, run=False)

        return status

    def _done_moving(self, success=True, timestamp=None, value=None, **kwargs):
        """Call when motion has completed.  Runs ``SUB_DONE`` subscription."""
        if success:
            self._run_subs(sub_type=self.SUB_DONE, timestamp=timestamp, value=value)

        self._run_subs(
            sub_type=self._SUB_REQ_DONE, success=success, timestamp=timestamp
        )
        self._reset_sub(self._SUB_REQ_DONE)

    @property
    def position(self):
        """The current position of the motor in its engineering units

        Returns
        -------
        position : any
        """
        return self._position

    def _set_position(self, value, **kwargs):
        """Set the current internal position, run the readback subscription"""
        self._position = value

        timestamp = kwargs.pop("timestamp", time.time())
        self._run_subs(
            sub_type=self.SUB_READBACK, timestamp=timestamp, value=value, **kwargs
        )

    @property
    def moving(self):
        """Whether or not the motor is moving

        Returns
        -------
        moving : bool
        """
        return self._moving

    def _repr_info(self):
        yield from super()._repr_info()
        yield ("settle_time", self._settle_time)
        yield ("timeout", self._timeout)

    @property
    def hints(self):
        if (~Kind.normal & Kind.hinted) & self.kind:
            return {"fields": [self.name]}
        else:
            return {"fields": []}


class SoftPositioner(PositionerBase):
    """A positioner which does not communicate with any hardware

    SoftPositioner 'moves' immediately to the target position when commanded to
    do so.

    Parameters
    ----------
    limits : (low_limit, high_limit)
        Soft limits to use
    egu : str, optional
        Engineering units (EGU) for a position
    source : str, optional
        Metadata indicating the source of this positioner's position. Defaults
        to 'computed'
    init_pos : float, optional
        Create the positioner with this starting position.  Defaults to ``None``.
    """

    def __init__(
        self, *, egu="", limits=None, source="computed", init_pos=None, **kwargs
    ):
        super().__init__(**kwargs)

        self._egu = egu
        if limits is None:
            limits = (0, 0)

        self._limits = tuple(limits)
        self.source = source
        if init_pos is not None:
            self.set(init_pos)

    @property
    def limits(self):
        return self._limits

    @property
    def egu(self):
        """The engineering units (EGU) for positions"""
        return self._egu

    def _setup_move(self, position, status):
        """Move requested to position

        This is a SoftPositioner method which allows customization of what
        happens when a motion request happens without re-implementing
        all of `move`.

        Parameters
        ----------
        position : any
            Position to move to (already verified by `check_value`)
        status : MoveStatus
            Status object created by PositionerBase.move()
        """
        # A soft positioner immediately 'moves' to the target position when
        # requested.
        self._run_subs(sub_type=self.SUB_START, timestamp=time.time())

        self._started_moving = True
        self._moving = False

        self._set_position(position)
        self._done_moving()

    def move(self, position, wait=True, timeout=None, moved_cb=None):
        """Move to a specified position, optionally waiting for motion to
        complete.

        Parameters
        ----------
        position
            Position to move to
        moved_cb : callable
            Call this callback when movement has finished. This callback
            must accept one keyword argument: 'obj' which will be set to
            this positioner instance.
        wait : bool, optional
            Wait until motion has completed
        timeout : float, optional
            Maximum time to wait for a motion

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
        """
        status = super().move(position, moved_cb=moved_cb, timeout=timeout)

        self._setup_move(position, status)

        if wait:
            try:
                status_wait(status)
            except RuntimeError:
                raise RuntimeError("Motion did not complete successfully")

        return status

    def _repr_info(self):
        yield from super()._repr_info()
        yield ("egu", self._egu)
        yield ("limits", self._limits)
        yield ("source", self.source)

    def read(self):
        d = OrderedDict()
        d[self.name] = {"value": self.position, "timestamp": time.time()}
        return d

    def describe(self):
        """Return the description as a dictionary

        Returns
        -------
        dict
            Dictionary of name and formatted description string
        """
        desc = OrderedDict()
        desc[self.name] = {
            "source": str(self.source),
            "dtype": data_type(self.position),
            "shape": data_shape(self.position),
            "units": self.egu,
            "lower_ctrl_limit": self.low_limit,
            "upper_ctrl_limit": self.high_limit,
        }
        return desc

    def read_configuration(self):
        return OrderedDict()

    def describe_configuration(self):
        return OrderedDict()

    def check_value(self, pos):
        """Check that the position is within the soft limits"""
        low_limit, high_limit = self.limits

        if low_limit < high_limit and not (low_limit <= pos <= high_limit):
            raise LimitError(f"position={pos} not within limits {self.limits}")
