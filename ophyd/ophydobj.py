from itertools import count

import time
import logging

from .status import (StatusBase, MoveStatus, DeviceStatus)

try:
    from enum import IntFlag
except ImportError:
    # we must be in python 3.5
    from .utils._backport_enum import IntFlag


class Kind(IntFlag):
    """
    This is used in the .kind attribute of all OphydObj (Signals, Devices).

    A Device examines its components' .kind atttribute to decide whether to
    traverse it in read(), read_configuration(), or neither. Additionally, if
    decides whether to include its name in `.hints['fields']`.
    """
    omitted = 0
    normal = 1
    config = 2
    hinted = 5  # Notice that bool(hinted & normal) is True.


class UnknownSubscription(KeyError):
    "Subclass of KeyError.  Raised for unknown event type"
    ...


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
    kind : a member the Kind IntEnum (or equivalent integer), optional
        Default is Kind.normal. See Kind for options.

    Attributes
    ----------
    name
    '''

    _default_sub = None

    def __init__(self, *, name=None, parent=None, labels=None,
                 kind=None):
        if labels is None:
            labels = set()
        self._ophyd_labels_ = set(labels)
        if kind is None:
            kind = Kind.normal
        self.kind = kind

        super().__init__()

        # base name and ref to parent, these go with properties
        if name is None:
            name = ''
        self._name = name
        self._parent = parent

        self.subscriptions = {getattr(self, k)
                              for k in dir(type(self))
                              if (k.startswith('SUB') or
                                  k.startswith('_SUB'))}

        # dictionary of wrapped callbacks
        self._callbacks = {k: {} for k in self.subscriptions}
        # this is to maintain api on clear_sub
        self._unwrapped_callbacks = {k: {} for k in self.subscriptions}
        # map cid -> back to which event it is in
        self._cid_to_event_mapping = dict()
        # cache of last inputs to _run_subs, the semi-private way
        # to trigger the callbacks for a given subscription to be run
        self._args_cache = {k: None for k in self.subscriptions}
        # count of subscriptions we have handed out, used to give unique ids
        self._cb_count = count()
        # Create logger name from parent or from module class
        if self.parent:
            base_log = self.parent.log.name
            name = self.name.lstrip(self.parent.name + '_')
        else:
            base_log = self.__class__.__module__
            name = self.name
        # Instantiate logger
        self.log = logging.getLogger(base_log + '.' + name)

    def _validate_kind(self, val):
        if isinstance(val, str):
            val = getattr(Kind, val.lower())
        return val

    @property
    def kind(self):
        return self._kind

    @kind.setter
    def kind(self, val):
        self._kind = self._validate_kind(val)

    @property
    def name(self):
        '''name of the device'''
        return self._name

    @name.setter
    def name(self, name):
        self._name = name

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
        return tuple(self.subscriptions)

    def _run_subs(self, *args, sub_type, **kwargs):
        '''Run a set of subscription callbacks

        Only the kwarg ``sub_type`` is required, indicating
        the type of callback to perform. All other positional arguments
        and kwargs are passed directly to the callback function.

        The host object will be injected into kwargs as 'obj' unless that key
        already exists.

        If the `timestamp` is None, then it will be replaced by the current
        time.

        No exceptions are raised if the callback functions fail.
        '''
        if sub_type not in self.subscriptions:
            raise UnknownSubscription(
                "Unknown subscription {}, must be one of {!r}"
                .format(sub_type, self.subscriptions))

        kwargs['sub_type'] = sub_type
        # Guarantee that the object will be in the kwargs
        kwargs.setdefault('obj', self)

        # And if a timestamp key exists, but isn't filled -- supply it with
        # a new timestamp
        if 'timestamp' in kwargs and kwargs['timestamp'] is None:
            kwargs['timestamp'] = time.time()

        # Shallow-copy the callback arguments for replaying the
        # callback at a later time (e.g., when a new subscription is made)
        self._args_cache[sub_type] = (tuple(args), dict(kwargs))

        for cb in list(self._callbacks[sub_type].values()):
            cb(*args, **kwargs)

    def subscribe(self, cb, event_type=None, run=True):
        '''Subscribe to events this event_type generates.

        The callback will be called as ``cb(*args, **kwargs)`` with
        the values passed to `_run_subs` with the following additional keys:

           sub_type : the string value of the event_type
           obj : the host object, added if 'obj' not already in kwargs

        if the key 'timestamp' is in kwargs _and_ is None, then it will
        be replaced with the current time before running the callback.

        The ``*args``, ``**kwargs`` passed to _run_subs will be cached as
        shallow copies, be aware of passing in mutable data.

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

        Returns
        -------
        cid : int
            id of callback, can be passed to `unsubscribe` to remove the
            callback

        '''
        if not callable(cb):
            raise ValueError("cb must be callable")
        # do default event type
        if event_type is None:
            # warnings.warn("Please specify which call back you wish to "
            #               "attach to defaulting to {}"
            #               .format(self._default_sub), stacklevel=2)
            event_type = self._default_sub

        if event_type is None:
            raise ValueError('Subscription type not set and object {} of class'
                             ' {} has no default subscription set'
                             ''.format(self.name, self.__class__.__name__))

        # check that this is a valid event type
        if event_type not in self.subscriptions:
            raise UnknownSubscription(
                "Unknown subscription {}, must be one of {!r}"
                .format(event_type, self.subscriptions))

        # wrapper for callback to snarf exceptions
        def wrap_cb(cb):
            def inner(*args, **kwargs):
                try:
                    cb(*args, **kwargs)
                except Exception:
                    sub_type = kwargs['sub_type']
                    self.log.exception('Subscription %s callback '\
                                       'exception (%s)',
                                       sub_type, self)
            return inner
        # get next cid
        cid = next(self._cb_count)
        wrapped = wrap_cb(cb)
        self._unwrapped_callbacks[event_type][cid] = cb
        self._callbacks[event_type][cid] = wrapped
        self._cid_to_event_mapping[cid] = event_type

        if run:
            cached = self._args_cache[event_type]
            if cached is not None:
                args, kwargs = cached
                wrapped(*args, **kwargs)

        return cid

    def _reset_sub(self, event_type):
        '''Remove all subscriptions in an event type'''
        self._callbacks[event_type].clear()
        self._unwrapped_callbacks[event_type].clear()

    def clear_sub(self, cb, event_type=None):
        '''Remove a subscription, given the original callback function

        See also :meth:`subscribe`, :meth:`unsubscribe`

        Parameters
        ----------
        cb : callable
            The callback
        event_type : str, optional
            The event to unsubscribe from (if None, removes it from all event
            types)
        '''
        if event_type is None:
            event_types = self.event_types
        else:
            event_types = [event_type]
        cid_list = []
        for et in event_types:
            for cid, target in self._unwrapped_callbacks[et].items():
                if cb == target:
                    cid_list.append(cid)
        for cid in cid_list:
            self.unsubscribe(cid)

    def unsubscribe(self, cid):
        """Remove a subscription

        See also :meth:`subscribe`, :meth:`clear_sub`

        Parameters
        ----------
        cid : int
           token return by :meth:`subscribe`
        """
        ev_type = self._cid_to_event_mapping.pop(cid, None)
        if ev_type is None:
            return
        del self._unwrapped_callbacks[ev_type][cid]
        del self._callbacks[ev_type][cid]

    def unsubscribe_all(self):
        for ev_type in self._callbacks:
            self._reset_sub(ev_type)

    def check_value(self, value, **kwargs):
        '''Check if the value is valid for this object

        This function does no normalization, but may raise if the
        value is invalid.

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
