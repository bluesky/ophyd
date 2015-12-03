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
from ..utils.epics_pvs import (pv_form,
                               waveform_to_string, raise_if_disconnected)
from .ophydobj import (OphydObject, DeviceStatus)

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
    timestamp : float, optional
        The timestamp associated with the initial value. Defaults to the
        current local time.
    setpoint_ts : float, optional
        The timestamp associated with the initial setpoint value. Defaults to
        the current local time.
    '''
    SUB_SETPOINT = 'setpoint'
    SUB_VALUE = 'value'

    def __init__(self, separate_readback=False, value=None, setpoint=None,
                 timestamp=None, setpoint_ts=None,
                 **kwargs):

        self._default_sub = self.SUB_VALUE
        super().__init__(**kwargs)

        if not separate_readback and setpoint is None:
            setpoint = value

        self._setpoint = setpoint
        self._readback = value

        self._separate_readback = separate_readback

        if setpoint_ts is None:
            setpoint_ts = time.time()

        if timestamp is None:
            timestamp = time.time()

        self._timestamp = timestamp
        self._setpoint_ts = setpoint_ts

    @property
    def connected(self):
        '''Subclasses should override this'''
        return True

    def wait_for_connection(self, timeout=0.0):
        '''Wait for the underlying signals to initialize or connect'''
        pass

    @property
    def setpoint_ts(self):
        '''Timestamp of the setpoint value'''
        return self._setpoint_ts

    @property
    def timestamp(self):
        '''Timestamp of the readback value'''
        return self._timestamp

    def __repr__(self):
        repr = ['value={0.value!r}'.format(self),
                'timestamp={0.timestamp}'.format(self),
                ]

        if self._separate_readback:
            repr.append('setpoint={0.setpoint!r}'.format(self))
            repr.append('setpoint_ts={0.setpoint_ts!r}'.format(self))

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
        self._setpoint_ts = kwargs.pop('timestamp', time.time())

        if not self._separate_readback:
            self._set_readback(value)

        if allow_cb:
            self._run_subs(sub_type=Signal.SUB_SETPOINT,
                           old_value=old_value, value=value,
                           timestamp=self._setpoint_ts, **kwargs)

    # getters/setters of properties are defined as lambdas so subclasses
    # can override them without redefining the property
    setpoint = property(lambda self: self.get_setpoint(),
                        lambda self, value: self.put(value),
                        doc='The setpoint value for the signal')

    def get(self):
        '''The readback value'''
        return self._readback

    # - Value reads from readback, and writes to setpoint
    value = property(lambda self: self.get(),
                     lambda self, value: self.put(value),
                     doc='The value associated with the signal')

    def _set_readback(self, value, allow_cb=True, **kwargs):
        '''Set the readback value internally'''
        old_value = self._readback
        self._readback = value
        self._timestamp = kwargs.pop('timestamp', time.time())

        if allow_cb:
            self._run_subs(sub_type=Signal.SUB_VALUE,
                           old_value=old_value, value=value,
                           timestamp=self._timestamp, **kwargs)

    def read(self):
        '''Put the status of the signal into a simple dictionary format
        for data acquisition

        Returns
        -------
            dict
        '''
        return {self.name: {'value': self.get(),
                            'timestamp': self.timestamp}}

    @property
    def report(self):
        return {self.name: self.get(),
                'pv': None
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

        self._read_pv = epics.PV(read_pv, form=pv_form,
                                 callback=self._read_changed,
                                 auto_monitor=auto_monitor,
                                 **pv_kw)

        if write_pv is not None:
            self._write_pv = epics.PV(write_pv, form=pv_form,
                                      callback=self._write_changed,
                                      auto_monitor=auto_monitor,
                                      **pv_kw)
        elif rw:
            self._write_pv = self._read_pv

    @property
    @raise_if_disconnected
    def precision(self):
        '''The precision of the read PV, as reported by EPICS'''
        return self._read_pv.precision

    def wait_for_connection(self, timeout=1.0):
        if not self._read_pv.connected:
            if not self._read_pv.wait_for_connection(timeout=timeout):
                raise TimeoutError('Failed to connect to %s' %
                                   self._read_pv.pvname)

        if self._write_pv is not None and not self._write_pv.connected:
            if not self._write_pv.wait_for_connection(timeout=timeout):
                raise TimeoutError('Failed to connect to %s' %
                                   self._write_pv.pvname)

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

    @property
    def connected(self):
        if self._write_pv is None:
            return self._read_pv.connected
        else:
            return self._read_pv.connected and self._write_pv.connected

    @property
    @raise_if_disconnected
    def limits(self):
        if self._write_pv is None:
            raise ReadOnlyError('Read-only EPICS signal')

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
        if self._write_pv is None:
            raise ReadOnlyError('Read-only EPICS signal')
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
        if self._write_pv is None:
            raise ReadOnlyError('Read-only EPICS signal')

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
            d = DeviceStatus(self)
            d._finished()
            return d


class EpicsSignalRO(EpicsSignal):
    def __init__(self, read_pv, **kwargs):

        if 'write_pv' in kwargs:
            raise ValueError('Read-only signals do not have a write_pv')
            # TODO half-assed way to make this read-only

        super().__init__(read_pv, rw=False, write_pv=None, **kwargs)


class SkepticalSignal(EpicsSignal):
    def trigger(self):
        d = DeviceStatus(self)
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
        self._index = {}

        if signals:
            for signal in signals:
                self.add_signal(signal)

    def __repr__(self):
        repr = []

        if self._signals:
            repr.append('signals={0._signals!r}'.format(self))

        return self._get_repr(repr)

    def __len__(self):
        '''The number of signals'''
        return len(self.signals)

    def __getitem__(self, idx):
        '''Get a signal by its index'''
        return self._index[idx]

    def __iter__(self):
        '''Iterate over all signals by order of index'''
        for idx, sig in sorted(self._index.items()):
            yield sig

    def iteritems(self):
        '''Iterate over (index, signal)'''
        yield from sorted(self._index.items())

    def add_signal(self, signal, prop_name=None, index=None):
        '''Add a signal to the group.

        Parameters
        ----------
        signal : Signal
            The :class:`Signal` to add
        prop_name : str, optional
            The property name to use in the collection.
            e.g., if set to 'sig1', then `group.sig1` would be how to refer to
            the signal.
        index : int, optional
            Index of signal
        '''

        if signal in self._signals:
            return

        self._signals.append(signal)

        if prop_name:
            setattr(self, prop_name, signal)

        if index is None:
            try:
                index = max(self._index.keys()) + 1
            except ValueError:
                if len(self._index) == 0:
                    # First entry
                    index = 0
                else:
                    # Not sure what happened?
                    raise

        self._index[index] = signal

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
        def get_pvname(signal):
            try:
                return signal.pvname
            except AttributeError:
                pass

        return [get_pvname(signal) for signal in self._signals]

    @property
    def setpoint_pvname(self):
        def get_pvname(signal):
            try:
                return signal.setpoint_pvname
            except AttributeError:
                pass

        return [get_pvname(signal) for signal in self._signals]

    @property
    def report(self):
        return [signal.report for signal in self._signals]

    def describe(self):
        """Describe for data acquisition the signals of the group"""
        descs = {}
        [descs.update(signal.describe()) for signal in self._signals]
        return descs

    def read(self):
        """Read signals for data acquisition"""
        values = {}
        for signal in self._signals:
            values.update(signal.read())

        return values

    def trigger(self):
        try:
            return super().trigger()
        except AttributeError:
            d = DeviceStatus(self)
            d._finished()
            return d

    def wait_for_connection(self, timeout=2.0):
        '''Wait for signals to connect

        Parameters
        ----------
        timeout : float or None
            Overall timeout
        '''
        signals = self._signals

        # start off the connection process
        for sig in signals:
            # TODO api decisions
            if hasattr(sig, 'connect'):
                sig.connect()
            elif hasattr(sig, '_read_pv'):
                sig._read_pv.connect(timeout=0.01)
                if hasattr(sig, '_write_pv') and sig._write_pv is not None:
                    sig._write_pv.connect(timeout=0.01)

        t0 = time.time()
        while timeout is None or (time.time() - t0) < timeout:
            connected = [sig.connected for sig in signals]
            if all(connected):
                return
            time.sleep(min((0.05, timeout / 10.0)))

        unconnected = [sig.name for sig in signals
                       if not sig.connected]

        raise TimeoutError('Failed to connect to all signals: {}'
                           ''.format(', '.join(unconnected)))
