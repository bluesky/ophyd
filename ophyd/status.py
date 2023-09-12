import threading
import time
from collections import deque
from functools import partial
from logging import LoggerAdapter
from warnings import warn

import numpy as np

from .log import logger
from .utils import (
    InvalidState,
    StatusTimeoutError,
    UnknownStatusFailure,
    WaitTimeoutError,
    adapt_old_callback_signature,
)


class UseNewProperty(RuntimeError):
    ...


class StatusBase:
    """
    Track the status of a potentially-lengthy action like moving or triggering.

    Parameters
    ----------
    timeout: float, optional
        The amount of time to wait before marking the Status as failed.  If
        ``None`` (default) wait forever. It is strongly encouraged to set a
        finite timeout.  If settle_time below is set, that time is added to the
        effective timeout.
    settle_time: float, optional
        The amount of time to wait between the caller specifying that the
        status has completed to running callbacks. Default is 0.


    Notes
    -----

    Theory of operation:

    This employs two ``threading.Event`` objects, one thread the runs for
    (timeout + settle_time) seconds, and one thread that runs for
    settle_time seconds (if settle_time is nonzero).

    At __init__ time, a *timeout* and *settle_time* are specified. A thread
    is started, on which user callbacks, registered after __init__ time via
    :meth:`add_callback`, will eventually be run. The thread waits on an
    Event be set or (timeout + settle_time) seconds to pass, whichever
    happens first.

    If (timeout + settle_time) expires and the Event has not
    been set, an internal Exception is set to ``StatusTimeoutError``, and a
    second Event is set, marking the Status as done and failed. The
    callbacks are run.

    If a callback is registered after the Status is done, it will be run
    immediately.

    If the first Event is set before (timeout + settle_time) expires,
    then the second Event is set and no internal Exception is set, marking
    the Status as done and successful. The callbacks are run.

    There are two methods that directly set the first Event. One,
    :meth:set_exception, sets it directly after setting the internal
    Exception.  The other, :meth:`set_finished`, starts a
    ``threading.Timer`` that will set it after a delay (the settle_time).
    One of these methods may be called, and at most once. If one is called
    twice or if both are called, ``InvalidState`` is raised. If they are
    called too late to prevent a ``StatusTimeoutError``, they are ignored
    but one call is still allowed. Thus, an external callback, e.g. pyepics,
    may reports success or failure after the Status object has expired, but
    to no effect because the callbacks have already been called and the
    program has moved on.

    """

    def __init__(self, *, timeout=None, settle_time=0, done=None, success=None):
        super().__init__()
        self._tname = None
        self._lock = threading.RLock()
        self._event = threading.Event()  # state associated with done-ness
        self._settled_event = threading.Event()
        # "Externally initiated" means set_finished() or set_exception(exc) was
        # called, as opposed to completion via an internal timeout.
        self._externally_initiated_completion_lock = threading.Lock()
        self._externally_initiated_completion = False
        self._callbacks = deque()
        self._exception = None

        self.log = LoggerAdapter(logger=logger, extra={"status": self})

        if settle_time is None:
            settle_time = 0.0

        self._settle_time = float(settle_time)

        if timeout is not None:
            timeout = float(timeout)
        self._timeout = timeout

        # We cannot know that we are successful if we are not done.
        if success and not done:
            raise ValueError("Cannot initialize with done=False but success=True.")
        if done is not None or success is not None:
            warn(
                "The 'done' and 'success' parameters will be removed in a "
                "future release. Use the methods set_finished() or "
                "set_exception(exc) to mark success or failure, respectively, "
                "after the Status has been instantiated.",
                DeprecationWarning,
            )

        self._callback_thread = threading.Thread(
            target=self._run_callbacks, daemon=True, name=self._tname
        )
        self._callback_thread.start()

        if done:
            if success:
                self.set_finished()
            else:
                exc = UnknownStatusFailure(
                    f"The status {self!r} has failed. To obtain more specific, "
                    "helpful errors in the future, update the Device to use "
                    "set_exception(...) instead of setting success=False "
                    "at __init__ time."
                )
                self.set_exception(exc)

    @property
    def timeout(self):
        """
        The timeout for this action.

        This is set when the Status is created, and it cannot be changed.
        """
        return self._timeout

    @property
    def settle_time(self):
        """
        A delay between when :meth:`set_finished` is when the Status is done.

        This is set when the Status is created, and it cannot be changed.
        """
        return self._settle_time

    @property
    def done(self):
        """
        Boolean indicating whether associated operation has completed.

        This is set to True at __init__ time or by calling
        :meth:`set_finished`, :meth:`set_exception`, or (deprecated)
        :meth:`_finished`. Once True, it can never become False.
        """
        return self._event.is_set()

    @done.setter
    def done(self, value):
        # For now, allow this setter to work only if it has no effect.
        # In a future release, make this property not settable.
        if bool(self._event.is_set()) != bool(value):
            raise RuntimeError(
                "The done-ness of a status object cannot be changed by "
                "setting its `done` attribute directly. Call `set_finished()` "
                "or `set_exception(exc)."
            )
        warn(
            "Do not set the `done` attribute of a status object directly. "
            "It should only be set indirectly by calling `set_finished()` "
            "or `set_exception(exc)`. "
            "Direct setting was never intended to be supported and it will be "
            "disallowed in a future release of ophyd, causing this code path "
            "to fail.",
            UserWarning,
        )

    @property
    def success(self):
        """
        Boolean indicating whether associated operation has completed.

        This is set to True at __init__ time or by calling
        :meth:`set_finished`, :meth:`set_exception`, or (deprecated)
        :meth:`_finished`. Once True, it can never become False.
        """
        return self.done and self._exception is None

    @success.setter
    def success(self, value):
        # For now, allow this setter to work only if it has no effect.
        # In a future release, make this property not settable.
        if bool(self.success) != bool(value):
            raise RuntimeError(
                "The success state of a status object cannot be changed by "
                "setting its `success` attribute directly. Call "
                "`set_finished()` or `set_exception(exc)`."
            )
        warn(
            "Do not set the `success` attribute of a status object directly. "
            "It should only be set indirectly by calling `set_finished()` "
            "or `set_exception(exc)`. "
            "Direct setting was never intended to be supported and it will be "
            "disallowed in a future release of ophyd, causing this code path "
            "to fail.",
            UserWarning,
        )

    def _handle_failure(self):
        pass

    def _settled(self):
        """Hook for when status has completed and settled"""
        pass

    def _run_callbacks(self):
        """
        Set the Event and run the callbacks.
        """
        if self.timeout is None:
            timeout = None
        else:
            timeout = self.timeout + self.settle_time
        if not self._settled_event.wait(timeout):
            # We have timed out. It's possible that set_finished() has already
            # been called but we got here before the settle_time timer expired.
            # And it's possible that in this space be between the above
            # statement timing out grabbing the lock just below,
            # set_exception(exc) has been called. Both of these possibilties
            # are accounted for.
            self.log.warning("%r has timed out", self)
            with self._externally_initiated_completion_lock:
                # Set the exception and mark the Status as done, unless
                # set_exception(exc) was called externally before we grabbed
                # the lock.
                if self._exception is None:
                    exc = StatusTimeoutError(
                        f"Status {self!r} failed to complete in specified timeout."
                    )
                    self._exception = exc
        # Mark this as "settled".
        try:
            self._settled()
        except Exception:
            # No alternative but to log this. We can't supersede set_exception,
            # and we have to continue and run the callbacks.
            self.log.exception("%r encountered error during _settled()", self)
        # Now we know whether or not we have succeed or failed, either by
        # timeout above or by set_exception(exc), so we can set the Event that
        # will mark this Status as done.
        with self._lock:
            self._event.set()
        if self._exception is not None:
            try:
                self._handle_failure()
            except Exception:
                self.log.exception(
                    "%r encountered an error during _handle_failure()", self
                )
        # The callbacks have access to self, from which they can distinguish
        # success or failure.
        for cb in self._callbacks:
            try:
                cb(self)
            except Exception:
                self.log.exception(
                    "An error was raised on a background thread while "
                    "running the callback %r(%r).",
                    cb,
                    self,
                )
        self._callbacks.clear()

    def set_exception(self, exc):
        """
        Mark as finished but failed with the given Exception.

        This method should generally not be called by the *recipient* of this
        Status object, but only by the object that created and returned it.

        Parameters
        ----------
        exc: Exception
        """
        # Since we rely on this being raise-able later, check proactively to
        # avoid potentially very confusing failures.
        if not (
            isinstance(exc, Exception)
            or isinstance(exc, type)
            and issubclass(exc, Exception)
        ):
            # Note that Python allows `raise Exception` or raise Exception()`
            # so we allow a class or an instance here too.
            raise ValueError(f"Expected an Exception, got {exc!r}")

        # Ban certain Timeout subclasses that have special significance. This
        # would probably never come up except due to some rare user error, but
        # if it did it could be very confusing indeed!
        for exc_class in (StatusTimeoutError, WaitTimeoutError):
            if (
                isinstance(exc, exc_class)
                or isinstance(exc, type)
                and issubclass(exc, exc_class)
            ):
                raise ValueError(
                    f"{exc_class} has special significance and cannot be set "
                    "as the exception. Use a plain TimeoutError or some other "
                    "subclass thereof."
                )

        with self._externally_initiated_completion_lock:
            if self._externally_initiated_completion:
                raise InvalidState(
                    "Either set_finished() or set_exception() has "
                    f"already been called on {self!r}"
                )
            self._externally_initiated_completion = True
            if isinstance(self._exception, StatusTimeoutError):
                # We have already timed out.
                return
            self._exception = exc
            self._settled_event.set()

    def set_finished(self):
        """
        Mark as finished successfully.

        This method should generally not be called by the *recipient* of this
        Status object, but only by the object that created and returned it.
        """
        with self._externally_initiated_completion_lock:
            if self._externally_initiated_completion:
                raise InvalidState(
                    "Either set_finished() or set_exception() has "
                    f"already been called on {self!r}"
                )
            self._externally_initiated_completion = True
        # Note that in either case, the callbacks themselves are run from the
        # same thread. This just sets an Event, either from this thread (the
        # one calling set_finished) or the thread created below.
        if self.settle_time > 0:
            threading.Timer(self.settle_time, self._settled_event.set).start()
        else:
            self._settled_event.set()

    def _finished(self, success=True, **kwargs):
        """
        Inform the status object that it is done and if it succeeded.

        This method is deprecated. Please use :meth:`set_finished` or
        :meth:`set_exception`.

        .. warning::

           kwargs are not used, but are accepted because pyepics gives
           in a bunch of kwargs that we don't care about.  This allows
           the status object to be handed directly to pyepics (but
           this is probably a bad idea for other reason.

           This may be deprecated in the future.

        Parameters
        ----------
        success : bool, optional
           if the action succeeded.
        """
        if success:
            self.set_finished()
        else:
            # success=False does not give any information about *why* it
            # failed, so set a generic exception.
            exc = UnknownStatusFailure(
                f"The status {self!r} has failed. To obtain more specific, "
                "helpful errors in the future, update the Device to use "
                "set_exception(...) instead of _finished(success=False)."
            )
            self.set_exception(exc)

    def exception(self, timeout=None):
        """
        Return the exception raised by the action.

        If the action has completed successfully, return ``None``. If it has
        finished in error, return the exception.

        Parameters
        ----------
        timeout: Union[Number, None], optional
            If None (default) wait indefinitely until the status finishes.

        Raises
        ------
        WaitTimeoutError
            If the status has not completed within ``timeout`` (starting from
            when this method was called, not from the beginning of the action).
        """
        if not self._event.wait(timeout=timeout):
            raise WaitTimeoutError(f"Status {self!r} has not completed yet.")
        return self._exception

    def wait(self, timeout=None):
        """
        Block until the action completes.

        When the action has finished succesfully, return ``None``. If the
        action has failed, raise the exception.

        Parameters
        ----------
        timeout: Union[Number, None], optional
            If None (default) wait indefinitely until the status finishes.

        Raises
        ------
        WaitTimeoutError
            If the status has not completed within ``timeout`` (starting from
            when this method was called, not from the beginning of the action).
        StatusTimeoutError
            If the status has failed because the *timeout* that it was
            initialized with has expired.
        Exception
            This is ``status.exception()``, raised if the status has finished
            with an error.  This may include ``TimeoutError``, which
            indicates that the action itself raised ``TimeoutError``, distinct
            from ``WaitTimeoutError`` above.
        """
        if not self._event.wait(timeout=timeout):
            raise WaitTimeoutError(f"Status {self!r} has not completed yet.")
        if self._exception is not None:
            raise self._exception

    @property
    def callbacks(self):
        """
        Callbacks to be run when the status is marked as finished
        """
        return self._callbacks

    @property
    def finished_cb(self):
        with self._lock:
            if len(self.callbacks) == 1:
                warn(
                    "The property `finished_cb` is deprecated, and must raise "
                    "an error if a status object has multiple callbacks. Use "
                    "the `callbacks` property instead.",
                    stacklevel=2,
                )
                (cb,) = self.callbacks
                assert cb is not None
                return cb
            else:
                raise UseNewProperty(
                    "The deprecated `finished_cb` property "
                    "cannot be used for status objects that have "
                    "multiple callbacks. Use the `callbacks` "
                    "property instead."
                )

    def add_callback(self, callback):
        """
        Register a callback to be called once when the Status finishes.

        The callback will be called exactly once. If the Status is finished
        before a callback is added, it will be called immediately. This is
        threadsafe.

        The callback will be called regardless of success of failure. The
        callback has access to this status object, so it can distinguish success
        or failure by inspecting the object.

        Parameters
        ----------
        callback: callable
            Expected signature: ``callback(status)``.

            The signature ``callback()`` is also supported for
            backward-compatibility but will issue warnings. Support will be
            removed in a future release of ophyd.
        """
        # Handle func with signature callback() for back-compat.
        callback = adapt_old_callback_signature(callback)
        with self._lock:
            if self.done:
                # Call it once and do not hold a reference to it.
                callback(self)
            else:
                # Hold a strong reference to this. In other contexts we tend to
                # hold weak references to callbacks, but this is a single-shot
                # callback, so we will hold a strong reference until we call it,
                # and then clear this cache to drop the reference(s).
                self._callbacks.append(callback)

    @finished_cb.setter
    def finished_cb(self, cb):
        with self._lock:
            if not self.callbacks:
                warn(
                    "The setter `finished_cb` is deprecated, and must raise "
                    "an error if a status object already has one callback. Use "
                    "the `add_callback` method instead.",
                    stacklevel=2,
                )
                self.add_callback(cb)
            else:
                raise UseNewProperty(
                    "The deprecated `finished_cb` setter cannot "
                    "be used for status objects that already "
                    "have one callback. Use the `add_callbacks` "
                    "method instead."
                )

    def __and__(self, other):
        """
        Returns a new 'composite' status object, AndStatus,
        with the same base API.

        It will finish when both `self` or `other` finish.
        """
        return AndStatus(self, other)


class AndStatus(StatusBase):
    "a Status that has composes two other Status objects using logical and"

    def __init__(self, left, right, **kwargs):
        super().__init__(**kwargs)
        self.left = left
        self.right = right

        def inner(status):
            with self._lock:
                if self._externally_initiated_completion:
                    return
                with self.left._lock:
                    with self.right._lock:
                        l_success = self.left.success
                        r_success = self.right.success
                        l_done = self.left.done
                        r_done = self.right.done

                        # At least one is done.
                        # If it failed, do not wait for the second one.
                        if (not l_success) and l_done:
                            self._finished(success=False)
                        elif (not r_success) and r_done:
                            self._finished(success=False)

                        elif l_success and r_success and l_done and r_done:
                            # Both are done, successfully.
                            self._finished(success=True)
                        # Else one is done, successfully, and we wait for #2,
                        # when this function will be called again.

        self.left.add_callback(inner)
        self.right.add_callback(inner)

    def __repr__(self):
        return "({self.left!r} & {self.right!r})".format(self=self)

    def __str__(self):
        return (
            "{0}(done={1.done}, "
            "success={1.success})"
            "".format(self.__class__.__name__, self)
        )

    def __contains__(self, status: StatusBase) -> bool:
        for child in [self.left, self.right]:
            if child == status:
                return True
            if isinstance(child, AndStatus):
                if status in child:
                    return True

        return False


class Status(StatusBase):
    """
    Track the status of a potentially-lengthy action like moving or triggering.

    This has room for an option ``obj`` parameter, noting the object associated
    with action. Status does not use this internally, but it can be useful for
    external code to keep track of things.

    Parameters
    ----------
    timeout: float, optional
        The amount of time to wait before marking the Status as failed.  If
        ``None`` (default) wait forever. It is strongly encouraged to set a
        finite timeout.  If settle_time below is set, that time is added to the
        effective timeout.
    settle_time: float, optional
        The amount of time to wait between the caller specifying that the
        status has completed to running callbacks. Default is 0.

    Attributes
    ----------
    obj : any or None
        The object
    """

    def __init__(self, obj=None, timeout=None, settle_time=0, done=None, success=None):
        self.obj = obj
        super().__init__(
            timeout=timeout, settle_time=settle_time, done=done, success=success
        )

    def __str__(self):
        return (
            "{0}(obj={1.obj}, "
            "done={1.done}, "
            "success={1.success})"
            "".format(self.__class__.__name__, self)
        )

    __repr__ = __str__


class DeviceStatus(StatusBase):
    """
    Track the status of a potentially-lengthy action like moving or triggering.

    This adds the notion of a Device and minimal support for progress bars.
    (They only get notified of the Device name and the time of completion.)
    See MoveStatus for a richer implementation of progress bars.

    Parameters
    ----------
    timeout: float, optional
        The amount of time to wait before marking the Status as failed.  If
        ``None`` (default) wait forever. It is strongly encouraged to set a
        finite timeout.  If settle_time below is set, that time is added to the
        effective timeout.
    settle_time: float, optional
        The amount of time to wait between the caller specifying that the
        status has completed to running callbacks. Default is 0.
    """

    def __init__(self, device, **kwargs):
        self.device = device
        self._watchers = []
        super().__init__(**kwargs)

    def _handle_failure(self):
        super()._handle_failure()
        self.log.debug("Trying to stop %s", repr(self.device))
        self.device.stop()

    def __str__(self):
        return (
            "{0}(device={1.device.name}, done={1.done}, "
            "success={1.success})"
            "".format(self.__class__.__name__, self)
        )

    def watch(self, func):
        """
        Subscribe to notifications about partial progress.
        """
        # See MoveStatus.watch for a richer implementation and more info.
        if self.device is not None:
            self._watchers.append(func)
            func(name=self.device.name)

    def _settled(self):
        """Hook for when status has completed and settled"""
        for watcher in self._watchers:
            watcher(name=self.device.name, fraction=0.0)

    __repr__ = __str__


class SubscriptionStatus(DeviceStatus):
    """
    Status updated via ``ophyd`` events

    Parameters
    ----------
    device : obj

    callback : callable
        Callback that takes event information and returns a boolean. Signature
        should be ``f(*, old_value, value, **kwargs)``. The arguments
        old_value and value will be passed in by keyword, so their order does
        not matter.

    event_type : str, optional
        Name of event type to check whether the device has finished succesfully

    timeout : float, optional
        Maximum timeout to wait to mark the request as a failure

    settle_time : float, optional
        Time to wait after completion until running callbacks

    run: bool, optional
        Run the callback now
    """

    def __init__(
        self,
        device,
        callback,
        event_type=None,
        timeout=None,
        settle_time=None,
        run=True,
    ):
        # Store device and attribute information
        self.device = device
        self.callback = callback

        # Start timeout thread in the background
        super().__init__(device, timeout=timeout, settle_time=settle_time)

        # Subscribe callback and run initial check
        self.device.subscribe(self.check_value, event_type=event_type, run=run)

    def check_value(self, *args, **kwargs):
        """
        Update the status object
        """
        # Get attribute from device
        try:
            success = self.callback(*args, **kwargs)

        # Do not fail silently
        except Exception as e:
            self.log.error(e)
            raise

        # If successfull indicate completion
        if success:
            self._finished(success=True)

    def set_finished(self):
        """
        Mark as finished successfully.

        This method should generally not be called by the *recipient* of this
        Status object, but only by the object that created and returned it.
        """
        # Clear callback
        self.device.clear_sub(self.check_value)
        # Run completion
        super().set_finished()

    def _handle_failure(self):
        # This is called whether we fail via the timeout thread or via an
        # a call to set_exception.
        # Clear callback
        self.device.clear_sub(self.check_value)
        return super()._handle_failure()


class StableSubscriptionStatus(SubscriptionStatus):
    """
    Status updated via ``ophyd`` events which will wait for the event to be
    stable (the callback continuing to return true) until being complete.
    If the event becomes unstable and then back to stable this timer will
    be reset.

    Parameters
    ----------
    device : obj

    callback : callable
        Callback that takes event information and returns a boolean. Signature
        should be ``f(*, old_value, value, **kwargs)``. The arguments
        old_value and value will be passed in by keyword, so their order does
        not matter

    stability_time: float
        How long the event should remain stable for the status to be done

    event_type : str, optional
        Name of event type to check whether the device has finished succesfully

    timeout : float, optional
        Maximum timeout to wait to mark the request as a failure

    settle_time : float, optional
        Time to wait after completion until running callbacks

    run: bool, optional
        Run the callback now
    """

    def __init__(
        self,
        device,
        callback,
        stability_time,
        event_type=None,
        timeout=None,
        settle_time=None,
        run=True,
    ):
        if timeout and stability_time > timeout:
            raise ValueError(
                f"Stability time ({stability_time}) must be less than full status timeout ({timeout})"
            )
        self._stability_time = stability_time
        self._stable_timer = threading.Timer(
            self._stability_time, partial(self._finished, success=True)
        )

        # Start timeout thread in the background
        super().__init__(
            device,
            callback,
            event_type,
            timeout=timeout,
            settle_time=settle_time,
            run=run,
        )

    def check_value(self, *args, **kwargs):
        """
        Update the status object
        """
        try:
            success = self.callback(*args, **kwargs)

            # If successfull start a timer for completion
            if success:
                if not self._stable_timer.is_alive():
                    self._stable_timer.start()
            else:
                self._stable_timer.cancel()
                self._stable_timer = threading.Timer(
                    self._stability_time, partial(self._finished, success=True)
                )

        # Do not fail silently
        except Exception as e:
            self.log.error(e)
            raise

    def set_finished(self):
        """
        Mark as finished successfully.

        This method should generally not be called by the *recipient* of this
        Status object, but only by the object that created and returned it.
        """
        # Cancel timer
        self._stable_timer.cancel()
        # Run completion
        super().set_finished()

    def _handle_failure(self):
        # This is called whether we fail via the timeout thread or via an
        # a call to set_exception.
        # Cancel timer
        self._stable_timer.cancel()
        return super()._handle_failure()


class MoveStatus(DeviceStatus):
    """
    Track the state of a movement from some initial to final "position".

    The position could a physical position, a "position" in a pseudo-space, a
    temperature, etc. This constraint allows richer support for progress bars,
    including progress updates and an ETA.

    Parameters
    ----------
    positioner : Positioner
    target : float or array-like
        Target position
    done : bool, optional
        Whether or not the motion has already completed
    success : bool, optional
        If motion has already completed, the status of that motion
    start_ts : float, optional
        The motion start timestamp
    timeout : float, optional
        The default timeout to use for a blocking wait, and the amount of time
        to wait to mark the motion as failed
    settle_time : float, optional
        The amount of time to wait between motion completion and running
        callbacks

    Attributes
    ----------
    pos : Positioner
    target : float or array-like
        Target position
    done : bool
        Whether or not the motion has already completed
    start_ts : float
        The motion start timestamp
    finish_ts : float
        The motion completd timestamp
    finish_pos : float or ndarray
        The final position
    success : bool
        Motion successfully completed
    """

    def __init__(self, positioner, target, *, start_ts=None, **kwargs):
        self._tname = "timeout for {}".format(positioner.name)
        if start_ts is None:
            start_ts = time.time()

        self.pos = positioner
        self.target = target
        self.start_ts = start_ts
        self.start_pos = self.pos.position
        self.finish_ts = None
        self.finish_pos = None

        self._unit = getattr(self.pos, "egu", None)
        self._precision = getattr(self.pos, "precision", None)
        self._name = self.pos.name

        # call the base class
        super().__init__(positioner, **kwargs)

        # Notify watchers (things like progress bars) of new values
        # at the device's natural update rate.
        if not self.done:
            self.pos.subscribe(self._notify_watchers, event_type=self.pos.SUB_READBACK)

    def watch(self, func):
        """
        Subscribe to notifications about partial progress.

        This is useful for progress bars.

        Parameters
        ----------
        func : callable
            Expected to accept the keyword aruments:

                * ``name``
                * ``current``
                * ``initial``
                * ``target``
                * ``unit``
                * ``precision``
                * ``fraction``
                * ``time_elapsed``
                * ``time_remaining``
        """
        self._watchers.append(func)

    def _notify_watchers(self, value, *args, **kwargs):
        # *args and **kwargs catch extra inputs from pyepics, not needed here
        if not self._watchers:
            return
        current = value
        target = self.target
        initial = self.start_pos
        time_elapsed = time.time() - self.start_ts
        try:
            fraction = np.clip(abs(target - current) / abs(initial - target), 0, 1)
        # maybe we can't do math?
        except (TypeError, ZeroDivisionError):
            fraction = None

        if fraction is not None and np.isnan(fraction):
            fraction = None

        for watcher in self._watchers:
            watcher(
                name=self._name,
                current=current,
                initial=initial,
                target=target,
                unit=self._unit,
                precision=self._precision,
                time_elapsed=time_elapsed,
                fraction=fraction,
            )

    @property
    def error(self):
        """Error between target position and current* position

        * If motion is already complete, the final position is used
        """
        if self.finish_pos is not None:
            finish_pos = self.finish_pos
        else:
            finish_pos = self.pos.position

        try:
            return np.array(finish_pos) - np.array(self.target)
        except Exception:
            return None

    def _settled(self):
        """Hook for when motion has completed and settled"""
        super()._settled()
        self.pos.clear_sub(self._notify_watchers)
        self._watchers.clear()
        self.finish_ts = time.time()
        self.finish_pos = self.pos.position

    @property
    def elapsed(self):
        """Elapsed time"""
        if self.finish_ts is None:
            return time.time() - self.start_ts
        else:
            return self.finish_ts - self.start_ts

    def __str__(self):
        return (
            "{0}(done={1.done}, pos={1.pos.name}, "
            "elapsed={1.elapsed:.1f}, "
            "success={1.success}, settle_time={1.settle_time})"
            "".format(self.__class__.__name__, self)
        )

    __repr__ = __str__


def wait(status, timeout=None, *, poll_rate="DEPRECATED"):
    """(Blocking) wait for the status object to complete

    Parameters
    ----------
    status: StatusBase
        A Status object
    timeout: Union[Number, None], optional
        Amount of time in seconds to wait. None disables, such that wait() will
        only return when either the status completes or if interrupted by the
        user.
    poll_rate: "DEPRECATED"
        DEPRECATED. Has no effect because this does not poll.

    Raises
    ------
    WaitTimeoutError
        If the status has not completed within ``timeout`` (starting from
        when this method was called, not from the beginning of the action).
    Exception
        This is ``status.exception()``, raised if the status has finished
        with an error.  This may include ``TimeoutError``, which
        indicates that the action itself raised ``TimeoutError``, distinct
        from ``WaitTimeoutError`` above.
    """
    return status.wait(timeout)
