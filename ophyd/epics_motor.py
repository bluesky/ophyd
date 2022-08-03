import logging
from enum import Enum

from .device import Component as Cpt
from .device import Device, required_for_connection
from .positioner import PositionerBase
from .signal import EpicsSignal, EpicsSignalRO
from .status import wait as status_wait
from .utils import DisconnectedError
from .utils.epics_pvs import AlarmSeverity, fmt_time, raise_if_disconnected

logger = logging.getLogger(__name__)


class HomeEnum(str, Enum):
    forward = "forward"
    reverse = "reverse"


class EpicsMotor(Device, PositionerBase):
    """An EPICS motor record, wrapped in a :class:`Positioner`

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
    settle_time : float, optional
        The amount of time to wait after moves to report status completion
    timeout : float, optional
        The default timeout to use for motion requests, in seconds.
    """

    # position
    user_readback = Cpt(EpicsSignalRO, ".RBV", kind="hinted", auto_monitor=True)
    user_setpoint = Cpt(EpicsSignal, ".VAL", limits=True, auto_monitor=True)

    # calibration dial <-> user
    user_offset = Cpt(EpicsSignal, ".OFF", kind="config", auto_monitor=True)
    user_offset_dir = Cpt(EpicsSignal, ".DIR", kind="config", auto_monitor=True)
    offset_freeze_switch = Cpt(EpicsSignal, ".FOFF", kind="omitted", auto_monitor=True)
    set_use_switch = Cpt(EpicsSignal, ".SET", kind="omitted", auto_monitor=True)

    # configuration
    velocity = Cpt(EpicsSignal, ".VELO", kind="config", auto_monitor=True)
    acceleration = Cpt(EpicsSignal, ".ACCL", kind="config", auto_monitor=True)
    motor_egu = Cpt(EpicsSignal, ".EGU", kind="config", auto_monitor=True)

    # motor status
    motor_is_moving = Cpt(EpicsSignalRO, ".MOVN", kind="omitted", auto_monitor=True)
    motor_done_move = Cpt(EpicsSignalRO, ".DMOV", kind="omitted", auto_monitor=True)
    high_limit_switch = Cpt(EpicsSignalRO, ".HLS", kind="omitted", auto_monitor=True)
    low_limit_switch = Cpt(EpicsSignalRO, ".LLS", kind="omitted", auto_monitor=True)
    high_limit_travel = Cpt(EpicsSignal, ".HLM", kind="omitted", auto_monitor=True)
    low_limit_travel = Cpt(EpicsSignal, ".LLM", kind="omitted", auto_monitor=True)
    direction_of_travel = Cpt(EpicsSignal, ".TDIR", kind="omitted", auto_monitor=True)

    # commands
    motor_stop = Cpt(EpicsSignal, ".STOP", kind="omitted")
    home_forward = Cpt(EpicsSignal, ".HOMF", kind="omitted")
    home_reverse = Cpt(EpicsSignal, ".HOMR", kind="omitted")

    # alarm information
    tolerated_alarm = AlarmSeverity.NO_ALARM

    def __init__(
        self,
        prefix="",
        *,
        name,
        kind=None,
        read_attrs=None,
        configuration_attrs=None,
        parent=None,
        **kwargs
    ):
        super().__init__(
            prefix=prefix,
            name=name,
            kind=kind,
            read_attrs=read_attrs,
            configuration_attrs=configuration_attrs,
            parent=parent,
            **kwargs
        )

        # Make the default alias for the user_readback the name of the
        # motor itself.
        self.user_readback.name = self.name

        def on_limit_changed(value, old_value, **kwargs):
            """
            update EpicsSignal object when a limit CA monitor received from EPICS
            """
            if self.connected and old_value is not None and value != old_value:
                self.user_setpoint._metadata_changed(
                    self.user_setpoint.pvname,
                    self.user_setpoint._read_pv.get_ctrlvars(),
                    from_monitor=True,
                    update=True,
                )

        self.low_limit_travel.subscribe(on_limit_changed)
        self.high_limit_travel.subscribe(on_limit_changed)

    @property
    def precision(self):
        """The precision of the readback PV, as reported by EPICS"""
        return self.user_readback.precision

    @property
    def egu(self):
        """The engineering units (EGU) for a position"""
        return self.motor_egu.get()

    @property
    @raise_if_disconnected
    def limits(self):
        return self.user_setpoint.limits

    @property
    @raise_if_disconnected
    def moving(self):
        """Whether or not the motor is moving

        Returns
        -------
        moving : bool
        """
        return bool(self.motor_is_moving.get(use_monitor=False))

    @raise_if_disconnected
    def stop(self, *, success=False):
        self.motor_stop.put(1, wait=False)
        super().stop(success=success)

    @raise_if_disconnected
    def move(self, position, wait=True, **kwargs):
        """Move to a specified position, optionally waiting for motion to
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
        """
        self._started_moving = False

        status = super().move(position, **kwargs)
        self.user_setpoint.put(position, wait=False)
        try:
            if wait:
                status_wait(status)
        except KeyboardInterrupt:
            self.stop()
            raise

        return status

    @property
    @raise_if_disconnected
    def position(self):
        """The current position of the motor in its engineering units

        Returns
        -------
        position : float
        """
        return self._position

    @raise_if_disconnected
    def set_current_position(self, pos):
        """Configure the motor user position to the given value

        Parameters
        ----------
        pos
           Position to set.

        """
        self.set_use_switch.put(1, wait=True)
        try:
            self.user_setpoint.put(pos, wait=True, force=True)
        finally:
            self.set_use_switch.put(0, wait=True)

    @raise_if_disconnected
    def home(self, direction, wait=True, **kwargs):
        """Perform the default homing function in the desired direction

        Parameters
        ----------
        direction : HomeEnum
           Direction in which to perform the home search.
        """
        direction = HomeEnum(direction)

        self._started_moving = False
        position = (self.low_limit + self.high_limit) / 2
        status = super().move(position, **kwargs)

        if direction == HomeEnum.forward:
            self.home_forward.put(1, wait=False)
        else:
            self.home_reverse.put(1, wait=False)

        try:
            if wait:
                status_wait(status)
        except KeyboardInterrupt:
            self.stop()
            raise

        return status

    def check_value(self, pos):
        """Check that the position is within the soft limits"""
        self.user_setpoint.check_value(pos)

    @required_for_connection
    @user_readback.sub_value
    def _pos_changed(self, timestamp=None, value=None, **kwargs):
        """Callback from EPICS, indicating a change in position"""
        self._set_position(value)

    @required_for_connection
    @motor_done_move.sub_value
    def _move_changed(self, timestamp=None, value=None, sub_type=None, **kwargs):
        """Callback from EPICS, indicating that movement status has changed"""
        was_moving = self._moving
        self._moving = value != 1

        started = False
        if not self._started_moving:
            started = self._started_moving = not was_moving and self._moving

        self.log.debug(
            "[ts=%s] %s moving: %s (value=%s)",
            fmt_time(timestamp),
            self,
            self._moving,
            value,
        )

        if started:
            self._run_subs(
                sub_type=self.SUB_START, timestamp=timestamp, value=value, **kwargs
            )

        if was_moving and not self._moving:
            success = True
            # Check if we are moving towards the low limit switch
            if self.direction_of_travel.get() == 0:
                if self.low_limit_switch.get(use_monitor=False) == 1:
                    success = False
            # No, we are going to the high limit switch
            else:
                if self.high_limit_switch.get(use_monitor=False) == 1:
                    success = False

            # Check the severity of the alarm field after motion is complete.
            # If there is any alarm at all warn the user, and if the alarm is
            # greater than what is tolerated, mark the move as unsuccessful
            severity = self.user_readback.alarm_severity

            if severity != AlarmSeverity.NO_ALARM:
                status = self.user_readback.alarm_status
                if severity > self.tolerated_alarm:
                    self.log.error(
                        "Motion failed: %s is in an alarm state "
                        "status=%s severity=%s",
                        self.name,
                        status,
                        severity,
                    )
                    success = False
                else:
                    self.log.warning(
                        "Motor %s raised an alarm during motion "
                        "status=%s severity %s",
                        self.name,
                        status,
                        severity,
                    )
            self._done_moving(success=success, timestamp=timestamp, value=value)

    @property
    def report(self):
        try:
            rep = super().report
        except DisconnectedError:
            # TODO there might be more in this that gets lost
            rep = {"position": "disconnected"}
        rep["pv"] = self.user_readback.pvname
        return rep

    def get_lim(self, flag):
        """
        Returns the travel limit of motor

        * flag > 0: returns high limit
        * flag < 0: returns low limit
        * flag == 0: returns None

        Included here for compatibility with similar with SPEC command.

        Parameters
        ----------
        high : float
           Limit of travel in the positive direction.
        low : float
           Limit of travel in the negative direction.
        """
        if flag > 0:
            return self.high_limit_travel.get()
        elif flag < 0:
            return self.low_limit_travel.get()

    def set_lim(self, low, high):
        """
        Sets the low and high travel limits of motor

        * No action taken if motor is moving.
        * Low limit is set to lesser of (low, high)
        * High limit is set to greater of (low, high)

        Included here for compatibility with similar with SPEC command.

        Parameters
        ----------
        high : float
           Limit of travel in the positive direction.
        low : float
           Limit of travel in the negative direction.
        """
        if not self.moving:
            # update EPICS
            lo = min(low, high)
            hi = max(low, high)
            if lo <= self.position <= hi:
                self.high_limit_travel.put(hi)
                self.low_limit_travel.put(lo)
                # and ophyd metadata dictionary will update via CA monitor
            else:
                self.log.debug(
                    "Could not set motor limits to (%f, %f) at position %g",
                    low,
                    high,
                    self.position,
                )


class MotorBundle(Device):
    """Sub-class this to device a bundle of motors

    This provides better default behavior for :ref:``hints``.
    """

    ...
