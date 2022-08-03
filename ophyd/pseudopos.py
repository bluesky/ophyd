# vi: ts=4 sw=4


import functools
import logging
import math
import threading
import time
from collections import OrderedDict, namedtuple
from collections.abc import Mapping, Sequence

from .device import Component as Cpt
from .device import Device, Kind, required_for_connection
from .positioner import PositionerBase, SoftPositioner
from .signal import AttributeSignal
from .utils import DisconnectedError, ExceptionBundle

logger = logging.getLogger(__name__)


class PseudoSingle(Device, SoftPositioner):
    """A single axis of a PseudoPositioner

    This should not be instantiated on its own, but rather used as a Component
    in a PseudoPositioner subclass.

    Parameters
    ----------
    prefix : str, optional
        The PV prefix, for compatibility with the Device hierarchy
    limits : (low_limit, high_limit)
        User-defined limits for this pseudo axis.
    egu : str, optional
        The engineering units (EGU) for the position
    parent : PseudoPositioner instance
        The instance of the parent PseudoPositioner
    name : str, optional
        The name of the positioner
    source : str, optional
        Metadata indicating the source of this positioner's position. Defaults
        to 'computed'
    target_initial_position : bool, optional
        Use initial inverse-calculated position as the default setpoint/target
        for this axis
    settle_time : float, optional
        The amount of time to wait after moves to report status completion
    timeout : float, optional
        The default timeout to use for motion requests, in seconds.
    """

    readback = Cpt(AttributeSignal, attr="position", kind=Kind.hinted)
    setpoint = Cpt(AttributeSignal, attr="target", kind=Kind.normal)

    def __init__(
        self,
        prefix="",
        *,
        limits=None,
        egu="",
        parent=None,
        name=None,
        source="computed",
        target_initial_position=False,
        **kwargs,
    ):

        super().__init__(
            prefix=prefix,
            name=name,
            parent=parent,
            limits=limits,
            egu=egu,
            source=source,
            **kwargs,
        )
        # the readback name should default to the name of the positioner
        self.readback.name = self.name

        self._target_initial_position = target_initial_position
        self._target = None

        # The index of this PseudoSingle in the parent PseudoPositioner tuple
        # will be set post-instantiation:
        self._idx = None
        self._parent.subscribe(self._sub_proxy_start, event_type=self.SUB_START)
        self._parent.subscribe(self._sub_proxy_done, event_type=self.SUB_DONE)
        self._parent.subscribe(self._sub_proxy_readback, event_type=self.SUB_READBACK)

    def _repr_info(self):
        yield from super()._repr_info()
        yield ("idx", self._idx)

    def _sub_proxy_start(self, obj=None, **kwargs):
        "Pass through parent callbacks for motion started"
        return self._run_subs(obj=self, **kwargs)

    def _sub_proxy_done(self, obj=None, **kwargs):
        "Pass through parent callbacks for motion started"
        return self._run_subs(obj=self, **kwargs)

    @required_for_connection(description="{device.name} readback subscription")
    def _sub_proxy_readback(self, obj=None, value=None, **kwargs):
        """Parent callbacks including a position value will be filtered through
        this function and re-broadcast using only the relevant position to this
        pseudo axis.
        """
        if hasattr(value, "__getitem__"):
            value = value[self._idx]

        return self._run_subs(obj=self, value=value, **kwargs)

    @property
    def target(self):
        """Last commanded target position"""
        if self._target is None:
            return self.position
        else:
            return self._target

    def sync(self):
        """Synchronize target position with current readback position"""
        self._target = None

    def check_value(self, pos):
        self._parent.check_single(self, pos)

    @property
    def moving(self):
        return self._parent.moving

    @property
    def position(self):
        """The current position of the motor in its engineering units

        Returns
        -------
        position
        """
        return self._parent.position[self._idx]

    def stop(self, *, success=False):
        """Stop motion on the PseudoPositioner"""
        return self._parent.stop(success=success)

    @property
    def _started_moving(self):
        """Has motion started since the motion request?

        This is a property on PseudoSingle, which overrides the default
        behavior of Positioner. It reflects the motion status of the
        PseudoPositioner as a whole.
        """
        return self._parent._started_moving

    @_started_moving.setter
    def _started_moving(self, value):
        # Don't allow the base class to specify whether it has started moving
        pass

    def _setup_move(self, position, status):
        """PseudoSingle.move overrides SoftPositioner move implementation, so
        this method is not called.
        """
        pass

    def move(self, pos, **kwargs):
        """Move this pseudo axis to a specific position.

        See `PseudoPositioner.move_single` for more information.

        Parameters
        ----------
        pos : float
            Position to move to
        kwargs : dict
            Passed onto parent.move_single()
        """
        self._target = pos
        return self._parent.move_single(self, pos, **kwargs)

    def describe(self):
        desc = super().describe()
        low_limit, high_limit = self.limits

        for d in (desc[self.readback.name], desc[self.setpoint.name]):
            d["upper_ctrl_limit"] = high_limit
            d["lower_ctrl_limit"] = low_limit
            d["units"] = self.egu

        return desc


def _position_argument_wrapper(type_):
    """Wrapper to convert positional arguments to a PositionTuple"""

    def wrapper(method):
        @functools.wraps(method)
        def wrapped(self, *args, **kwargs):
            m = {"pseudo": self.to_pseudo_tuple, "real": self.to_real_tuple}[type_]
            pos, new_kwargs = m(*args, **kwargs)

            return method(self, pos, **new_kwargs)

        return wrapped

    return wrapper


real_position_argument = _position_argument_wrapper("real")
pseudo_position_argument = _position_argument_wrapper("pseudo")

_to_position_tuple_usage_info = """Positions can be passed in a number of ways.

As positional arguments:
    pseudo.method(px, py, pz, **kwargs)
As a sequence or PseudoPosition/RealPosition:
    pseudo.method((px, py, pz), **kwargs)
As kwargs:
    pseudo.method(px=1, py=2, pz=3, **kwargs)

"""


def _to_position_tuple(cls, *args, _cur, **kwargs):
    """Convert user-specified arguments to a Position namedtuple and kwargs

    TODO update for _cur

    Example::

        Tuple = namedtuple('Tuple', 'px py pz')

    All of the following will return the same thing::

        t, kwargs = to_position_tuple(Tuple, px, py, pz, a=4)
        t, kwargs = to_position_tuple(Tuple, (px, py, pz), a=4)
        t, kwargs = to_position_tuple(Tuple, Tuple(px, py, pz), a=4)
        t, kwargs = to_position_tuple(Tuple, px=1, py=2, pz=3, a=4)

    t will be Tuple(px, py, pz), and kwargs will be {'a': 4}.

    Parameters
    ----------
    cls : namedtuple
        The position class to use. This is likely a RealPosition or a
        PseudoPosition from a PseudoPositioner.
    args :
        User-specified positional arguments
    kwargs : dict
        User-specified keyword arguments

    Returns
    -------
    position_tuple : cls
        The position tuple
    kwargs : dict
        Keyword arguments not related to the position tuple

    Raises
    ------
    TypeError
        On an empty or invalid namedtuple
    ValueError
        On a mismatch of parameters
    """
    try:
        fields = cls._fields
    except AttributeError:
        raise TypeError("Invalid position tuple")

    if not fields:
        raise TypeError("Invalid position tuple")

    if args:
        if isinstance(args[0], (cls, Sequence)):
            (args,) = args

        elif isinstance(args[0], Mapping):
            (arg,) = args
            if any(k in kwargs for k in arg):
                raise ValueError("overlap between dict arg and kwargs")
            kwargs.update(arg)
            args = tuple()

    # too many args, give up
    if len(args) > len(fields):
        raise ValueError("too many args")

    # have _cur, too few args, and no field names in kwargs, fill out
    elif len(args) > 0:
        if any(f in kwargs for f in fields):
            raise ValueError("can not mix args and kwargs for positions")
        if len(args) == len(fields):
            return cls(*args), kwargs
        else:
            _cur = _cur()
            return cls(*args, *_cur[len(args) :]), kwargs

    # No positional arguments, position described in terms of kwargs
    if not kwargs:
        # no positional arguments or kwargs, just show usage information
        raise ValueError(_to_position_tuple_usage_info)

    missing_fields = [field for field in fields if field not in kwargs]

    if missing_fields:
        _cur = _cur()
        kwargs.update({k: getattr(_cur, k) for k in missing_fields})

    # separate position tuple kwargs from other kwargs
    position_kw = {field: kwargs[field] for field in fields}
    other_kw = {key: value for key, value in kwargs.items() if key not in fields}
    position = cls(**position_kw)
    return position, other_kw


class PseudoPositioner(Device, SoftPositioner):
    """A pseudo positioner which can be comprised of multiple positioners

    Parameters
    ----------
    prefix : str
        The PV prefix for all components of the device
    concurrent : bool, optional
        If set, all real motors will be moved concurrently. If not, they will
        be moved in order of how they were defined initially
    read_attrs : sequence of attribute names
        the components to include in a normal reading (i.e., in ``read()``)
    configuration_attrs : sequence of attribute names
        the components to be read less often (i.e., in
        ``read_configuration()``) and to adjust via ``configure()``
    name : str, optional
        The name of the device
    egu : str, optional
        The user-defined engineering units for the whole PseudoPositioner
    auto_target : bool, optional
        Automatically set the target position of PseudoSingle devices when
        moving to a single PseudoPosition
    parent : instance or None
        The instance of the parent device, if applicable
    settle_time : float, optional
        The amount of time to wait after moves to report status completion
    timeout : float, optional
        The default timeout to use for motion requests, in seconds.
    """

    class __add_sub_mixin:
        """Helper mix-in to make RealPosition and PseudoPosition mathable

        .. warning ::

           Do not use this outside of this purpose.

           No really, don't
        """

        __slots__ = ()

        def __add__(self, other):
            if not isinstance(other, type(self)):
                try:
                    for k in self._fields:
                        other.setdefault(k, 0)
                    other = type(self)(**other)
                except (TypeError, AttributeError):
                    try:
                        other = type(self)(*other)
                    except TypeError:
                        return NotImplemented

            return type(self)(*(s + o for s, o in zip(self, other)))

        def __sub__(self, other):
            if not isinstance(other, type(self)):
                try:
                    for k in self._fields:
                        other.setdefault(k, 0)
                    other = type(self)(**other)
                except (TypeError, AttributeError):
                    try:
                        other = type(self)(*other)
                    except TypeError:
                        return NotImplemented

            return type(self)(*(s - o for s, o in zip(self, other)))

        def __abs__(self):
            return math.sqrt(sum(x * x for x in self))

    def __init__(
        self,
        prefix="",
        *,
        concurrent=True,
        read_attrs=None,
        configuration_attrs=None,
        name,
        egu="",
        auto_target=True,
        **kwargs,
    ):

        self._finished_lock = threading.RLock()
        self._concurrent = bool(concurrent)
        self._finish_thread = None
        self._real_waiting = []
        self._move_queue = []
        self.auto_target = auto_target

        if self.__class__ is PseudoPositioner:
            raise TypeError(
                "PseudoPositioner must be subclassed with the "
                "correct signals set in the class definition."
            )

        super().__init__(
            prefix,
            read_attrs=read_attrs,
            configuration_attrs=configuration_attrs,
            name=name,
            egu=egu,
            **kwargs,
        )

        self._real = [getattr(self, attr) for attr, cpt in self._get_real_positioners()]
        self._pseudo = [
            getattr(self, attr) for attr, cpt in self._get_pseudo_positioners()
        ]

        if not self._pseudo or not self._real:
            raise ValueError("Must have at least 1 positioner and " "pseudo-positioner")

        if not self._egu:
            # Make the PseudoPositioner units based on the PseudoSingle
            # units
            self._egu = self.composite_egu

        self.RealPosition = self._real_position_tuple()
        self.PseudoPosition = self._pseudo_position_tuple()

        self.log.debug("Real positioners: %s", self._real)
        self.log.debug("Pseudo positioners: %s", self._pseudo)

        for idx, pseudo in enumerate(self._pseudo):
            pseudo._idx = idx

        self._real_cur_pos = OrderedDict((real, None) for real in self._real)

        for real in self._real:
            # Subscribe to events from all the real motors and update the
            # internal state of their position
            self._required_for_connection[real] = f"{real.name} readback position"
            real.subscribe(
                self._real_pos_update, event_type=real.SUB_READBACK, run=True
            )

    @property
    def composite_egu(self):
        """The composite engineering units (EGU) from all PseudoSingles"""
        return ", ".join(pseudo.egu for pseudo in self._pseudo if pseudo.egu)

    @property
    def pseudo_positioners(self):
        """Pseudo positioners instances in a namedtuple

        Returns
        -------
        positioner_instances : PseudoPosition
        """
        return self.PseudoPosition(*self._pseudo)

    @property
    def real_positioners(self):
        """Real positioners instances in a namedtuple

        Returns
        -------
        positioner_instances : RealPosition
        """
        return self.RealPosition(*self._real)

    @classmethod
    def _real_position_tuple(cls):
        """A namedtuple for a real motor position

        This is automatically generated at the class-level for all
        non-PseudoSingle-based positioners.
        """
        cname = cls.__name__ + "RealPos"

        return type(
            cname,
            (
                cls.__add_sub_mixin,
                namedtuple(
                    "_" + cname, [name for name, cpt in cls._get_real_positioners()]
                ),
            ),
            {},
        )

    @classmethod
    def _pseudo_position_tuple(cls):
        """A namedtuple for a pseudo motor position

        This is automatically generated at the class-level for all
        PseudoSingle-based positioners.
        """
        cname = cls.__name__ + "PseudoPos"
        return type(
            cname,
            (
                cls.__add_sub_mixin,
                namedtuple(
                    "_" + cname, [name for name, cpt in cls._get_pseudo_positioners()]
                ),
            ),
            {},
        )

    @classmethod
    def _get_pseudo_positioners(cls):
        """Inspect the components and find the pseudo positioners

        All `PseudoSingle` (and subclassed) components will be returned, by
        default.

        The built-in mechanism to override the list of pseudo positioners on a
        PseudoPositioner is to define '_pseudo' on the class-level.  It should
        be a list of attribute names.

        Yields
        ------
        (attr, component)
        """
        if hasattr(cls, "_pseudo"):
            for pseudo in cls._pseudo:
                yield pseudo, getattr(cls, pseudo)
        else:
            for attr, cpt in cls._sig_attrs.items():
                if issubclass(cpt.cls, PseudoSingle):
                    yield attr, cpt

    @classmethod
    def _get_real_positioners(cls):
        """Inspect the components and find the real positioners

        All `Positioner` components which are not `PseudoSingle`s will be
        returned, by default.

        The built-in mechanism to override the list of real positioners on a
        PseudoPositioner is to define '_real' on the class-level.  It should be
        a list of attribute names. This allows you to group real motors
        logically on the device but not have them included in motions or
        calculations.

        Yields
        ------
        (attr, component)
        """
        if hasattr(cls, "_real"):
            for real in cls._real:
                yield real, getattr(cls, real)
        else:
            for attr, cpt in cls._sig_attrs.items():
                is_pseudo = issubclass(cpt.cls, PseudoSingle)
                is_positioner = issubclass(cpt.cls, PositionerBase)
                if is_positioner and not is_pseudo:
                    yield attr, cpt

    def _repr_info(self):
        yield from super()._repr_info()
        yield ("concurrent", self._concurrent)

    def stop(self, success=False):
        del self._move_queue[:]
        exc_list = []

        for attr in self._sub_devices:
            dev = getattr(self, attr)

            if isinstance(dev, PseudoSingle) or not dev.connected:
                continue

            try:
                dev.stop(success=success)
            except ExceptionBundle as ex:
                exc_list.extend(
                    [
                        ("{}.{}".format(attr, sub_attr), ex)
                        for sub_attr, ex in ex.exceptions.items()
                    ]
                )
            except Exception as ex:
                exc_list.append((attr, ex))
                self.log.exception("Device %s (%s) stop failed", attr, dev)

        if exc_list:
            exc_info = "\n".join(
                "{} raised {!r}".format(attr, ex) for attr, ex in exc_list
            )
            raise ExceptionBundle(
                "{} exception(s) were raised during stop: \n"
                "{}".format(len(exc_list), exc_info),
                exceptions=dict(exc_list),
            )

    def check_single(self, pseudo_single, single_pos):
        """Check if a new position for a single pseudo positioner is valid"""
        idx = pseudo_single._idx
        target = list(self.target)
        target[idx] = single_pos
        return self.check_value(self.PseudoPosition(*target))

    def to_pseudo_tuple(self, *args, **kwargs):
        """Convert arguments to a PseudoPosition namedtuple and kwargs"""
        return _to_position_tuple(
            self.PseudoPosition, *args, **kwargs, _cur=lambda: self.target
        )

    def to_real_tuple(self, *args, **kwargs):
        """Convert arguments to a RealPosition namedtuple and kwargs"""
        return _to_position_tuple(
            self.RealPosition, *args, **kwargs, _cur=lambda: self.real_position
        )

    def check_value(self, pseudo_pos):
        """Check if a new position for all pseudo positioners is valid

        First checks limits against those set for individual pseudo axes.
        Second, calculates forward(pseudo_pos) => real_pos and checks it
        against the real positioners.

        NOTE: If you have limits that are coupled together or are somehow more
        complicated than the above procedure, you should redefine this method
        in your subclass.
        """
        try:
            pseudo_pos = self.PseudoPosition(*pseudo_pos)
        except TypeError as ex:
            raise ValueError(
                "Not all required values for a PseudoPosition: {}"
                "({})".format(self.PseudoPosition._fields, ex)
            )

        for pseudo, pos in zip(self._pseudo, pseudo_pos):
            low, high = pseudo.limits
            if (high > low) and not (low <= pos <= high):
                raise ValueError(
                    "Position is outside of pseudo single limits:"
                    " {}, {} < {} < {}".format(pseudo.name, low, pos, high)
                )

        real_pos = self.forward(pseudo_pos)
        for real, pos in zip(self._real, real_pos):
            real.check_value(pos)

    @property
    def limits(self):
        """All PseudoSingle limits as a namedtuple"""
        # NOTE: overrides SoftPositioner implementation
        return self.PseudoPosition(*(pseudo.limits for pseudo in self._pseudo))

    @property
    def low_limit(self):
        """All PseudoSingle low limits as a namedtuple"""
        # NOTE: overrides SoftPositioner implementation
        return self.PseudoPosition(*(pseudo.low_limit for pseudo in self._pseudo))

    @property
    def high_limit(self):
        """All PseudoSingle high limits as a namedtuple"""
        # NOTE: overrides SoftPositioner implementation
        return self.PseudoPosition(*(pseudo.high_limit for pseudo in self._pseudo))

    @property
    def moving(self):
        return any(pos.moving for pos in self._real)

    @property
    def sequential(self):
        """If sequential is set, motors will move in the sequence they were
        defined in (i.e., in series)
        """
        return not self._concurrent

    @property
    def concurrent(self):
        """If concurrent is set, motors will move concurrently (in parallel)"""
        return self._concurrent

    @property
    def _started_moving(self):
        return any(pos._started_moving for pos in self._real)

    @_started_moving.setter
    def _started_moving(self, value):
        # Don't allow the base class to specify whether it has started moving
        pass

    @property
    def position(self):
        """Pseudo motor position namedtuple"""
        return self.inverse(self.real_position)

    @property
    def real_position(self):
        """Real motor position namedtuple"""
        return self.RealPosition(*self._real_cur_pos.values())

    def _update_position(self):
        """Update the internal position based on all of the real positioners"""
        real_cur_pos = self.real_position
        if None in real_cur_pos:
            raise DisconnectedError("Not all positioners connected")

        initial_position = self._position is None
        calc_pseudo_pos = self.inverse(real_cur_pos)
        self._set_position(calc_pseudo_pos)

        if initial_position:
            for positioner, single_pos in zip(self._pseudo, calc_pseudo_pos):
                if positioner._target_initial_position:
                    positioner._target = single_pos

        return calc_pseudo_pos

    def _real_pos_update(self, obj=None, value=None, **kwargs):
        """Callback: A single real positioner has moved"""
        real = obj
        self._real_cur_pos[real] = value
        # Only update the position if all real motors are connected
        try:
            self._update_position()
        except DisconnectedError:
            pass

        # Now that we have a position for this motor, it is no longer blocking
        # the PseudoPositioner from being marked as connected:
        self._required_for_connection.pop(real, None)

    def _done_moving(self, success=True):
        """Call this when motion has completed.  Runs SUB_DONE subscription."""
        del self._real_waiting[:]
        super()._done_moving(success=success)

    def _real_finished(self, status=None, *, obj=None):
        """Callback: A single real positioner has finished moving.

        Used for asynchronous motion, if all have finished moving then fire a
        callback (via `Positioner._done_moving`)
        """
        with self._finished_lock:
            real = obj
            self.log.debug("Real motor %s finished moving", real.name)

            if real in self._real_waiting:
                self._real_waiting.remove(real)

                if not self._real_waiting:
                    self._done_moving()

    def move_single(self, pseudo, position, **kwargs):
        """Move one PseudoSingle axis to a position

        All other positioners will use their current setpoint/target value, if
        available. Failing that, their current readback value will be used (see
        `PseudoSingle.sync` and `PseudoSingle.target`).

        Parameters
        ----------
        pseudo : PseudoSingle
            PseudoSingle positioner to move
        position : float
            Position only for the PseudoSingle
        kwargs : dict
            Passed onto move
        """
        idx = pseudo._idx
        target = list(self.target)
        target[idx] = position
        return self.move(self.PseudoPosition(*target), **kwargs)

    @property
    def target(self):
        """Last commanded target positions"""
        return self.PseudoPosition(*(pos.target for pos in self._pseudo))

    def _sequential_move(self, real_pos, timeout=None, **kwargs):
        """Move all real positioners to a certain position, in series"""
        self._move_queue[:] = zip(self._real, real_pos)
        pending_status = []
        t0 = time.time()

        def move_next(status=None, obj=None):
            # last motion complete message came from 'obj'
            self.log.debug("[%s:sequential] move_next called", self.name)
            with self._finished_lock:
                if pending_status:
                    last_status = pending_status[-1]
                    if not last_status.success:
                        self.log.error("Failing due to last motion")
                        self._done_moving(success=False)
                        return

                try:
                    real, position = self._move_queue.pop(0)
                except IndexError:
                    self._done_moving(success=True)
                    return

                self.log.debug(
                    "[%s:sequential] Moving next motor: %s", self.name, real.name
                )

                elapsed = time.time() - t0
                if timeout is None:
                    sub_timeout = None
                else:
                    sub_timeout = timeout - elapsed

                self.log.debug(
                    "[%s:sequential] Moving %s to %s (timeout=%s)",
                    self.name,
                    real.name,
                    position,
                    sub_timeout,
                )

                if sub_timeout is not None and sub_timeout < 0:
                    self.log.error("Motion timeout")
                    self._done_moving(success=False)
                else:
                    status = real.move(
                        position,
                        wait=False,
                        timeout=sub_timeout,
                        moved_cb=move_next,
                        **kwargs,
                    )
                    pending_status.append(status)
                    self.log.debug(
                        "[%s:sequential] waiting on %s", self.name, real.name
                    )

        self.log.debug("[%s:sequential] started", self.name)
        move_next()

    def _concurrent_move(self, real_pos, **kwargs):
        """Move all real positioners to a certain position, in parallel"""
        self._real_waiting.extend(self._real)

        for real, value in zip(self._real, real_pos):
            self.log.debug("[concurrent] Moving %s to %s", real.name, value)
            real.move(value, wait=False, moved_cb=self._real_finished, **kwargs)

    @pseudo_position_argument
    def move(self, position, wait=True, timeout=None, moved_cb=None):
        """Move to a specified position, optionally waiting for motion to
        complete.

        Parameters
        ----------
        position
            Pseudo position to move to
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
        if self.auto_target:
            # in auto-target mode, we update the setpoints of the PseudoSingles
            # on every motion of the PseudoPositioner
            for positioner, single_pos in zip(self._pseudo, position):
                positioner._target = single_pos
        return super().move(position, wait=wait, timeout=timeout, moved_cb=moved_cb)

    move.__doc__ = SoftPositioner.move.__doc__

    def _setup_move(self, position, status):
        """Move requested to position

        This is a customization of SoftPositioner's _setup_move method which
        is what gets called when a motion request happens.

        Parameters
        ----------
        position : PseudoPosition
            Position to move to (already verified by `check_value`)
        status : MoveStatus
            Status object created by PositionerBase.move()
        """
        # Clear all old statuses for not yet completed real motions
        del self._real_waiting[:]

        timeout = status.timeout
        real_pos = self.forward(position)

        with self._finished_lock:
            # ensure we don't get any motion complete messages before motion
            # setup is finished
            if self.sequential:
                self._sequential_move(real_pos, timeout=timeout)
            else:
                self._concurrent_move(real_pos, timeout=timeout)

    @pseudo_position_argument
    def forward(self, pseudo_pos):
        """Calculate a RealPosition from a given PseudoPosition

        Must be defined on the subclass.

        Parameters
        ----------
        pseudo_pos : PseudoPosition
            The pseudo position input

        Returns
        -------
        real_position : RealPosition
            The real position output
        """
        # return self.RealPosition()
        raise NotImplementedError()

    @real_position_argument
    def inverse(self, real_pos):
        """Calculate a PseudoPosition from a given RealPosition

        Must be defined on the subclass.

        Parameters
        ----------
        real_position : RealPosition
            The real position input

        Returns
        -------
        pseudo_pos : PseudoPosition
            The pseudo position output
        """
        # return self.PseudoPosition()
        raise NotImplementedError()

    @pseudo_position_argument
    def set(self, position, **kwargs):
        """Move to a new position asynchronously

        Parameters
        ----------
        position : PseudoPosition
            Position for the all of the pseudo axes

        Returns
        -------
        status : MoveStatus
        """
        return super().set(position, **kwargs)
