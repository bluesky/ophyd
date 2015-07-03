# vi: ts=4 sw=4
'''
:mod:`ophyd.control.ophydobj` - Base object type
================================================

.. module:: ophyd.control.ophydobj
   :synopsis:
'''

from __future__ import print_function

import time

from ..session import register_object


class OphydObject(object):
    '''The base class for all objects in Ophyd

    Handles:
    * Subscription/callback mechanism
    * Registration with session manager

    Parameters
    ----------
    name : str, optional
        The name of the object.  If None, registration is disabled.
    alias : str, optional
        A [potentially simplified] alias of the object
    register : bool, optional
        Attempt to register with the session manager

    Attributes
    ----------
    name
    alias
    '''

    _default_sub = None

    def __init__(self, name=None, alias=None, register=True):
        self._name = name
        if alias is None:
            self._alias = name
        else:
            self._alias = alias

        self._subs = dict((getattr(self, sub), []) for sub in dir(self)
                          if sub.startswith('SUB_') or sub.startswith('_SUB_'))
        self._sub_cache = {}
        self._ses_logger = None

        if register:
            self._register()

    def _run_sub(self, cb, *args, **kwargs):
        '''Run a single subscription callback

        Parameters
        ----------
        cb
            The callback
        '''

        try:
            cb(*args, **kwargs)
        except StopIteration as si:
            raise si
        except Exception as ex:
            raise ex
            sub_type = kwargs['sub_type']
            self._ses_logger.error('Subscription %s callback exception (%s)' %
                                   (sub_type, self), exc_info=ex)

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

        try:
            args, kwargs = self._sub_cache[sub_type]
        except KeyError as ex:
            pass
        else:
            # Cached kwargs includes sub_type
            self._run_sub(cb, *args, **kwargs)

    def _run_subs(self, *args, **kwargs):
        '''Run a set of subscription callbacks

        Only the kwarg :param:`sub_type` is required, indicating
        the type of callback to perform. All other positional arguments
        and kwargs are passed directly to the callback function.

        No exceptions are raised when the callback functions fail;
        they are merely logged with the session logger.
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
            A callable function (that takes kwargs)
            to be run when the event is generated
        event_type : str, optional
            The name of the event to subscribe to (if None,
            defaults to SignalGroup._default_sub)
        run : bool, optional
            Run the callback now
        '''
        if event_type is None:
            event_type = self._default_sub

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

    def _register(self):
        '''Register this object with the session'''
        register_object(self)

    @property
    def name(self):
        return self._name

    @property
    def alias(self):
        '''An alternative name for the signal'''
        return self._alias

    def check_value(self, value, **kwargs):
        '''Check if the value is valid for this object

        Raises
        ------
        ValueError
        '''
        pass

    def __repr__(self):
        return self._get_repr()

    def _get_repr(self, info=None):
        _repr = []

        if self._name:
            _repr.append('name={0._name!r}'.format(self))

        if info:
            _repr.extend(info)

        if self._alias:
            _repr.append('alias={0._alias!r}'.format(self))

        return '{}({})'.format(self.__class__.__name__, ', '.join(_repr))
