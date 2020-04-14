from collections import deque
from functools import wraps
from logging import LoggerAdapter
import threading
import time
from warnings import warn

import numpy as np

from .log import logger
from .utils import adapt_old_callback_signature


class UseNewProperty(RuntimeError):
    ...


# This is used below by StatusBase.
def _locked(func):
    "an decorator for running a method with the instance's lock"
    @wraps(func)
    def f(self, *args, **kwargs):
        with self._lock:
            return func(self, *args, **kwargs)

    return f


class StatusBase:
    """
    This is a base class that provides a single-slot callback for when the
    specific operation has finished.

    Parameters
    ----------
    timeout : float, optional
        The default timeout to use for a blocking wait, and the amount of time
        to wait to mark the operation as failed
    settle_time : float, optional
        The amount of time to wait between the caller specifying that the
        status has completed to running callbacks
    """
    def __init__(self, *, timeout=None, settle_time=None, done=False,
                 success=False):
        super().__init__()
        self._tname = None
        self._lock = threading.RLock()
        self._callbacks = deque()
        self._done = done
        self.success = success
        self.timeout = None

        self.log = LoggerAdapter(logger=logger, extra={'status': self})

        if settle_time is None:
            settle_time = 0.0

        self.settle_time = float(settle_time)

        if timeout is not None:
            self.timeout = float(timeout)

        if self.done:
            # in the case of a pre-completed status object,
            # don't handle timeout
            return

        if self.timeout is not None and self.timeout > 0.0:
            thread = threading.Thread(target=self._wait_and_cleanup,
                                      daemon=True, name=self._tname)
            self._timeout_thread = thread
            self._timeout_thread.start()

    @property
    def done(self):
        """
        Boolean indicating whether associated operation has completed.

        This is set to True at __init__ time or by calling `_finished()`. Once
        True, it can never become False.
        """
        return self._done

    @done.setter
    def done(self, value):
        # For now, allow this setter to work only if it has no effect.
        # In a future release, make this property not settable.
        if bool(self._done) != bool(value):
            raise RuntimeError(
                "The done-ness of a status object cannot be changed by "
                "setting its `done` attribute directly. Call `_finished()`.")
        warn(
            "Do not set the `done` attribute of a status object directly. "
            "It should only be set indirectly by calling `_finished()`. "
            "Direct setting was never intended to be supported and it will be "
            "disallowed in a future release of ophyd, causing this code path "
            "to fail.",
            UserWarning)

    def _wait_and_cleanup(self):
        """Handle timeout"""
        try:
            if self.timeout is not None:
                timeout = self.timeout + self.settle_time
            else:
                timeout = None
            wait(self, timeout=timeout, poll_rate=0.2)
        except TimeoutError:
            with self._lock:
                if self.done:
                    # Avoid race condition with settling.
                    return
                self.log.warning('timeout after %.2f seconds', timeout)
                try:
                    self._handle_failure()
                finally:
                    self._finished(success=False)
        except RuntimeError:
            pass
        finally:
            self._timeout_thread = None

    def _handle_failure(self):
        pass

    def _settled(self):
        """Hook for when status has completed and settled"""
        pass

    def _settle_then_run_callbacks(self, success=True):
        # wait until the settling time is done to mark completion
        if self.settle_time > 0.0:
            time.sleep(self.settle_time)

        with self._lock:
            if self.done:
                # We timed out while waiting for the settle time.
                return
            self.success = success
            self._done = True
            self._settled()

            for cb in self._callbacks:
                cb(self)
            self._callbacks.clear()

    def _finished(self, success=True, **kwargs):
        """Inform the status object that it is done and if it succeeded

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
        if self.done:
            self.log.info('finished')
            return

        if success and self.settle_time > 0:
            # delay gratification until the settle time is up
            self._settle_thread = threading.Thread(
                target=self._settle_then_run_callbacks, daemon=True,
                kwargs=dict(success=success),
            )
            self._settle_thread.start()
        else:
            self._settle_then_run_callbacks(success=success)

    @property
    def callbacks(self):
        """
        Callbacks to be run when the status is marked as finished

        The callback has no arguments ::

            def cb() -> None:

        """
        return self._callbacks

    @property
    @_locked
    def finished_cb(self):
        if len(self.callbacks) == 1:
            warn("The property `finished_cb` is deprecated, and must raise "
                 "an error if a status object has multiple callbacks. Use "
                 "the `callbacks` property instead.", stacklevel=2)
            cb, = self.callbacks
            assert cb is not None
            return cb
        else:
            raise UseNewProperty("The deprecated `finished_cb` property "
                                 "cannot be used for status objects that have "
                                 "multiple callbacks. Use the `callbacks` "
                                 "property instead.")

    @_locked
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
    @_locked
    def finished_cb(self, cb):
        if not self.callbacks:
            warn("The setter `finished_cb` is deprecated, and must raise "
                 "an error if a status object already has one callback. Use "
                 "the `add_callback` method instead.", stacklevel=2)
            self.add_callback(cb)
        else:
            raise UseNewProperty("The deprecated `finished_cb` setter cannot "
                                 "be used for status objects that already "
                                 "have one callback. Use the `add_callbacks` "
                                 "method instead.")

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

        def inner():
            with self._lock:
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
        return ('{0}(done={1.done}, '
                'success={1.success})'
                ''.format(self.__class__.__name__, self)
                )


class Status(StatusBase):
    """A basic status object

    Has an optional associated object instance

    Attributes
    ----------
    obj : any or None
        The object
    """
    def __init__(self, obj=None, **kwargs):
        self.obj = obj
        super().__init__(**kwargs)

    def __str__(self):
        return ('{0}(obj={1.obj}, '
                'done={1.done}, '
                'success={1.success})'
                ''.format(self.__class__.__name__, self)
                )

    __repr__ = __str__


class DeviceStatus(StatusBase):
    """Device status

    Parameters
    ----------
    device : obj
    done : bool, optional
        Whether or not the motion has already completed
    success : bool, optional
        If motion has already completed, the status of that motion
    timeout : float, optional
        The default timeout to use for a blocking wait, and the amount of time
        to wait to mark the motion as failed
    settle_time : float, optional
        The amount of time to wait between motion completion and running
        callbacks
    """
    def __init__(self, device, **kwargs):
        self.device = device
        self._watchers = []
        super().__init__(**kwargs)

    def _handle_failure(self):
        super()._handle_failure()
        logger.debug('Trying to stop %s', repr(self.device))
        self.device.stop()

    def __str__(self):
        return ('{0}(device={1.device.name}, done={1.done}, '
                'success={1.success})'
                ''.format(self.__class__.__name__, self)
                )

    def watch(self, func):
        # See MoveStatus.watch for a richer implementation and more info.
        if self.device is not None:
            self._watchers.append(func)
            func(name=self.device.name)

    def _settled(self):
        '''Hook for when status has completed and settled'''
        for watcher in self._watchers:
            watcher(name=self.device.name, fraction=1)

    __repr__ = __str__


class SubscriptionStatus(DeviceStatus):
    """
    Status updated via `ophyd` events

    Parameters
    ----------
    device : obj

    callback : callable
        Callback that takes event information and returns a boolean. Signature
        should be `f(*args, **kwargs)`

    event_type : str, optional
        Name of event type to check whether the device has finished succesfully

    timeout : float, optional
        Maximum timeout to wait to mark the request as a failure

    settle_time : float, optional
        Time to wait after completion until running callbacks

    run: bool, optional
        Run the callback now
    """
    def __init__(self, device, callback, event_type=None,
                 timeout=None, settle_time=None, run=True):
        # Store device and attribute information
        self.device = device
        self.callback = callback

        # Start timeout thread in the background
        super().__init__(device, timeout=timeout, settle_time=settle_time)

        # Subscribe callback and run initial check
        self.device.subscribe(self.check_value,
                              event_type=event_type,
                              run=run)

    def check_value(self, *args, **kwargs):
        """
        Update the status object
        """
        # Get attribute from device
        try:
            success = self.callback(*args, **kwargs)

        # Do not fail silently
        except Exception as e:
            logger.error(e)
            raise

        # If successfull indicate completion
        if success:
            self._finished(success=True)

    def _finished(self, *args, **kwargs):
        """
        Reimplemented finished command to cleanup callback subscription
        """
        # Clear callback
        self.device.clear_sub(self.check_value)
        # Run completion
        super()._finished(**kwargs)


class MoveStatus(DeviceStatus):
    """Asynchronous movement status

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

    def __init__(self, positioner, target, *, start_ts=None,
                 **kwargs):
        self._tname = 'timeout for {}'.format(positioner.name)
        if start_ts is None:
            start_ts = time.time()

        self.pos = positioner
        self.target = target
        self.start_ts = start_ts
        self.start_pos = self.pos.position
        self.finish_ts = None
        self.finish_pos = None

        self._unit = getattr(self.pos, 'egu', None)
        self._precision = getattr(self.pos, 'precision', None)
        self._name = self.pos.name

        # call the base class
        super().__init__(positioner, **kwargs)

        # Notify watchers (things like progress bars) of new values
        # at the device's natural update rate.
        if not self.done:
            self.pos.subscribe(self._notify_watchers,
                               event_type=self.pos.SUB_READBACK)

    def watch(self, func):
        """
        Subscribe to notifications about progress. Useful for progress bars.

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
            watcher(name=self._name,
                    current=current,
                    initial=initial,
                    target=target,
                    unit=self._unit,
                    precision=self._precision,
                    time_elapsed=time_elapsed,
                    fraction=fraction)

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
        return ('{0}(done={1.done}, pos={1.pos.name}, '
                'elapsed={1.elapsed:.1f}, '
                'success={1.success}, settle_time={1.settle_time})'
                ''.format(self.__class__.__name__, self)
                )

    __repr__ = __str__


def wait(status, timeout=None, *, poll_rate=0.05):
    """(Blocking) wait for the status object to complete

    Parameters
    ----------
    timeout : float, optional
        Amount of time in seconds to wait. None disables, such that wait() will
        only return when either the status completes or if interrupted by the
        user.
    poll_rate : float, optional
        Polling rate used to check the status

    Raises
    ------
    TimeoutError
        If time waited exceeds specified timeout
    RuntimeError
        If the status failed to complete successfully
    """
    t0 = time.time()

    def time_exceeded():
        return timeout is not None and (time.time() - t0) > timeout

    while not status.done and not time_exceeded():
        time.sleep(poll_rate)

    if status.done:
        if status.success is not None and not status.success:
            raise RuntimeError('Operation completed but reported an error: {}'
                               ''.format(status))
    elif time_exceeded():
        elapsed = time.time() - t0
        raise TimeoutError('Operation failed to complete within {} seconds '
                           '(elapsed {:.2f} sec)'.format(timeout, elapsed))
