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


logger = logging.getLogger(__name__)


# TODO: where do our exceptions go?
class OpException(Exception):
    pass


class OpTimeoutError(OpException):
    pass


class Signal(object):
    '''
    This class represents a signal, which can potentially be a read-write
    or read-only value.
    '''

    # TODO: no enums in Python 2.x -- if you have a better way, let me know:
    SUB_REQUEST = 'request'
    SUB_READBACK = 'readback'

    def __init__(self, alias=None, separate_readback=False):
        '''

        :param alias: An alias for the signal
        :type alias: unicode/str or None

        :param bool separate_readback: If the readback value isn't coming
            from the same source as the request value, set this to True.
        '''

        self._default_sub = self.SUB_READBACK
        self._subs = dict((getattr(self, sub), []) for sub in dir(self)
                          if sub.startswith('SUB_'))

        self._alias = alias
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

    def _run_sub(self, *args, **kwargs):
        '''
        Run a set of callback subscriptions

        Only the kwarg :param:`sub_type` is required, indicating
        the type of callback to perform. All other positional arguments
        and kwargs are passed directly to the callback function.

        No exceptions are raised when the callback functions fail;
        they are merely logged with the session logger.
        '''
        sub_type = kwargs['sub_type']

        for cb in self._subs[sub_type]:
            try:
                cb(*args, **kwargs)
            except Exception as ex:
                self._ses_logger.error('Subscription %s callback exception (%s)' %
                                       (sub_type, self), exc_info=ex)

    @property
    def alias(self):
        '''
        An alternative name for the signal
        '''
        return self._alias

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
            self._run_sub(sub_type=Signal.SUB_REQUEST,
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

    # - Value is the same thing as the readback for simplicity
    value = readback

    def _set_readback(self, value, allow_cb=True, **kwargs):
        old_value = self._readback
        self._readback = value

        if allow_cb:
            timestamp = kwargs.pop('timestamp', time.time())
            self._run_sub(sub_type=Signal.SUB_READBACK,
                          old_value=old_value, value=value,
                          timestamp=timestamp, **kwargs)

    def subscribe(self, callback, event_type=None):
        '''
        Subscribe to events this signal emits

        See also :func:`Signal.clear_sub`

        :param callable callback: A callable function (that takes kwargs)
            to be run when the event is generated
        :param event_type: The name of the event to subscribe to (if None,
            defaults to Signal._default_sub)
        :type event_type: str or None
        '''
        if event_type is None:
            event_type = self._default_sub

        self._subs[event_type].append(callback)

    def clear_sub(self, callback, event_type=None):
        '''
        Remove a subscription, given the original callback function

        See also :func:`Signal.subscribe`

        :param callable callback: The callback
        :param event_type: The event to unsubscribe from (if None, removes it
            from all event types)
        :type event_type: str or None
        '''
        if event_type is None:
            for event_type, cbs in self._subs.items():
                try:
                    cbs.remove(callback)
                except ValueError:
                    pass
        else:
            self._subs[event_type].remove(callback)

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

        separate_readback = True

        Signal.__init__(self, **kwargs)

        if rw and write_pv is not None:
            self._write_pv = epics.PV(write_pv, form='time',
                                      callback=self._write_changed,
                                      connection_callback=self._connected,
                                      **pv_kw)

        if read_pv is not None:
            self._read_pv = epics.PV(read_pv, form='time',
                                     callback=self._read_changed,
                                     connection_callback=self._connected,

                                     **pv_kw)
        else:
            self._read_pv = self._write_pv
            separate_readback = False

        if rw and self._write_pv is None:
            self._write_pv = self._read_pv
            separate_readback = False

        # TODO structure this better -- logger needs to be set
        # by the time we create epics pvs (for connection callback logging)
        self._separate_readback = separate_readback

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
        return 'EpicsSignal(alias={0}, read_pv={1}, write_pv={2})'.format(
            self._alias, self._read_pv, self._write_pv)

    def _connected(self, pvname=None, conn=True, pv=None, **kwargs):
        '''
        Connection callback from PyEpics
        '''
        if conn:
            msg = '%s connected' % pvname
        else:
            msg = '%s disconnected' % pvname

        self._ses_logger.info(msg)

        if self._session is not None:
            self._session.notify_connection(self, pvname)

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
                raise OpTimeoutError('Failed to connect to %s' %
                                     self._write_pv.pvname)

        self._write_pv.put(value, wait=wait, **kwargs)

        Signal._set_request(self, value)

    def _read_changed(self, value=None, **kwargs):
        '''
        A callback indicating that the read value has changed
        '''
        self._set_readback(value, **kwargs)

    def _write_changed(self, value=None, **kwargs):
        '''
        A callback indicating that the write value has changed
        '''
        self._set_request(value, **kwargs)

    def _get_readback(self):
        return self._read_pv.get()

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
            ret['read_pv'] = self._read_pv.pvname

        if self._write_pv is not None:
            ret['write_pv'] = self._write_pv.pvname

        return ret


class SignalGroup(object):
    def __init__(self, alias=None):
        '''
        Create a group or collection of related signals

        :param alias: An alternative name for the signal group
        '''
        self._default_sub = None
        self._subs = dict((getattr(self, sub), []) for sub in dir(self)
                          if sub.startswith('SUB_'))

        self._signals = []
        self._alias = alias

        register_object(self)

    def _run_sub(self, *args, **kwargs):
        '''
        Run a set of callback subscriptions

        Only the kwarg :param:`sub_type` is required, indicating
        the type of callback to perform. All other positional arguments
        and kwargs are passed directly to the callback function.

        No exceptions are raised when the callback functions fail;
        they are merely logged with the session logger.
        '''
        sub_type = kwargs['sub_type']

        for cb in self._subs[sub_type]:
            try:
                cb(*args, **kwargs)
            except Exception as ex:
                self._ses_logger.error('Subscription %s callback exception (%s)' %
                                       (sub_type, self), exc_info=ex)

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

            setattr(self, prop_name, signal)

    def subscribe(self, cb, event_type=None):
        '''
        Subscribe to events this signal group emits

        See also :func:`SignalGroup.clear_sub`

        :param callable cb: A callable function (that takes kwargs)
            to be run when the event is generated
        :param event_type: The name of the event to subscribe to (if None,
            defaults to SignalGroup._default_sub)
        :type event_type: str or None
        '''
        if event_type is None:
            event_type = self._default_sub

        self._subs[event_type].append(cb)

    def clear_sub(self, cb, event_type=None):
        '''
        Remove a subscription, given the original callback function

        See also :func:`SignalGroup.subscribe`

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

    def read(self):
        '''
        See :func:`Signal.read`
        '''
        return dict((signal.alias, signal.read())
                    for signal in self._signals)
