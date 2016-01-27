# vi: ts=4 sw=4
import logging
import time

import epics

from .utils import (ReadOnlyError, TimeoutError, LimitError)
from .utils.epics_pvs import (pv_form, waveform_to_string,
                              raise_if_disconnected, data_type, data_shape)
from .ophydobj import (OphydObject, DeviceStatus)

logger = logging.getLogger(__name__)


class Signal(OphydObject):
    '''A signal, which can have a read-write or read-only value.

    Parameters
    ----------
    value : any, optional
        The initial value
    timestamp : float, optional
        The timestamp associated with the initial value. Defaults to the
        current local time.
    '''
    SUB_VALUE = 'value'
    _default_sub = SUB_VALUE

    def __init__(self, *, value=None, timestamp=None, name=None, parent=None):
        super().__init__(name=name, parent=parent)

        self._readback = value

        if timestamp is None:
            timestamp = time.time()

        self._timestamp = timestamp

    def trigger(self):
        '''Call that is used by bluesky prior to read()'''
        # NOTE: this is a no-op that exists here for bluesky purposes
        #       it may need to be moved in the future
        d = DeviceStatus(self)
        d._finished()
        return d

    @property
    def connected(self):
        '''Subclasses should override this'''
        return True

    def wait_for_connection(self, timeout=0.0):
        '''Wait for the underlying signals to initialize or connect'''
        pass

    @property
    def timestamp(self):
        '''Timestamp of the readback value'''
        return self._timestamp

    def _repr_info(self):
        yield from super()._repr_info()
        yield ('value', self.value)
        yield ('timestamp', self.timestamp)

    def get(self):
        '''The readback value'''
        return self._readback

    def put(self, value, *, timestamp=None, force=False):
        '''Put updates the internal readback value

        The value is optionally checked first, depending on the value of force.
        In addition, VALUE subscriptions are run.

        Parameters
        ----------
        value : any
            Value to set
        timestamp : float, optional
            The timestamp associated with the value, defaults to time.time()
        force : bool, optional
            Check the value prior to setting it, defaults to False
        '''

        # TODO: consider adding set_and_wait here as a kwarg
        if not force:
            self.check_value(value)

        old_value = self._readback
        self._readback = value

        if timestamp is None:
            timestamp = time.time()

        self._timestamp = timestamp
        self._run_subs(sub_type=self.SUB_VALUE, old_value=old_value,
                       value=value, timestamp=self._timestamp)

    @property
    def value(self):
        '''The signal's value'''
        return self.get()

    @value.setter
    def value(self, value):
        self.put(value)

    def read(self):
        '''Put the status of the signal into a simple dictionary format
        for data acquisition

        Returns
        -------
            dict
        '''
        return {self.name: {'value': self.get(),
                            'timestamp': self.timestamp}}

    def describe(self):
        """Return the description as a dictionary"""
        return {self.name: {'source': 'SIM:{}'.format(self.name),
                            'dtype': 'number',
                            'shape': []}}

    def read_configuration(self):
        "Subclasses may customize this."
        return self.read()

    def describe_configuration(self):
        "Subclasses may customize this."
        return self.describe()

    @property
    def limits(self):
        # Always override, never extend this
        return (0, 0)

    @property
    def low_limit(self):
        return self.limits[0]

    @property
    def high_limit(self):
        return self.limits[1]


class EpicsSignalBase(Signal):
    '''A read-only EpicsSignal -- that is, one with no `write_pv`

    Keyword arguments are passed on to the base class (Signal) initializer

    Parameters
    ----------
    read_pv : str
        The PV to read from
    pv_kw : dict, optional
        Keyword arguments for epics.PV(**pv_kw)
    auto_monitor : bool, optional
        Use automonitor with epics.PV
    name : str, optional
        Name of signal.  If not given defaults to read_pv
    string : bool, optional
        Attempt to cast the EPICS PV value to a string by default
    '''
    def __init__(self, read_pv, *,
                 pv_kw=None,
                 string=False,
                 auto_monitor=False,
                 name=None,
                 **kwargs):

        if 'rw' in kwargs:
            if kwargs['rw']:
                new_class = EpicsSignal
            else:
                new_class = EpicsSignalRO

            raise RuntimeError('rw is no longer an option for EpicsSignal. '
                               'Based on your setting of `rw`, you should be '
                               'using this class: {}'
                               ''.format(new_class.__name__))

        if pv_kw is None:
            pv_kw = dict()

        self._read_pv = None
        self._string = bool(string)
        self._pv_kw = pv_kw
        self._auto_monitor = auto_monitor

        if name is None:
            name = read_pv

        super().__init__(name=name, **kwargs)

        self._read_pv = epics.PV(read_pv, form=pv_form,
                                 auto_monitor=auto_monitor,
                                 **pv_kw)

        self._read_pv.add_callback(self._read_changed,
                                   run_now=self._read_pv.connected)

    @property
    def as_string(self):
        '''Attempt to cast the EPICS PV value to a string by default'''
        return self._string

    @property
    @raise_if_disconnected
    def precision(self):
        '''The precision of the read PV, as reported by EPICS'''
        return self._read_pv.precision

    @property
    @raise_if_disconnected
    def enum_strs(self):
        """List of strings if PV is an enum type"""
        return self._read_pv.enum_strs

    def wait_for_connection(self, timeout=1.0):
        if not self._read_pv.connected:
            if not self._read_pv.wait_for_connection(timeout=timeout):
                raise TimeoutError('Failed to connect to %s' %
                                   self._read_pv.pvname)

    @property
    @raise_if_disconnected
    def timestamp(self):
        '''Timestamp of readback PV, according to EPICS'''
        return self._read_pv.timestamp

    @property
    def pvname(self):
        '''The readback PV name'''
        return self._read_pv.pvname

    def _repr_info(self):
        yield ('read_pv', self._read_pv.pvname)
        yield from super()._repr_info()
        yield ('pv_kw', self._pv_kw)
        yield ('auto_monitor', self._auto_monitor)
        yield ('string', self._string)

    @property
    def connected(self):
        return self._read_pv.connected

    @property
    @raise_if_disconnected
    def limits(self):
        '''The read PV limits'''

        # This overrides the base limits
        pv = self._read_pv
        pv.get_ctrlvars()
        return (pv.lower_ctrl_limit, pv.upper_ctrl_limit)

    def get(self, *, as_string=None, **kwargs):
        '''Get the readback value through an explicit call to EPICS

        Parameters
        ----------
        count : int, optional
            Explicitly limit count for array data
        as_string : bool, optional
            Get a string representation of the value, defaults to as_string
            from this signal, optional
        as_numpy : bool
            Use numpy array as the return type for array data.
        timeout : float, optional
            maximum time to wait for value to be received.
            (default = 0.5 + log10(count) seconds)
        use_monitor : bool, optional
            to use value from latest monitor callback or to make an
            explicit CA call for the value. (default: True)
        '''
        # NOTE: in the future this should be improved to grab self._readback
        #       instead, when all of the kwargs match up
        if as_string is None:
            as_string = self._string

        if not self._read_pv.connected:
            if not self._read_pv.wait_for_connection():
                raise TimeoutError('Failed to connect to %s' %
                                   self._read_pv.pvname)

        ret = self._read_pv.get(as_string=as_string, **kwargs)

        if as_string:
            return waveform_to_string(ret)

        return ret

    def _fix_type(self, value):
        if self._string:
            value = waveform_to_string(value)

        return value

    def _read_changed(self, value=None, timestamp=None, **kwargs):
        '''A callback indicating that the read value has changed'''
        if timestamp is None:
            timestamp = time.time()

        value = self._fix_type(value)
        super().put(value, timestamp=timestamp, force=True)


    def describe(self):
        """Return the description as a dictionary

        Returns
        -------
        dict
            Dictionary of name and formatted description string
        """
        desc = {'source': 'PV:{}'.format(self._read_pv.pvname), }

        val = self.value
        desc['dtype'] = data_type(val)
        desc['shape'] = data_shape(val)

        desc['precision'] = self.precision
        desc['units'] = self._read_pv.units

        if hasattr(self, '_write_pv'):
            desc['lower_ctrl_limit'] = self._write_pv.lower_ctrl_limit
            desc['upper_ctrl_limit'] = self._write_pv.upper_ctrl_limit

        if self.enum_strs:
            desc['enum_strs'] = list(self.enum_strs)

        return {self.name: desc}

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


class EpicsSignalRO(EpicsSignalBase):
    '''A read-only EpicsSignal -- that is, one with no `write_pv`

    Keyword arguments are passed on to the base class (Signal) initializer

    Parameters
    ----------
    read_pv : str
        The PV to read from
    pv_kw : dict, optional
        Keyword arguments for epics.PV(**pv_kw)
    limits : bool, optional
        Check limits prior to writing value
    auto_monitor : bool, optional
        Use automonitor with epics.PV
    name : str, optional
        Name of signal.  If not given defaults to read_pv
    '''
    def put(self, *args, **kwargs):
        raise ReadOnlyError('Read-only signals cannot be put to')


class EpicsSignal(EpicsSignalBase):
    '''An EPICS signal, comprised of either one or two EPICS PVs

    Keyword arguments are passed on to the base class (Signal) initializer

    Parameters
    ----------
    read_pv : str
        The PV to read from
    write_pv : str, optional
        The PV to write to if different from the read PV
    pv_kw : dict, optional
        Keyword arguments for epics.PV(**pv_kw)
    limits : bool, optional
        Check limits prior to writing value
    auto_monitor : bool, optional
        Use automonitor with epics.PV
    name : str, optional
        Name of signal.  If not given defaults to read_pv
    put_complete : bool, optional
        Use put completion when writing the value
    '''
    SUB_SETPOINT = 'setpoint'

    def __init__(self, read_pv, write_pv=None, *, pv_kw=None,
                 put_complete=False, string=False, limits=False,
                 auto_monitor=False, name=None, **kwargs):

        self._write_pv = None
        self._use_limits = bool(limits)
        self._put_complete = put_complete

        self._setpoint = None
        self._setpoint_ts = None

        if write_pv == read_pv:
            write_pv = None

        super().__init__(read_pv, pv_kw=pv_kw, string=string,
                         auto_monitor=auto_monitor, name=name, **kwargs)

        if write_pv is not None:
            self._write_pv = epics.PV(write_pv, form=pv_form,
                                      auto_monitor=self._auto_monitor,
                                      **self._pv_kw)
            self._write_pv.add_callback(self._write_changed,
                                        run_now=self._write_pv.connected)
        else:
            self._write_pv = self._read_pv

    def wait_for_connection(self, timeout=1.0):
        super().wait_for_connection(timeout=1.0)

        if self._write_pv is not None and not self._write_pv.connected:
            if not self._write_pv.wait_for_connection(timeout=timeout):
                raise TimeoutError('Failed to connect to %s' %
                                   self._write_pv.pvname)

    @property
    @raise_if_disconnected
    def setpoint_ts(self):
        '''Timestamp of setpoint PV, according to EPICS'''
        return self._write_pv.timestamp

    @property
    def setpoint_pvname(self):
        '''The setpoint PV name'''
        return self._write_pv.pvname

    def _repr_info(self):
        yield from super()._repr_info()
        if self._write_pv is not None:
            yield ('write_pv', self._write_pv.pvname)

        yield ('limits', self._use_limits)
        yield ('put_complete', self._put_complete)

    @property
    def connected(self):
        return self._read_pv.connected and self._write_pv.connected

    @property
    @raise_if_disconnected
    def limits(self):
        '''The write PV limits'''
        # read_pv_limits = super().limits
        pv = self._write_pv
        pv.get_ctrlvars()
        return (pv.lower_ctrl_limit, pv.upper_ctrl_limit)

    def check_value(self, value):
        '''Check if the value is within the setpoint PV's control limits

        Raises
        ------
        ValueError
        '''
        super().check_value(value)

        if value is None:
            raise ValueError('Cannot write None to epics PVs')
        if not self._use_limits:
            return

        low_limit, high_limit = self.limits
        if low_limit >= high_limit:
            return

        if not (low_limit <= value <= high_limit):
            raise LimitError('Value {} outside of range: [{}, {}]'
                             .format(value, low_limit, high_limit))

    @raise_if_disconnected
    def get_setpoint(self, **kwargs):
        '''Get the setpoint value (use only if the setpoint PV and the readback
        PV differ)

        Keyword arguments are passed on to epics.PV.get()
        '''
        setpoint = self._write_pv.get(**kwargs)
        return self._fix_type(setpoint)

    def _write_changed(self, value=None, timestamp=None, **kwargs):
        '''A callback indicating that the write value has changed'''
        if timestamp is None:
            timestamp = time.time()

        value = self._fix_type(value)

        old_value = self._setpoint
        self._setpoint = value
        self._setpoint_ts = timestamp

        if self._read_pv is not self._write_pv:
            self._run_subs(sub_type=self.SUB_SETPOINT,
                           old_value=old_value, value=value,
                           timestamp=self._setpoint_ts, **kwargs)

    def put(self, value, force=False, **kwargs):
        '''Using channel access, set the write PV to `value`.

        Keyword arguments are passed on to callbacks

        Parameters
        ----------
        value : any
            The value to set
        force : bool, optional
            Skip checking the value in Python first
        '''
        if not force:
            self.check_value(value)

        if not self._write_pv.connected:
            if not self._write_pv.wait_for_connection():
                raise TimeoutError('Failed to connect to %s' %
                                   self._write_pv.pvname)

        use_complete = kwargs.get('use_complete', self._put_complete)

        self._write_pv.put(value, use_complete=use_complete,
                           **kwargs)

        old_value = self._setpoint
        self._setpoint = value

        if self._read_pv is self._write_pv:
            # readback and setpoint PV are one in the same, so update the
            # readback as well
            super().put(value, timestamp=time.time(), force=True)
            self._run_subs(sub_type=self.SUB_SETPOINT,
                           old_value=old_value, value=value,
                           timestamp=self.timestamp, **kwargs)

    @property
    def setpoint(self):
        '''The setpoint PV value'''
        return self.get_setpoint()

    @setpoint.setter
    def setpoint(self, value):
        self.put(value)
