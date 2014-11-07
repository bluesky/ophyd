# vi: ts=4 sw=4
'''

'''

from __future__ import print_function
import logging
import epics
from ..context import get_session_manager


logger = logging.getLogger(__name__)


# TODO: where do our exceptions go?
class OpException(Exception):
    pass


class OpTimeoutError(OpException):
    pass


# TODO: not sure if i like this
class SessionAware(object):
    def __init__(self, session=None):
        self._session = None
        self._ses_logger = logger
        if session is not None:
            self._register_session(session)
        else:
            self._auto_register_session()

    def _register_session(self, session):
        if session is self._session:
            return
        elif self._session is not None:
            self._session.unregister(self)

        if session is None:
            self._session = None
            self._ses_logger = None
        else:
            self._ses_logger = session.register(self)
            self._session = session

    def _auto_register_session(self):
        session = get_session_manager()
        if session is not None:
            self._register_session(session)


class Signal(SessionAware):
    # TODO: no enums in Python 2.x -- if you have a better way, let me know:
    SUB_REQUEST = 'request'
    SUB_READBACK = 'readback'

    def __init__(self, alias=None, session=None,
                 separate_readback=False):
        SessionAware.__init__(self, session=session)

        self._default_sub = self.SUB_READBACK
        self._subs = dict((getattr(self, sub), []) for sub in dir(self)
                          if sub.startswith('SUB_'))

        self._alias = alias
        self._request = None
        self._readback = None

        self._separate_readback = separate_readback

    def __str__(self):
        if self._separate_readback:
            return 'Signal(alias=%s, request=%s, readback=%s)' % \
                (self._alias, self.request, self.readback)
        else:
            return 'Signal(alias=%s, readback=%s)' % \
                (self._alias, self.readback)

    def _run_sub(self, type_, *args, **kwargs):
        for cb in self._subs[type_]:
            try:
                cb(type_, *args, **kwargs)
            except Exception as ex:
                self._ses_logger.error('Subscription %s callback exception (%s)' %
                                       (type_, self), exc_info=ex)

    @property
    def alias(self):
        return self._alias

    # - Request value
    def _get_request(self):
        return self._request

    def _set_request(self, value, allow_cb=True):
        old_value = self._request
        self._request = value

        if not self._separate_readback:
            self._set_readback(value)

        if allow_cb:
            self._run_sub(Signal.SUB_REQUEST,
                          old_value, value)

    request = property(lambda self: self._get_request(),
                       lambda self, value: self._set_request(value),
                       doc='')

    # - Readback value
    @property
    def readback(self):
        return self._readback

    def _set_readback(self, value, allow_cb=True):
        old_value = self._readback
        self._readback = value

        if allow_cb:
            self._run_sub(Signal.SUB_READBACK,
                          old_value, value)

    def subscribe(self, callback, event_type=None):
        if event_type is None:
            event_type = self._default_sub

        self._subs[event_type].append(callback)

    def clear_sub(self, callback, event_type=None):
        '''
        Remove subscription
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
        self._read_pv = None
        self._write_pv = None

        separate_readback = True

        if write_pv is not None:
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

        Signal.__init__(self, separate_readback=separate_readback,
                        **kwargs)

    @property
    def read_pvname(self):
        try:
            return self._read_pv.pvname
        except AttributeError:
            return None

    @property
    def write_pvname(self):
        try:
            return self._write_pv.pvname
        except AttributeError:
            return None

    def __str__(self):
        return 'EpicsSignal(alias={0}, read_pv={1}, write_pv={2})'.format(
            self._alias, self._read_pv, self._write_pv)

    def _connected(self, pvname=None, conn=True, pv=None, **kwargs):
        if self._ses_logger is not None:
            if conn:
                msg = '%s connected' % pvname
            else:
                msg = '%s disconnected' % pvname

            slog = self._ses_logger
            slog.info(msg)

        if self._session is not None:
            self._session.notify_connection(self, pvname)

    def _set_request(self, value, allow_cb=True, wait=True):
        if self._write_pv is None:
            raise RuntimeError('Read-only EPICS signal')

        if not self._write_pv.connected:
            if not self._write_pv.wait_for_connection():
                raise OpTimeoutError('Failed to connect to %s' %
                                     self._write_pv.pvname)

        self._write_pv.put(value, wait=wait)

        Signal._set_request(self, value,
                            allow_cb=allow_cb)

    def _read_changed(self, value=None, **kwargs):
        self._set_readback(value)

    def _write_changed(self, value=None, **kwargs):
        self.request = value

    @property
    def readback(self):
        return self._read_pv.get()

    def read(self):
        ret = Signal.read(self)
        if self._read_pv is not None:
            ret['read_pv'] = self._read_pv.pvname

        if self._write_pv is not None:
            ret['write_pv'] = self._write_pv.pvname

        return ret


class SignalGroup(SessionAware):
    def __init__(self, alias=None, session=None):
        SessionAware.__init__(self, session=session)

        self._default_sub = None
        self._subs = dict((getattr(self, sub), []) for sub in dir(self)
                          if sub.startswith('SUB_'))

        self._signals = []
        self._alias = alias

    def _run_sub(self, type_, *args, **kwargs):
        for cb in self._subs[type_]:
            try:
                cb(type_, *args, **kwargs)
            except Exception as ex:
                self._ses_logger.error('Subscription %s callback exception (%s)' %
                                       (type_, self), exc_info=ex)

    def add_signal(self, signal, prop_name=None):
        if signal not in self._signals:
            self._signals.append(signal)

            if prop_name is None:
                prop_name = signal.alias

            setattr(self, prop_name, signal)

    def subscribe(self, cb, event_type=None):
        if event_type is None:
            event_type = self._default_sub

        self._subs[event_type].append(cb)

    def clear_sub(self, cb, event_type=None):
        if event_type is None:
            for event_type, cbs in self._subs.items():
                try:
                    cbs.remove(callback)
                except ValueError:
                    pass
        else:
            self._subs[event_type].remove(callback)

    def read(self):
        return dict((signal.alias, signal.read())
                    for signal in self._signals)
