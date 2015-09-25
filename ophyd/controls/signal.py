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

from ..utils import (ReadOnlyError, TimeoutError, LimitError)
from ..utils.epics_pvs import (get_pv_form,
                               waveform_to_string, raise_if_disconnected)
from .ophydobj import OphydObject, DetectorStatus

logger = logging.getLogger(__name__)


class Signal(OphydObject):
    '''A signal, which can have a read-write or read-only value.

    Parameters
    ----------
    separate_readback : bool, optional
        If the readback value isn't coming from the same source as the setpoint
        value, set this to True.
    value : any, optional
        The initial value
    setpoint : any, optional
        The initial setpoint value
    recordable : bool
        A flag to indicate if the signal is recordable by DAQ
    '''
    SUB_SETPOINT = 'setpoint'
    SUB_VALUE = 'value'

    def __init__(self, separate_readback=False,
                 value=None, setpoint=None,
                 recordable=True, **kwargs):

        self._default_sub = self.SUB_VALUE
        super().__init__(**kwargs)

        self._setpoint = setpoint
        self._readback = value
        self._recordable = recordable

        self._separate_readback = separate_readback

    @property
    def connected(self):
        '''Subclasses should override this'''
        return True

    @property
    def recordable(self):
        """Return if this signal is recordable by the DAQ"""
        return self._recordable

    def __repr__(self):
        repr = ['value={0.value!r}'.format(self)]
        if self._separate_readback:
            repr.append('setpoint={0.setpoint!r}'.format(self))
        return self._get_repr(repr)

    def get_setpoint(self):
        '''Get the value of the setpoint'''
        return self._setpoint

    def put(self, value, allow_cb=True, force=False, **kwargs):
        '''Set the setpoint value internally.

        .. note:: A timestamp will be generated if none is passed via kwargs.

        Keyword arguments are passed on to callbacks

        Parameters
        ----------
        value
            The value to set
        allow_cb : bool, optional
            Allow callbacks (subscriptions) to happen
        force : bool, optional
            Skip checking the value first
        '''
        if not force:
            self.check_value(value)

        old_value = self._setpoint
        self._setpoint = value

        if not self._separate_readback:
            self._set_readback(value)

        if allow_cb:
            timestamp = kwargs.pop('timestamp', time.time())
            self._run_subs(sub_type=Signal.SUB_SETPOINT,
                           old_value=old_value, value=value,
                           timestamp=timestamp, **kwargs)

    # getters/setters of properties are defined as lambdas so subclasses
    # can override them without redefining the property
    setpoint = property(lambda self: self.get_setpoint(),
                        lambda self, value: self.put(value),
                        doc='The setpoint value for the signal')

    # - Readback value
    def get(self):
        '''Get the readback value'''
        return self._readback

    # - Value reads from readback, and writes to setpoint
    value = property(lambda self: self.get(),
                     lambda self, value: self.put(value),
                     doc='The value associated with the signal')

    def _set_readback(self, value, allow_cb=True, **kwargs):
        '''Set the readback value internally'''
        old_value = self._readback
        self._readback = value

        if allow_cb:
            timestamp = kwargs.pop('timestamp', time.time())
            self._run_subs(sub_type=Signal.SUB_VALUE,
                           old_value=old_value, value=value,
                           timestamp=timestamp, **kwargs)

    def read(self):
        '''Put the status of the signal into a simple dictionary format
        for data acquisition

        Returns
        -------
            dict
        '''
        if self._separate_readback:
            return {'alias': self.alias,
                    'setpoint': self.setpoint,
                    'readback': self.readback,
                    }
        else:
            return {'alias': self.alias,
                    'value': self.value,
                    }

    def describe(self):
        """Return the description as a dictionary"""
        return {self.name: {'source': 'SIM:{}'.format(self.name),
                            'dtype': 'number',
                            'shape': []}}


class EpicsSignal(Signal):
    '''An EPICS signal, comprised of either one or two EPICS PVs

    =======  =========  =====  ==========================================
    read_pv  write_pv   rw     Result
    =======  ========   ====   ==========================================
    str      None       True   read_pv is used as write_pv
    str      None       False  Read-only signal
    str      str        True   Read from read_pv, write to write_pv
    str      str        False  write_pv ignored.
    =======  ========   ====   ==========================================

    Keyword arguments are passed on to the base class (Signal) initializer

    Parameters
    ----------
    read_pv : str
        The PV to read from
    write_pv : str, optional
        The PV to write to required)
    rw : bool, optional
        Read-write signal (or read-only)
    pv_kw : dict, optional
        Keyword arguments for epics.PV(**pv_kw)
    limits : bool, optional
        Check limits prior to writing value
    auto_monitor : bool, optional
        Use automonitor with epics.PV
    '''
    def __init__(self, read_pv, write_pv=None,
                 rw=True, pv_kw=None,
                 put_complete=False,
                 string=False,
                 limits=False,
                 auto_monitor=None,
                 **kwargs):
        if pv_kw is None:
            pv_kw = dict()
        self._read_pv = None
        self._write_pv = None
        self._put_complete = put_complete
        self._string = bool(string)
        self._check_limits = bool(limits)
        self._rw = rw
        self._pv_kw = pv_kw
        self._auto_monitor = auto_monitor

        separate_readback = False

        if not rw:
            write_pv = None
        elif write_pv is not None:
            if write_pv == read_pv:
                write_pv = None
            else:
                separate_readback = True

        name = kwargs.pop('name', read_pv)
        super().__init__(separate_readback=separate_readback, name=name,
                        **kwargs)

        self._read_pv = epics.PV(read_pv, form=get_pv_form(),
                                 callback=self._read_changed,
                                 connection_callback=self._connection_cb,
                                 auto_monitor=auto_monitor,
                                 **pv_kw)

        if write_pv is not None:
            self._write_pv = epics.PV(write_pv, form=get_pv_form(),
                                      callback=self._write_changed,
                                      connection_callback=self._connection_cb,
                                      auto_monitor=auto_monitor,
                                      **pv_kw)
        elif rw:
            self._write_pv = self._read_pv

    @property
    @raise_if_disconnected
    def precision(self):
        '''The precision of the read PV, as reported by EPICS'''
        return self._read_pv.precision

    @property
    @raise_if_disconnected
    def setpoint_ts(self):
        '''Timestamp of setpoint PV, according to EPICS'''
        if self._write_pv is None:
            raise ReadOnlyError('Read-only EPICS signal')

        return self._write_pv.timestamp

    @property
    @raise_if_disconnected
    def timestamp(self):
        '''Timestamp of readback PV, according to EPICS'''
        return self._read_pv.timestamp

    @property
    def pvname(self):
        '''The readback PV name'''
        try:
            return self._read_pv.pvname
        except AttributeError:
            return None

    @property
    def setpoint_pvname(self):
        '''The setpoint PV name'''
        try:
            return self._write_pv.pvname
        except AttributeError:
            return None

    def __repr__(self):
        repr = ['read_pv={0._read_pv.pvname!r}'.format(self)]
        if self._write_pv is not None:
            repr.append('write_pv={0._write_pv.pvname!r}'.format(self))

        repr.append('rw={0._rw!r}, string={0._string!r}'.format(self))
        repr.append('limits={0._check_limits!r}'.format(self))
        repr.append('put_complete={0._put_complete!r}'.format(self))
        repr.append('pv_kw={0._pv_kw!r}'.format(self))
        repr.append('auto_monitor={0._auto_monitor!r}'.format(self))
        return self._get_repr(repr)

    def _connection_cb(self, pvname=None, conn=None, pv=None, **kwargs):
        '''Connection callback from PyEpics'''
        if conn:
            msg = '%s connected' % pvname
        else:
            msg = '%s disconnected' % pvname

        if self._session is not None:
            self._session.notify_connection(msg)
        else:
            self._ses_logger.debug(msg)

    @property
    def connected(self):
        if self._write_pv is None:
            return self._read_pv.connected
        else:
            return self._read_pv.connected and self._write_pv.connected

    @property
    @raise_if_disconnected
    def limits(self):
        pv = self._write_pv
        pv.get_ctrlvars()
        return (pv.lower_ctrl_limit, pv.upper_ctrl_limit)

    @property
    def low_limit(self):
        return self.limits[0]

    @property
    def high_limit(self):
        return self.limits[1]

    def check_value(self, value):
        '''Check if the value is within the setpoint PV's control limits

        Raises
        ------
        ValueError
        '''
        if value is None:
            raise ValueError('Cannot write None to epics PVs')

        if not self._check_limits:
            return

        low_limit, high_limit = self.limits
        if low_limit >= high_limit:
            return

        if not (low_limit <= value <= high_limit):
            raise LimitError('Value {} outside of range: [{}, {}]'
                             .format(value, low_limit, high_limit))

    # TODO: monitor updates self._readback - this shouldn't be necessary
    #       ... but, there should be a mode of operation without using
    #           monitor updates, e.g., for large arrays
    def get(self, as_string=None, **kwargs):
        if as_string is None:
            as_string = self._string

        if not self._read_pv.connected:
            if not self._read_pv.wait_for_connection():
                raise TimeoutError('Failed to connect to %s' %
                                   self._read_pv.pvname)

        ret = self._read_pv.get(as_string=as_string, **kwargs)

        if as_string:
            return waveform_to_string(ret)
        else:
            return ret

    @raise_if_disconnected
    def get_setpoint(self, **kwargs):
        '''Get the setpoint value (use only if the setpoint PV and the readback
        PV differ)

        Keyword arguments are passed on to epics.PV.get()
        '''
        if kwargs or self._setpoint is None:
            setpoint = self._write_pv.get(**kwargs)
            return self._fix_type(setpoint)
        else:
            return self._setpoint

    def put(self, value, force=False, **kwargs):
        '''Using channel access, set the write PV to `value`.

        Keyword arguments are passed on to callbacks

        Parameters
        ----------
        value : any
            The value to set
        force : bool, optional
            Skip checking the value first
        '''
        if self._write_pv is None:
            raise ReadOnlyError('Read-only EPICS signal')

        if not force:
            self.check_value(value)

        if not self._write_pv.connected:
            if not self._write_pv.wait_for_connection():
                raise TimeoutError('Failed to connect to %s' %
                                   self._write_pv.pvname)

        use_complete = kwargs.get('use_complete', self._put_complete)

        self._write_pv.put(value, use_complete=use_complete,
                           **kwargs)

        Signal.put(self, value, force=True)

    def _fix_type(self, value):
        if self._string:
            value = waveform_to_string(value)

        return value

    def _read_changed(self, value=None, timestamp=None, **kwargs):
        '''A callback indicating that the read value has changed'''
        if timestamp is None:
            timestamp = time.time()

        value = self._fix_type(value)
        self._set_readback(value, timestamp=timestamp)

    def _write_changed(self, value=None, timestamp=None, **kwargs):
        '''A callback indicating that the write value has changed'''
        if timestamp is None:
            timestamp = time.time()

        value = self._fix_type(value)
        Signal.put(self, value, timestamp=timestamp)

    @property
    @raise_if_disconnected
    def report(self):
        # FIXME:
        if self._read_pv == self._write_pv:
            value = self._read_pv.value
            pv = self.pvname
        elif self._read_pv is not None:
            value = self._read_pv.value
            pv = self.pvname
        elif self._write_pv is not None:
            value = self._write_pv.value
            pv = self.setpoint_pvname

        return {self.name: value,
                'pv': pv
                }

    def describe(self):
        """Return the description as a dictionary

        Returns
        -------
        dict
            Dictionary of name and formatted description string
        """
        return {self.name: {'source': 'PV:{}'.format(self._read_pv.pvname),
                            'dtype': 'number',
                            'shape': []}}

    @raise_if_disconnected
    def read(self):
        """Read the signal and format for data collection

        Returns
        -------
        dict
            Dictionary of value timestamp pairs
        """

        return {self.name: {'value': self.value,
                            'timestamp': self.timestamp}}

    def trigger(self):
        try:
            return super().trigger()
        except AttributeError:
            d = DetectorStatus(self)
            d._finished()
            return d


class SkepticalSignal(EpicsSignal):
    def trigger(self):
        d = DetectorStatus(self)
        # scary assumption
        cur = self.read()[self._name]
        old_time = cur['timestamp']

        def local(old_value, value, timestamp, **kwargs):
            if old_time == timestamp:
                # the time stamp has not changed.  Given that
                # this function is being called by a subscription
                # on value changed, this should never happen
                return
            # tell the status object we are done
            d._finished()
            # disconnect this function
            self.clear_sub(local)

        self.subscribe(local, self.SUB_VALUE)

        return d

    def _set_readback(self, value, **kwargs):
        if value == 0.0:
            return
        return super()._set_readback(value, **kwargs)


class SignalGroup(OphydObject):
    '''Create a group or collection of related signals

    Parameters
    ----------
    signals : sequence of Signal, optional
        Signals to add to the group
    '''

    def __init__(self, signals=None, **kwargs):
        super().__init__(**kwargs)

        self._signals = []

        if signals:
            for signal in signals:
                self.add_signal(signal)

    def __repr__(self):
        repr = []

        if self._signals:
            repr.append('signals={0._signals!r}'.format(self))

        if self._alias:
            repr.append('alias={0._alias!r}'.format(self))

        return self._get_repr(repr)

    def add_signal(self, signal, prop_name=None):
        '''Add a signal to the group.

        Parameters
        ----------
        signal : Signal
            The :class:`Signal` to add
        prop_name : str, optional
            The property name to use in the collection.
            e.g., if set to 'sig1', then `group.sig1` would be how to refer to
            the signal.
        '''

        if signal not in self._signals:
            self._signals.append(signal)

            if prop_name is None:
                prop_name = signal.alias

            if prop_name:
                setattr(self, prop_name, signal)

    @property
    def connected(self):
        return all([sig.connected for sig in self._signals])

    def get(self, **kwargs):
        return [signal.get(**kwargs) for signal in self._signals]

    @property
    def signals(self):
        return self._signals

    def put(self, values, **kwargs):
        return [signal.put(value, **kwargs)
                for signal, value in zip(self._signals, values)]

    def get_setpoint(self, **kwargs):
        return [signal.get_setpoint(**kwargs)
                for signal in self._signals]

    setpoint = property(get_setpoint, put,
                        doc='Setpoint list')

    value = property(get, put,
                     doc='Readback value list')

    @property
    def setpoint_ts(self):
        '''Timestamp of setpoint PVs, according to EPICS'''
        def get_ts(signal):
            try:
                return signal.setpoint_ts
            except ReadOnlyError:
                return

        return [get_ts(signal) for signal in self._signals]

    @property
    def timestamp(self):
        '''Timestamp of readback PV, according to EPICS'''
        return [signal.timestamp for signal in self._signals]

    @property
    def pvname(self):
        return [signal.pvname for signal in self._signals]

    @property
    def setpoint_pvname(self):
        return [signal.setpoint_pvname for signal in self._signals]

    @property
    def report(self):
        return [signal.report for signal in self._signals]

    def describe(self):
        """Describe for data acquisition the signals of the group

        This property uses the `recordable` flag in ophyd to filter
        the returned signals of the signal group"""
        descs = {}
        [descs.update(signal.describe()) for signal in self._signals
         if signal.recordable]
        return descs

    def read(self):
        """Read signals for data acquisition

        This method uses the `recordable` flag in ophyd to filter
        the returned signals of the signal group"""
        values = {}
        for signal in self._signals:
            if signal.recordable:
                values.update(signal.read())

        return values

    def trigger(self):
        try:
            return super().trigger()
        except AttributeError:
            d = DetectorStatus(self)
            d._finished()
            return d
