from collections import defaultdict
import time
import logging

from .status import (StatusBase, MoveStatus, DeviceStatus)

logger = logging.getLogger(__name__)


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

        # find magic class attributes to name 'event' types.
        # for publicly exposed event types
        self._pub_event_types = tuple(getattr(self, k) for k in dir(self) if
                                      k.startswith('SUB_'))
        # and for private event types
        self._priv_event_types = tuple(getattr(self, k) for k in dir(self) if
                                       k.startswith('_SUB_'))

        self._subs = {k: [] for k in
                      self._pub_event_types + self._priv_event_types}

        self._sub_cache = defaultdict(lambda: None)

    @property
    def connected(self):
        '''If the device is connected.

        Subclasses should override this'''
        return True

    @property
    def parent(self):
        '''The parent of the ophyd object.

        If at the top of its hierarchy, `parent` will be None
        '''
        return self._parent

    @property
    def root(self):
        "Walk parents to find ultimate ancestor (parent's parent...)."
        root = self
        while True:
            if root.parent is None:
                return root
            root = root.parent

    @property
    def report(self):
        '''A report on the object.'''
        return {}

    @property
    def event_types(self):
        '''Events that can be subscribed to via `obj.subscribe`
        '''
        return self._pub_event_types

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
            logger.error('Subscription %s callback exception (%s)',
                         kwargs['sub_type'],
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

    def _run_subs(self, *args, sub_type, **kwargs):
        '''Run a set of subscription callbacks

        Only the kwarg ``sub_type`` is required, indicating
        the type of callback to perform. All other positional arguments
        and kwargs are passed directly to the callback function.

        No exceptions are raised when the callback functions fail.

        Parameters
        ----------
        sub_type : str
            The name of the event (sub_type) to run all of the callbacks for.
        '''
        kwargs['sub_type'] = sub_type
        kwargs.setdefault('obj', self)

        # And if a timestamp key exists, but isn't filled -- supply it with
        # a new timestamp
        if 'timestamp' in kwargs and kwargs['timestamp'] is None:
            kwargs['timestamp'] = time.time()

        # Shallow-copy the callback arguments for replaying the
        # callback at a later time (e.g., when a new subscription is made)
        self._sub_cache[sub_type] = (tuple(args), dict(kwargs))

        for cb in tuple(self._subs[sub_type]):
            self._run_sub(cb, *args, **kwargs)

    def subscribe(self, cb, event_type=None, run=True):
        '''Subscribe to events this signal group emits

        .. warning::

           If the callback raises any exceptions when run they will be
           silently ignored.

        Parameters
        ----------
        cb : callable
            A callable function (that takes kwargs) to be run when the event is
            generated.  The expected signature is ::

              def cb(*args, obj: OphydObject, sub_type: str, **kwargs) -> None:

            The exact args/kwargs passed are whatever are passed to
            ``_run_subs``
        event_type : str, optional
            The name of the event to subscribe to (if None, defaults to
            the default sub for the instance - obj._default_sub)

            This maps to the ``sub_type`` kwargs in `_run_subs`
        run : bool, optional
            Run the callback now

        See Also
        --------
        clear_sub, _run_subs

        '''
        if event_type is None:
            event_type = self._default_sub

        if event_type is None:
            raise ValueError('Subscription type not set and object {} of class'
                             ' {} has no default subscription set'
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
