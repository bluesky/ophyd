# vi: ts=4 sw=4
'''
:mod:`ophyd.control.ophydobj` - Base object type
================================================

.. module:: ophyd.control.ophydobj
   :synopsis:
'''

from collections import defaultdict
from threading import RLock
from functools import wraps
import time
import logging
import threading

import numpy as np


logger = logging.getLogger(__name__)


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
        self.timeout = float(timeout)

        if timeout is not None:
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
    def _finished(self, *args, **kwargs):
        # args/kwargs are not really used, but are passed.
        # uncomment these if you want to go hunting
        # if args:
        #     print("this should be empty: {}".format(args))
        # if kwargs:
        #     print("this should be empty: {}".format(kwargs))
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

    def wait(self, timeout=30.0, *, poll_rate=0.05):
        '''(Blocking) wait for the status to complete

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

        while not self.done and not time_exceeded():
            time.sleep(poll_rate)

        if self.done:
            if self.success is not None and not self.success:
                raise RuntimeError('Operation did not successfully complete')
        elif time_exceeded():
            elapsed = time.time() - t0
            raise TimeoutError('Operation failed to complete within {} seconds'
                               '(elapsed {} sec)'.format(timeout, elapsed))


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

    def _finished(self, success=True, timestamp=None, **kwargs):
        with self._lock:
            self.success = success

            if timestamp is None:
                timestamp = time.time()
            self.finish_ts = timestamp
            self.finish_pos = self.pos.position
            # run super last so that all the state is ready before the
            # callback runs
            super()._finished()

    @property
    def elapsed(self):
        if self.finish_ts is None:
            return time.time() - self.start_ts
        else:
            return self.finish_ts - self.start_ts

    def wait(self, timeout=None, *, poll_rate=0.05):
        '''(Blocking) wait for the status to complete

        Parameters
        ----------
        timeout : float, optional
            Amount of time in seconds to wait. If None, defaults to the timeout
            for the MoveStatus object
        poll_rate : float, optional
            Polling rate used to check the status

        Raises
        ------
        TimeoutError
            If time waited exceeds specified timeout
        RuntimeError
            If the status failed to complete successfully
        '''
        if timeout is None:
            timeout = self.timeout
        super().wait(timeout=timeout, poll_rate=poll_rate)

    def __str__(self):
        return '{0}(done={1.done}, elapsed={1.elapsed:.1f}, ' \
               'success={1.success})'.format(self.__class__.__name__,
                                             self)

    __repr__ = __str__


class DetectorStatus(StatusBase):
    def __init__(self, detector):
        super().__init__()
        self.detector = detector


class DeviceStatus(StatusBase):
    def __init__(self, device):
        super().__init__()
        self.device = device


class OphydObject:
    '''The base class for all objects in Ophyd

    Handles:
    * Subscription/callback mechanism

    Parameters
    ----------
    name : str, optional
        The name of the object.
    parent : parent, optional
        The object's parent, if it exists in a hierarchy

    Attributes
    ----------
    name
    '''

    _default_sub = None

    def __init__(self, *, name=None, parent=None):
        super().__init__()

        self.name = name
        self._parent = parent

        self._subs = dict((getattr(self, sub), []) for sub in dir(self)
                          if sub.startswith('SUB_') or sub.startswith('_SUB_'))
        self._sub_cache = defaultdict(lambda: None)

    @property
    def parent(self):
        '''The parent of the ophyd object

        If at the top of its hierarchy, `parent` will be None
        '''
        return self._parent

    def _run_sub(self, cb, *args, **kwargs):
        '''Run a single subscription callback

        Parameters
        ----------
        cb
            The callback
        '''

        try:
            cb(*args, **kwargs)
        except Exception as ex:
            sub_type = kwargs['sub_type']
            logger.error('Subscription %s callback exception (%s)', sub_type,
                         self, exc_info=ex)

    def _run_cached_sub(self, sub_type, cb):
        '''Run a single subscription callback using the most recent
        cached arguments

        Parameters
        ----------
        sub_type
            The subscription type
        cb
            The callback
        '''
        cached = self._sub_cache[sub_type]
        if cached:
            args, kwargs = cached
            self._run_sub(cb, *args, **kwargs)

    def _run_subs(self, *args, **kwargs):
        '''Run a set of subscription callbacks

        Only the kwarg :param:`sub_type` is required, indicating
        the type of callback to perform. All other positional arguments
        and kwargs are passed directly to the callback function.

        No exceptions are raised when the callback functions fail.
        '''
        sub_type = kwargs['sub_type']

        # Guarantee that the object will be in the kwargs
        if 'obj' not in kwargs:
            kwargs['obj'] = self

        # And if a timestamp key exists, but isn't filled -- supply it with
        # a new timestamp
        if 'timestamp' in kwargs and kwargs['timestamp'] is None:
            kwargs['timestamp'] = time.time()

        # Shallow-copy the callback arguments for replaying the
        # callback at a later time (e.g., when a new subscription is made)
        self._sub_cache[sub_type] = (tuple(args), dict(kwargs))

        for cb in self._subs[sub_type]:
            self._run_sub(cb, *args, **kwargs)

    def subscribe(self, cb, event_type=None, run=True):
        '''Subscribe to events this signal group emits

        See also :func:`clear_sub`

        Parameters
        ----------
        cb : callable
            A callable function (that takes kwargs) to be run when the event is
            generated
        event_type : str, optional
            The name of the event to subscribe to (if None, defaults to
            the default sub for the instance - obj._default_sub)
        run : bool, optional
            Run the callback now
        '''
        if event_type is None:
            event_type = self._default_sub

        if event_type is None:
            raise ValueError('Subscription type not set and object {} of class '
                             '{} has no default subscription set'
                             ''.format(self.name, self.__class__.__name__))

        try:
            self._subs[event_type].append(cb)
        except KeyError:
            raise KeyError('Unknown event type: %s' % event_type)

        if run:
            self._run_cached_sub(event_type, cb)

    def _reset_sub(self, event_type):
        '''Remove all subscriptions in an event type'''
        del self._subs[event_type][:]

    def clear_sub(self, cb, event_type=None):
        '''Remove a subscription, given the original callback function

        See also :func:`subscribe`

        Parameters
        ----------
        cb : callable
            The callback
        event_type : str, optional
            The event to unsubscribe from (if None, removes it from all event
            types)
        '''
        if event_type is None:
            for event_type, cbs in self._subs.items():
                try:
                    cbs.remove(cb)
                except ValueError:
                    pass
        else:
            self._subs[event_type].remove(cb)

    def check_value(self, value, **kwargs):
        '''Check if the value is valid for this object

        Raises
        ------
        ValueError
        '''
        pass

    def __repr__(self):
        info = self._repr_info()
        info = ', '.join('{}={!r}'.format(key, value) for key, value in info)
        return '{}({})'.format(self.__class__.__name__, info)

    def _repr_info(self):
        if self.name is not None:
            yield ('name', self.name)

        if self._parent is not None:
            yield ('parent', self.parent.name)

    def __copy__(self):
        info = dict(self._repr_info())
        return self.__class__(**info)
