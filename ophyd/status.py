from collections import deque
import time
from threading import RLock
from functools import wraps
from warnings import warn

import logging
import threading
import numpy as np

logger = logging.getLogger(__name__)


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
        self._lock = RLock()
        self._callbacks = deque()
        self.done = done
        self.success = success
        self.timeout = None

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

    def _wait_and_cleanup(self):
        '''Handle timeout'''
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
                logger.debug('Status object %s timed out', str(self))
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
        '''Hook for when status has completed and settled'''
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
            self.done = True
            self._settled()

            for cb in self._callbacks:
                cb()
            self._callbacks.clear()

    def _finished(self, success=True, **kwargs):
        '''Inform the status object that it is done and if it succeeded

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
        '''
        if self.done:
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
    def add_callback(self, cb):
        if self.done:
            cb()
        else:
            self._callbacks.append(cb)

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
    '''A basic status object

    Has an optional associated object instance

    Attributes
    ----------
    obj : any or None
        The object
    '''
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
    '''Device status

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
    '''
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
    '''Asynchronous movement status

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
    '''

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
            fraction = abs(target - current) / abs(initial - target)
        # maybe we can't do math?
        except TypeError:
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
        '''Error between target position and current* position

        * If motion is already complete, the final position is used
        '''
        if self.finish_pos is not None:
            finish_pos = self.finish_pos
        else:
            finish_pos = self.pos.position

        try:
            return np.array(finish_pos) - np.array(self.target)
        except Exception:
            return None

    def _settled(self):
        '''Hook for when motion has completed and settled'''
        super()._settled()
        self.pos.clear_sub(self._notify_watchers)
        self._watchers.clear()
        self.finish_ts = time.time()
        self.finish_pos = self.pos.position

    @property
    def elapsed(self):
        '''Elapsed time'''
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
    '''(Blocking) wait for the status object to complete

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
    '''
    t0 = time.time()

    def time_exceeded():
        return timeout is not None and (time.time() - t0) > timeout

    while not status.done and not time_exceeded():
        time.sleep(poll_rate)

    if status.done:
        if status.success is not None and not status.success:
            raise RuntimeError('Operation completed but reported an error')
    elif time_exceeded():
        elapsed = time.time() - t0
        raise TimeoutError('Operation failed to complete within {} seconds'
                           '(elapsed {} sec)'.format(timeout, elapsed))
