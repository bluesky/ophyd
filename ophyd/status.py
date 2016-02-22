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
    def __init__(self, *, timeout=None):
        super().__init__()
        self._lock = RLock()
        self._cb = None
        self.done = False
        self.success = False
        self.timeout = None

        if timeout is not None:
            self.timeout = float(timeout)

        if self.timeout is not None:
            thread = threading.Thread(target=self._timeout_thread, daemon=True)
            self._timeout_thread = thread
            self._timeout_thread.start()

    def _timeout_thread(self):
        '''Handle timeout'''
        try:
            self.wait(timeout=self.timeout,
                      poll_rate=max(1.0, self.timeout / 10.0))
        except TimeoutError:
            self._finished(success=False)
        finally:
            self._timeout_thread = None

    @_locked
    def _finished(self, success=True, **kwargs):
        # args/kwargs are not really used, but are passed - because pyepics
        # gives in a bunch of kwargs that we don't care about

        self.success = success
        self.done = True

        if self._cb is not None:
            self._cb()
            self._cb = None

    @property
    def finished_cb(self):
        """
        Callback to be run when the status is marked as finished

        The call back has no arguments
        """
        return self._cb

    @finished_cb.setter
    @_locked
    def finished_cb(self, cb):
        if self._cb is not None:
            raise RuntimeError("Can not change the call back")
        if self.done:
            cb()
        else:
            self._cb = cb


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

    def __init__(self, positioner, target, *, done=False, start_ts=None,
                 timeout=30.0):
        # call the base class
        super().__init__(timeout=timeout)

        self.done = done
        if start_ts is None:
            start_ts = time.time()

        self.pos = positioner
        self.target = target
        self.start_ts = start_ts
        self.finish_ts = None
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
    def _finished(self, success=True, timestamp=None, **kwargs):
        if timestamp is None:
            timestamp = time.time()
        self.finish_ts = timestamp
        self.finish_pos = self.pos.position
        # run super last so that all the state is ready before the
        # callback runs
        super()._finished(success=success)

    @property
    def elapsed(self):
        if self.finish_ts is None:
            return time.time() - self.start_ts
        else:
            return self.finish_ts - self.start_ts

    def __str__(self):
        return '{0}(done={1.done}, elapsed={1.elapsed:.1f}, ' \
               'success={1.success})'.format(self.__class__.__name__,
                                             self)

    __repr__ = __str__


class DeviceStatus(StatusBase):
    '''Device status'''
    def __init__(self, device, *, timeout=None):
        super().__init__(timeout=timeout)
        self.device = device


def wait(status, timeout=30.0, *, poll_rate=0.05):
    '''(Blocking) wait for the status object to complete

    Parameters
    ----------
    timeout : float, optional
        Amount of time in seconds to wait. If None, will wait until
        completed or otherwise interrupted.
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
