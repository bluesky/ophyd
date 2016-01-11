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

from .utils import (ReadOnlyError, TimeoutError, LimitError)
from .utils.epics_pvs import (pv_form,
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

    def __init__(self, *, separate_readback=False, value=None, setpoint=None,
                 timestamp=None, setpoint_ts=None,
                 name=None, parent=None):

        self._default_sub = self.SUB_VALUE
        super().__init__(name=name, parent=parent)

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

    @property
    def enum_strs(self):
        return self._read_pv.enum_strs

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

    def _repr_info(self):
        yield from super()._repr_info()
        yield ('value', self.value)
        yield ('timestamp', self.timestamp)

        if self._separate_readback:
            yield ('setpoint', self.setpoint)
            yield ('setpoint_ts', self.setpoint_ts)

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
        The PV to write to if different from the read PV
    rw : bool, optional
        Read-write signal (or read-only)
    pv_kw : dict, optional
        Keyword arguments for epics.PV(**pv_kw)
    limits : bool, optional
        Check limits prior to writing value
    auto_monitor : bool, optional
        Use automonitor with epics.PV
    '''
    def __init__(self, read_pv, write_pv=None, *,
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

    def _repr_info(self):
        yield from super()._repr_info()
        yield ('read_pv', self._read_pv.pvname)
        if self._write_pv is not None:
            yield ('write_pv', self._write_pv.pvname)

        yield ('rw', self._rw)
        yield ('limits', self._check_limits)
        yield ('put_complete', self._put_complete)
        yield ('pv_kw', self._pv_kw)
        yield ('auto_monitor', self._auto_monitor)

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
