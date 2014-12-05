# vi: ts=4 sw=4
'''
:mod:`ophyd.control.signal` - Ophyd signals
===========================================

.. module:: ophyd.control.signal
   :synopsis:

'''

from __future__ import print_function

import logging
import time

import epics

from ..session import register_object
from ..utils import TimeoutError
from ..utils.epics_pvs import (get_pv_form, waveform_to_string)

logger = logging.getLogger(__name__)


class OphydObject(object):
    _default_sub = None

    def __init__(self, name, alias):
        '''
        Subscription/callback mechanism for registered objects in ophyd sessions.
        '''

        self._subs = dict((getattr(self, sub), []) for sub in dir(self)
                          if sub.startswith('SUB_'))
        self._sub_cache = {}
        self._ses_logger = None
        self._name = name
        self._alias = alias

    def _run_sub(self, cb, *args, **kwargs):
        '''
        Run a single subscription callback

        :param cb: The callback
        '''

        try:
            cb(*args, **kwargs)
        except Exception as ex:
            sub_type = kwargs['sub_type']
            self._ses_logger.error('Subscription %s callback exception (%s)' %
                                   (sub_type, self), exc_info=ex)

    def _run_cached_sub(self, sub_type, cb):
        '''
        Run a single subscription callback using the most recent
        cached arguments

        :param sub_type: The subscription type
        :param cb: The callback
        '''

        try:
            args, kwargs = self._sub_cache[sub_type]
        except KeyError:
            pass
            print('no cached sub', sub_type, 'keys', self._sub_cache.keys())
        else:
            print('running cached sub', sub_type)
            # Cached kwargs includes sub_type
            self._run_sub(cb, *args, **kwargs)

    def _run_subs(self, *args, **kwargs):
        '''
        Run a set of subscription callbacks

        Only the kwarg :param:`sub_type` is required, indicating
        the type of callback to perform. All other positional arguments
        and kwargs are passed directly to the callback function.

        No exceptions are raised when the callback functions fail;
        they are merely logged with the session logger.
        '''
        sub_type = kwargs['sub_type']

        # Shallow-copy the callback arguments for replaying the
        # callback at a later time (e.g., when a new subscription is made)
        self._sub_cache[sub_type] = (tuple(args), dict(kwargs))

        for cb in self._subs[sub_type]:
            self._run_sub(cb, *args, **kwargs)

    def subscribe(self, cb, event_type=None, run=True):
        '''
        Subscribe to events this signal group emits

        See also :func:`clear_sub`

        :param callable cb: A callable function (that takes kwargs)
            to be run when the event is generated
        :param event_type: The name of the event to subscribe to (if None,
            defaults to SignalGroup._default_sub)
        :type event_type: str or None
        :param bool run: Run the callback now
        '''
        if event_type is None:
            event_type = self._default_sub

        self._subs[event_type].append(cb)

        if run:
            self._run_cached_sub(event_type, cb)

    def clear_sub(self, cb, event_type=None):
        '''
        Remove a subscription, given the original callback function

        See also :func:`subscribe`

        :param callable callback: The callback
        :param event_type: The event to unsubscribe from (if None, removes it
            from all event types)
        :type event_type: str or None
        '''
        if event_type is None:
            for event_type, cbs in self._subs.items():
                try:
                    cbs.remove(cb)
                except ValueError:
                    pass
        else:
            self._subs[event_type].remove(cb)

    def register(self):
        '''
        Register this object with the session
        '''
        register_object(self)

    @property
    def name(self):
        return self._name

    @property
    def alias(self):
        '''
        An alternative name for the signal
        '''
        return self._alias


class Signal(OphydObject):
    '''
    This class represents a signal, which can potentially be a read-write
    or read-only value.
    '''

    SUB_REQUEST = 'request'
    SUB_READBACK = 'readback'

    def __init__(self, alias=None, separate_readback=False, name=None):
        '''

        :param alias: An alias for the signal
        :type alias: unicode/str or None

        :param bool separate_readback: If the readback value isn't coming
            from the same source as the request value, set this to True.
        '''

        self._default_sub = self.SUB_READBACK
        OphydObject.__init__(self, name, alias)

        self._request = None
        self._readback = None

        self._separate_readback = separate_readback

        register_object(self)

    def __str__(self):
        if self._separate_readback:
            return 'Signal(alias=%s, request=%s, readback=%s)' % \
                (self._alias, self.request, self.readback)
        else:
            return 'Signal(alias=%s, readback=%s)' % \
                (self._alias, self.readback)

    __repr__ = __str__

    # - Request value
    def _get_request(self):
        return self._request

    def _set_request(self, value, allow_cb=True, **kwargs):
        '''
        Set the request value internally.

        :param value: The value to set
        :param bool allow_cb: Allow callbacks (subscriptions) to happen
        :param dict kwargs: Keyword arguments to pass to callbacks

        .. note:: A timestamp will be generated if none is passed via kwargs.
        '''
        old_value = self._request
        self._request = value

        if not self._separate_readback:
            self._set_readback(value)

        if allow_cb:
            timestamp = kwargs.pop('timestamp', time.time())
            self._run_subs(sub_type=Signal.SUB_REQUEST,
                           old_value=old_value, value=value,
                           timestamp=timestamp, **kwargs)

    request = property(lambda self: self._get_request(),
                       lambda self, value: self._set_request(value),
                       doc='The desired/requested value for the signal')

    # - Readback value
    def _get_readback(self):
        return self._readback

    @property
    def readback(self):
        '''
        The readback value of the signal
        '''
        return self._get_readback()

    # - Value reads from readback, and writes to request
    value = property(lambda self: self._get_readback(),
                     lambda self, value: self._set_request(value),
                     doc='The requested value for the signal')

    def _set_readback(self, value, allow_cb=True, **kwargs):
        old_value = self._readback
        self._readback = value

        if allow_cb:
            timestamp = kwargs.pop('timestamp', time.time())
            self._run_subs(sub_type=Signal.SUB_READBACK,
                           old_value=old_value, value=value,
                           timestamp=timestamp, **kwargs)

    def read(self):
        '''
        Put the status of the signal into a simple dictionary format
        for serialization.

        :returns: dict
        '''
        if self._separate_readback:
            return {'alias': self.alias,
                    'request': self.request,
                    'readback': self.readback,
                    }
        else:
            return {'alias': self.alias,
                    'value': self.readback,
                    }


class EpicsSignal(Signal):
    def __init__(self, read_pv, write_pv=None,
                 rw=True, pv_kw={},
                 put_complete=False,
                 string=False,
                 **kwargs):
        '''
        An EPICS signal, comprised of either one or two EPICS PVs

        :param str read_pv: The PV to read from
        :param write_pv: The PV to write to required)
        :type write_pv: str or None
        :param dict pv_kw: Keyword arguments for epics.PV(**pv_kw)
        :param bool rw: Read-write signal (or read-only)

        ==========================
        read_pv  write_pv   rw     Result
        -------  --------   ----   ------
        str      None       True   read_pv is used as write_pv
        str      None       False  Read-only signal
        str      str        True   Read from read_pv, write to write_pv
        str      str        False  write_pv ignored.
        '''

        self._read_pv = None
        self._write_pv = None
        self._put_complete = put_complete
        self._string = bool(string)

        separate_readback = False

        if not rw:
            write_pv = None
        elif write_pv is not None:
            if write_pv == read_pv:
                write_pv = None
            else:
                separate_readback = True

        Signal.__init__(self, separate_readback=separate_readback, **kwargs)

        self._read_pv = epics.PV(read_pv, form=get_pv_form(),
                                 callback=self._read_changed,
                                 connection_callback=self._connected,
                                 **pv_kw)

        if write_pv is not None:
            self._write_pv = epics.PV(write_pv, form=get_pv_form(),
                                      callback=self._write_changed,
                                      connection_callback=self._connected,
                                      **pv_kw)
        elif rw:
            self._write_pv = self._read_pv

    @property
    def request_ts(self):
        '''
        Timestamp of request PV, according to EPICS
        '''
        if self._write_pv is None:
            raise RuntimeError('Read-only EPICS signal')

        return self._write_pv.timestamp

    @property
    def readback_ts(self):
        '''
        Timestamp of readback PV, according to EPICS
        '''
        return self._read_pv.timestamp

    value_ts = readback_ts

    @property
    def read_pvname(self):
        '''
        The readback PV name
        '''
        try:
            return self._read_pv.pvname
        except AttributeError:
            return None

    @property
    def write_pvname(self):
        '''
        The request/write PV name
        '''
        try:
            return self._write_pv.pvname
        except AttributeError:
            return None

    def __str__(self):
        return 'EpicsSignal(value={0}, read_pv={1}, write_pv={2})'.format(
            self.value, self._read_pv, self._write_pv)

    __repr__ = __str__

    def _connected(self, pvname=None, conn=None, pv=None, **kwargs):
        '''
        Connection callback from PyEpics
        '''
        if conn:
            msg = '%s connected' % pvname
        else:
            msg = '%s disconnected' % pvname

        if self._session is not None:
            self._session.notify_connection(msg)
        else:
            self._ses_logger.info(msg)

    def _set_request(self, value, wait=True, **kwargs):
        '''
        Using channel access, set the write PV to `value`.

        :param value: The value to set
        :param bool allow_cb: Allow callbacks (subscriptions) to happen
        :param dict kwargs: Keyword arguments to pass to callbacks
        '''
        if self._write_pv is None:
            raise RuntimeError('Read-only EPICS signal')

        if not self._write_pv.connected:
            if not self._write_pv.wait_for_connection():
                raise TimeoutError('Failed to connect to %s' %
                                   self._write_pv.pvname)

        use_complete = kwargs.get('use_complete', self._put_complete)
        self._write_pv.put(value, wait=wait, use_complete=use_complete,
                           **kwargs)

        Signal._set_request(self, value)

    def _fix_type(self, value):
        if self._string:
            value = waveform_to_string(value)

        return value

    def _read_changed(self, value=None, timestamp=None, **kwargs):
        '''
        A callback indicating that the read value has changed
        '''
        if timestamp is None:
            timestamp = time.time()

        value = self._fix_type(value)
        self._set_readback(value, timestamp=timestamp)

    def _write_changed(self, value=None, timestamp=None, **kwargs):
        '''
        A callback indicating that the write value has changed
        '''
        if timestamp is None:
            timestamp = time.time()

        value = self._fix_type(value)
        Signal._set_request(self, value, timestamp=timestamp)

    # TODO: monitor updates self._readback - this shouldn't be necessary
    #       ... but, there should be a mode of operation without using
    #           monitor updates, e.g., for large arrays
    def _get_readback(self, as_string=None, **kwargs):
        if as_string is None:
            as_string = self._string

        ret = self._read_pv.get(**kwargs)

        if as_string:
            return waveform_to_string(ret)
        else:
            return ret

    @property
    def readback(self):
        '''
        The readback value, read from EPICS
        '''
        return self._get_readback()

    def read(self):
        '''
        See :func:`Signal.read`
        '''

        ret = Signal.read(self)
        if self._read_pv is not None:
            ret['read_pv'] = self.read_pvname

        if self._write_pv is not None:
            ret['write_pv'] = self.write_pvname

        return ret

    @property
    def report(self):
        # FIXME:
        if self._read_pv == self._write_pv:
            value = self._read_pv.value
            pv = self.read_pvname
        elif self._read_pv is not None:
            value = self._read_pv.value
            pv = self.read_pvname
        elif self._write_pv is not None:
            value = self._read_pv.value
            pv = self.read_pvname

        return {self.name: value,
                'pv': pv
                }


# TODO uniform interface to Signal and SignalGroup

class SignalGroup(OphydObject):
    def __init__(self, name='none', alias=None, **kwargs):
        '''
        Create a group or collection of related signals

        :param alias: An alternative name for the signal group
        '''

        OphydObject.__init__(self, name=name, alias=alias)

        self._signals = []

        self._register()

    def add_signal(self, signal, prop_name=None):
        '''
        Add a signal to the group.

        :param Signal signal: The :class:`Signal` to add
        :param str prop_name: The property name to use in the collection.
            e.g., if set to 'sig1', then `group.sig1` would be how to refer
            to the signal.
        '''

        if signal not in self._signals:
            self._signals.append(signal)

            if prop_name is None:
                prop_name = signal.alias

            if prop_name:
                setattr(self, prop_name, signal)

    def read(self):
        '''
        See :func:`Signal.read`
        '''
        return dict((signal.alias, signal.read())
                    for signal in self._signals)

    def _get_readback(self, **kwargs):
        return [signal._get_readback(**kwargs)
                for signal in self._signals]

    readback = property(_get_readback, doc='Readback list')

    def _get_request(self, **kwargs):
        return [signal._get_request(**kwargs)
                for signal in self._signals]

    def _set_request(self, values, **kwargs):
        return [signal._set_request(value, **kwargs)
                for value, signal in zip(values, self._signals)]

    request = property(_get_request, _set_request,
                       doc='Request list')

    value = property(_get_readback, _set_request,
                     doc='Readback/request value list')

    @property
    def request_ts(self):
        '''
        Timestamp of request PVs, according to EPICS
        '''
        return [signal.request_ts for signal in self._signals]

    @property
    def readback_ts(self):
        '''
        Timestamp of readback PV, according to EPICS
        '''
        return [signal.readback_ts for signal in self._signals]

    value_ts = readback_ts

    @property
    def read_pvname(self):
        return [signal.read_pvname for signal in self._signals]

    @property
    def write_pvname(self):
        return [signal.write_pvname for signal in self._signals]

    @property
    def report(self):
        return [signal.report for signal in self._signals]
