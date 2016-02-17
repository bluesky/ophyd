import time
from threading import RLock
from functools import wraps

import threading
import numpy as np


# This is used below by StatusBase.
def _locked(func):
    "an decorator for running a method with the instance's lock"
    @wraps(func)
    def f(self, *args, **kwargs):
        with self._lock:
            func(self, *args, **kwargs)

    return f


class StatusBase:
    """
    This is a base class that provides a single-slot
    call back for finished.

    Parameters
    ----------
    timeout : float, optional
        The default timeout to use for a blocking wait, and the amount of time
        to wait to mark the operation as failed
    """
    def __init__(self, *, timeout=None, timestamp=None):
        super().__init__()
        self._lock = RLock()
        self._callbacks = set()
        self.done = False
        self.success = None
        self.timeout = None
        self.finish_ts = None

        if timestamp is None:
            timestamp = time.time()
        self.start_ts = timestamp

        if timeout is not None:
            self.timeout = float(timeout)

        if self.timeout is not None:
            thread = threading.Thread(target=self._timeout_thread, daemon=True)
            self._timeout_thread = thread
            self._timeout_thread.start()

    def _timeout_thread(self):
        '''Handle timeout'''
        try:
            wait(self, timeout=self.timeout,
                 poll_rate=max(1.0, self.timeout / 10.0))
        except TimeoutError:
            self._finished(success=False)
        except RuntimeError:
            pass
        finally:
            self._timeout_thread = None

    @_locked
    def _finished(self, *, success=True, timestamp=None, **kwargs):
        # args/kwargs are not really used, but are passed - because pyepics
        # gives in a bunch of kwargs that we don't care about
        self.success = success
        self.done = True
        if timestamp is None:
            timestamp = time.time()
        self.finish_ts = timestamp
        for cb in list(self._callbacks):
            cb()
            self._callbacks.remove(cb)

    @property
    def callbacks(self):
        """
        Callbacks to be run when the status is marked as finished

        The call back has no arguments
        """
        return self._callbacks

    @_locked
    def add_callback(self, cb):
        if self.done:
            cb()
        else:
            self._callbacks.add(cb)

    def __and__(self, other):
        """
        Returns a new 'composite' status object, OrStatus,
        with the same base API.

        It will finish when both `self` or `other` finish.
        """
        return AndStatus(self, other)

    @property
    def elapsed(self):
        if self.finish_ts is None:
            return time.time() - self.start_ts
        else:
            return self.finish_ts - self.start_ts

    def __repr__(self):
        return '{0}(done={1.done}, elapsed={1.elapsed:.1f}, ' \
               'success={1.success})'.format(self.__class__.__name__, self)


class AndStatus(StatusBase):
    "a Status that has composes two other Status objects using logical and"
    def __init__(self, left, right, *, timestamp=None, timeout=None):
        super().__init__(timestamp=timestamp, timeout=timeout)
        self.left = left
        self.right = right

        def inner():
            with self._lock:
                l_success = self.left.success  # alias for readability below
                r_success = self.right.success

                # At least one is done.
                # If it failed, do not wait for the second one.
                if (not l_success) and (l_success is not None):
                    self._finished(success=False)
                elif (not r_success) and (r_success is not None):
                    self._finished(success=False)

                elif l_success and r_success:
                    # both are done, successfully
                    success = l_success and r_success
                    self._finished(success=success)
                # else one is done, successfully, and we wait for #2

        self.left.add_callback(inner)
        self.right.add_callback(inner)

    def __repr__(self):
        return "({self.left!r} & {self.right!r})".format(self=self)


class MoveStatus(StatusBase):
    '''Asynchronous movement status

    Parameters
    ----------
    positioner : Positioner
    target : float or array-like
        Target position
    done : bool, optional
        Whether or not the motion has already completed
    start_ts : float, optional
        The motion start timestamp
    timeout : float, optional
        The default timeout to use for a blocking wait, and the amount of time
        to wait to mark the motion as failed

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

    def __init__(self, positioner, target, *, done=False, timestamp=None,
                 timeout=None):
        super().__init__(timestamp=timestamp, timeout=timeout)

        self.done = done
        self.pos = positioner
        self.target = target
        self.finish_pos = None

    @property
    def error(self):
        if self.finish_pos is not None:
            finish_pos = self.finish_pos
        else:
            finish_pos = self.pos.position

        try:
            return np.array(finish_pos) - np.array(self.target)
        except Exception:
            return None

    @_locked
    def _finished(self, *, success=True, timestamp=None, **kwargs):
        self.finish_pos = self.pos.position
        # run super last so that all the state is ready before the
        # callback runs
        super()._finished(success=success, timestamp=timestsamp)


class DeviceStatus(StatusBase):
    "A status object that stashes a reference to a device"
    def __init__(self, device, *, timeout=None, timestamp=None):
        super().__init__(timeout=timeout, timestamp=timestamp)
        self.device = device


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
