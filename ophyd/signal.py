# vi: ts=4 sw=4
import logging
import time
import threading

import numpy as np

from .utils import (ReadOnlyError, LimitError)
from .utils.epics_pvs import (waveform_to_string,
                              raise_if_disconnected, data_type, data_shape,
                              AlarmStatus, AlarmSeverity, validate_pv_name)
from .ophydobj import OphydObject, Kind
from .status import Status
from .utils import set_and_wait
from . import get_cl

logger = logging.getLogger(__name__)


class Signal(OphydObject):
    '''A signal, which can have a read-write or read-only value.

    Parameters
    ----------
    name : string, keyword only
    value : any, optional
        The initial value
    kind : a member the Kind IntEnum (or equivalent integer), optional
        Default is Kind.normal. See Kind for options.
    parent : Device, optional
    timestamp : float, optional
        The timestamp associated with the initial value. Defaults to the
        current local time.
    tolerance : any, optional
        The absolute tolerance associated with the value
    rtolerance : any, optional
        The relative tolerance associated with the value, used in
        set_and_wait as follows

        .. math::

          |setpoint - readback| \leq (tolerance + rtolerance * |readback|)

    cl : namespace, optional
        Control Layer.  Must provide 'get_pv' and 'thread_class'

    Attributes
    ----------
    rtolerance : any, optional
        The relative tolerance associated with the value
    '''
    SUB_VALUE = 'value'
    _default_sub = SUB_VALUE

    def __init__(self, *, name, value=None, timestamp=None, parent=None,
                 labels=None,
                 kind=Kind.hinted, tolerance=None, rtolerance=None, cl=None):
        super().__init__(name=name, parent=parent, kind=kind, labels=labels)
        if cl is None:
            cl = get_cl()
        self.cl = cl
        self._readback = value

        if timestamp is None:
            timestamp = time.time()

        self._timestamp = timestamp
        self._set_thread = None
        self._tolerance = tolerance
        # self.tolerance is a property
        self.rtolerance = rtolerance

    def trigger(self):
        '''Call that is used by bluesky prior to read()'''
        # NOTE: this is a no-op that exists here for bluesky purposes
        #       it may need to be moved in the future
        d = Status(self)
        d._finished()
        return d

    def wait_for_connection(self, timeout=0.0):
        '''Wait for the underlying signals to initialize or connect'''
        pass

    @property
    def timestamp(self):
        '''Timestamp of the readback value'''
        return self._timestamp

    @property
    def tolerance(self):
        '''The absolute tolerance associated with the value.'''
        return self._tolerance

    @tolerance.setter
    def tolerance(self, tolerance):
        self._tolerance = tolerance

    def _repr_info(self):
        yield from super()._repr_info()
        value = self.value
        if value is not None:
            yield ('value', value)
        if self.timestamp is not None:
            yield ('timestamp', self.timestamp)
        if self.tolerance is not None:
            yield ('tolerance', self.tolerance)
        if self.rtolerance is not None:
            yield ('rtolerance', self.rtolerance)

    def get(self, **kwargs):
        '''The readback value'''
        return self._readback

    def put(self, value, *, timestamp=None, force=False, **kwargs):
        '''Put updates the internal readback value

        The value is optionally checked first, depending on the value of force.
        In addition, VALUE subscriptions are run.

        Extra kwargs are ignored (for API compatibility with EpicsSignal kwargs
        pass through).

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

    def set(self, value, *, timeout=None, settle_time=None):
        '''Set is like `put`, but is here for bluesky compatibility

        Returns
        -------
        st : Status
            This status object will be finished upon return in the
            case of basic soft Signals
        '''
        def set_thread():
            try:
                set_and_wait(self, value, timeout=timeout, atol=self.tolerance,
                             rtol=self.rtolerance)
            except TimeoutError:
                self.log.debug('set_and_wait(%r, %s) timed out', self.name,
                             value)
                success = False
            except Exception as ex:
                self.log.debug('set_and_wait(%r, %s) failed', self.name, value,
                             exc_info=ex)
                success = False
            else:
                self.log.debug('set_and_wait(%r, %s) succeeded => %s', self.name,
                             value, self.value)
                success = True
                if settle_time is not None:
                    time.sleep(settle_time)
            finally:
                # keep a local reference to avoid any GC shenanigans
                th = self._set_thread
                # these two must be in this order to avoid a race condition
                self._set_thread = None
                st._finished(success=success)
                del th

        if self._set_thread is not None:
            raise RuntimeError('Another set() call is still in progress')

        st = Status(self)
        self._status = st
        self._set_thread = self.cl.thread_class(target=set_thread)
        self._set_thread.daemon = True
        self._set_thread.start()
        return self._status

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

    @property
    def hints(self):
        if (~Kind.normal & Kind.hinted) & self.kind:
            return {'fields': [self.name]}
        else:
            return {'fields': []}


class DerivedSignal(Signal):
    def __init__(self, derived_from, *, name=None, parent=None, **kwargs):
        '''A signal which is derived from another one

        Parameters
        ----------
        derived_from : Union[Signal, str]
            The signal from which this one is derived.  If a string assumed
            to be a sibling on the parent.
        name : str, optional
            The signal name
        parent : Device, optional
            The parent device
        '''
        super().__init__(name=name, parent=parent, **kwargs)
        if isinstance(derived_from, str):
            derived_from = getattr(parent, derived_from)
        self._derived_from = derived_from
        connected = self._derived_from.connected
        if connected:
            # set up the initial timestamp reporting, if connected
            self._timestamp = self._derived_from.timestamp

        self._derived_from.subscribe(self._derived_value_callback,
                                     event_type=self.SUB_VALUE, run=connected)

    @property
    def derived_from(self):
        '''Signal that this one is derived from'''
        return self._derived_from

    def describe(self):
        '''Description based on the original signal description'''
        desc = self._derived_from.describe()[self._derived_from.name]
        desc['derived_from'] = self._derived_from.name
        return {self.name: desc}

    def _derived_value_callback(self, value=None, timestamp=None, **kwargs):
        value = self.inverse(value)
        self._run_subs(sub_type=self.SUB_VALUE, timestamp=timestamp,
                       value=value)

    def get(self, **kwargs):
        '''Get the value from the original signal'''
        value = self._derived_from.get(**kwargs)
        value = self.inverse(value)
        self._timestamp = self._derived_from.timestamp
        return value

    def inverse(self, value):
        '''Compute original signal value -> derived signal value'''
        return value

    def put(self, value, **kwargs):
        '''Put the value to the original signal'''
        value = self.forward(value)
        res = self._derived_from.put(value, **kwargs)
        self._timestamp = self._derived_from.timestamp
        return res

    def forward(self, value):
        '''Compute derived signal value -> original signal value'''
        return value

    def wait_for_connection(self, timeout=0.0):
        '''Wait for the original signal to connect'''
        return self._derived_from.wait_for_connection(timeout=timeout)

    @property
    def connected(self):
        '''Mirrors the connection state of the original signal'''
        return self._derived_from.connected

    @property
    def limits(self):
        '''Limits from the original signal'''
        return self._derived_from.limits

    def _repr_info(self):
        yield from super()._repr_info()
        yield ('derived_from', self._derived_from)


class EpicsSignalBase(Signal):
    '''A read-only EpicsSignal -- that is, one with no `write_pv`

    Keyword arguments are passed on to the base class (Signal) initializer

    Parameters
    ----------
    read_pv : str
        The PV to read from
    pv_kw : dict, optional
        Keyword arguments for ``epics.PV(**pv_kw)``
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

        self._lock = threading.RLock()
        self._read_pv = None
        self._string = bool(string)
        self._pv_kw = pv_kw
        self._auto_monitor = auto_monitor

        if name is None:
            name = read_pv

        super().__init__(name=name, **kwargs)

        validate_pv_name(read_pv)
        cl = self.cl
        self._read_pv = cl.get_pv(read_pv, form=cl.pv_form,
                                  auto_monitor=auto_monitor,
                                  **pv_kw)

        with self._lock:
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
        with self._lock:
            return self._read_pv.precision

    @property
    @raise_if_disconnected
    def enum_strs(self):
        """List of strings if PV is an enum type"""
        with self._lock:
            return self._read_pv.enum_strs

    @property
    @raise_if_disconnected
    def alarm_status(self):
        """PV status"""
        with self._lock:
            status = self._read_pv.status
            if status is None:
                return None
            return AlarmStatus(status)

    @property
    @raise_if_disconnected
    def alarm_severity(self):
        """PV alarm severity"""
        with self._lock:
            severity = self._read_pv.severity
            if severity is None:
                return None
            return AlarmSeverity(severity)

    def _reinitialize_pv(self, old_instance, **pv_kw):
        '''Reinitialize a PV instance

        Takes care of clearing callbacks, setting PV form, and ensuring
        connectivity status remains the same

        Parameters
        ----------
        old_instance : epics.PV
            The old PV instance
        pv_kw : kwargs
            The parameters to pass to the initializer
        '''
        with self._lock:
            old_instance.clear_callbacks()
            was_connected = old_instance.connected

            new_instance = self.cl.get_pv(old_instance.pvname,
                                          form=old_instance.form, **pv_kw)
            if was_connected:
                new_instance.wait_for_connection()

            return new_instance

    def subscribe(self, callback, event_type=None, run=True):
        if event_type is None:
            event_type = self._default_sub

        # check if this is a setpoint subscription, and we are not explicitly
        # auto monitoring
        obj_mon = (event_type == self.SUB_VALUE and
                   self._auto_monitor is not True)

        # but if the epics.PV has already connected and determined that it
        # should automonitor (based on the maximum automonitor length), then we
        # don't need to reinitialize it
        with self._lock:
            if obj_mon and not self._read_pv.auto_monitor:
                self._read_pv = self._reinitialize_pv(self._read_pv,
                                                      auto_monitor=True,
                                                      **self._pv_kw)
                self._read_pv.add_callback(self._read_changed,
                                           run_now=self._read_pv.connected)

        return super().subscribe(callback, event_type=event_type, run=run)

    def wait_for_connection(self, timeout=1.0):
        if self._read_pv.connected:
            return

        with self._lock:
            if not self._read_pv.wait_for_connection(timeout=timeout):
                raise TimeoutError('Failed to connect to %s' %
                                   self._read_pv.pvname)

    @property
    @raise_if_disconnected
    def timestamp(self):
        '''Timestamp of readback PV, according to EPICS'''
        with self._lock:
            if not self._read_pv.auto_monitor:
                # force updating the timestamp when not using auto monitoring
                self._read_pv.get_timevars()
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
        with self._lock:
            pv = self._read_pv
            pv.get_ctrlvars()
            return (pv.lower_ctrl_limit, pv.upper_ctrl_limit)

    def get(self, *, as_string=None, connection_timeout=1.0, **kwargs):
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
        connection_timeout : float, optional
            If not already connected, allow up to `connection_timeout` seconds
            for the connection to complete.
        '''
        # NOTE: in the future this should be improved to grab self._readback
        #       instead, when all of the kwargs match up
        if as_string is None:
            as_string = self._string

        with self._lock:
            if not self._read_pv.connected:
                if not self._read_pv.wait_for_connection(connection_timeout):
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

        try:
            desc['precision'] = int(self.precision)
        except (ValueError, TypeError):
            pass

        with self._lock:
            desc['units'] = self._read_pv.units

        low_limit, high_limit = self.limits
        desc['lower_ctrl_limit'] = low_limit
        desc['upper_ctrl_limit'] = high_limit

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
        Keyword arguments for ``epics.PV(**pv_kw)``
    limits : bool, optional
        Check limits prior to writing value
    auto_monitor : bool, optional
        Use automonitor with epics.PV
    name : str, optional
        Name of signal.  If not given defaults to read_pv
    '''
    def put(self, *args, **kwargs):
        raise ReadOnlyError('Read-only signals cannot be put to')

    def set(self, *args, **kwargs):
        raise ReadOnlyError('Read-only signals cannot be set')


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
        Keyword arguments for ``epics.PV(**pv_kw)``
    limits : bool, optional
        Check limits prior to writing value
    auto_monitor : bool, optional
        Use automonitor with epics.PV
    name : str, optional
        Name of signal.  If not given defaults to read_pv
    put_complete : bool, optional
        Use put completion when writing the value
    tolerance : any, optional
        The absolute tolerance associated with the value.
        If specified, this overrides any precision information calculated from
        the write PV
    rtolerance : any, optional
        The relative tolerance associated with the value
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
            validate_pv_name(write_pv)
            cl = self.cl
            self._write_pv = cl.get_pv(write_pv, form=cl.pv_form,
                                       auto_monitor=self._auto_monitor,
                                       **self._pv_kw)
            self._write_pv.add_callback(self._write_changed,
                                        run_now=self._write_pv.connected)
        else:
            self._write_pv = self._read_pv

    def subscribe(self, callback, event_type=None, run=True):
        if event_type is None:
            event_type = self._default_sub

        # check if this is a setpoint subscription, and we are not explicitly
        # auto monitoring
        obj_mon = (event_type == self.SUB_SETPOINT and
                   self._auto_monitor is not True)

        # but if the epics.PV has already connected and determined that it
        # should automonitor (based on the maximum automonitor length), then we
        # don't need to reinitialize it
        with self._lock:
            if obj_mon and not self._write_pv.auto_monitor:
                self._write_pv = self._reinitialize_pv(self._write_pv,
                                                       auto_monitor=True,
                                                       **self._pv_kw)
                self._write_pv.add_callback(self._write_changed,
                                            run_now=self._write_pv.connected)

        return super().subscribe(callback, event_type=event_type, run=run)

    def wait_for_connection(self, timeout=1.0):
        super().wait_for_connection(timeout=timeout)

        with self._lock:
            if self._write_pv is not None and not self._write_pv.connected:
                if not self._write_pv.wait_for_connection(timeout=timeout):
                    raise TimeoutError('Failed to connect to %s' %
                                       self._write_pv.pvname)

    @property
    @raise_if_disconnected
    def tolerance(self):
        '''The tolerance of the write PV, as reported by EPICS

        Can be overidden by the user at the EpicsSignal level.

        Returns
        -------
        tolerance : float or None
        Using the write PV's precision:
            If precision == 0, tolerance will be None
            If precision > 0, calculated to be 10**(-precision)
        '''
        # NOTE: overrides Signal.tolerance property
        if self._tolerance is not None:
            return self._tolerance

        precision = self.precision
        if precision == 0 or precision is None:
            return None

        return 10. ** (-precision)

    @tolerance.setter
    def tolerance(self, tolerance):
        self._tolerance = tolerance

    @property
    @raise_if_disconnected
    def setpoint_ts(self):
        '''Timestamp of setpoint PV, according to EPICS'''
        with self._lock:
            if not self._write_pv.auto_monitor:
                # force updating the timestamp when not using auto monitoring
                self._write_pv.get_timevars()
            return self._write_pv.timestamp

    @property
    def setpoint_pvname(self):
        '''The setpoint PV name'''
        return self._write_pv.pvname

    @property
    @raise_if_disconnected
    def setpoint_alarm_status(self):
        """Setpoint PV status"""
        with self._lock:
            status = self._write_pv.status
            if status is None:
                return None
            return AlarmStatus(status)

    @property
    @raise_if_disconnected
    def setpoint_alarm_severity(self):
        """Setpoint PV alarm severity"""
        with self._lock:
            severity = self._write_pv.severity
            if severity is None:
                return None
            return AlarmSeverity(severity)

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
        with self._lock:
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
        with self._lock:
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

    def put(self, value, force=False, connection_timeout=1.0,
            use_complete=None, **kwargs):
        '''Using channel access, set the write PV to `value`.

        Keyword arguments are passed on to callbacks

        Parameters
        ----------
        value : any
            The value to set
        force : bool, optional
            Skip checking the value in Python first
        connection_timeout : float, optional
            If not already connected, allow up to `connection_timeout` seconds
            for the connection to complete.
        use_complete : bool, optional
            Override put completion settings
        '''
        if not force:
            self.check_value(value)

        with self._lock:
            if not self._write_pv.connected:
                if not self._write_pv.wait_for_connection(connection_timeout):
                    raise TimeoutError('Failed to connect to %s' %
                                       self._write_pv.pvname)

            if use_complete is None:
                use_complete = self._put_complete

            self._write_pv.put(value, use_complete=use_complete, **kwargs)

        old_value = self._setpoint
        self._setpoint = value

        if self._read_pv is self._write_pv:
            # readback and setpoint PV are one in the same, so update the
            # readback as well
            ts = time.time()
            super().put(value, timestamp=ts, force=True)
            self._run_subs(sub_type=self.SUB_SETPOINT,
                           old_value=old_value, value=value,
                           timestamp=ts, **kwargs)

    def set(self, value, *, timeout=None, settle_time=None):
        '''Set is like `EpicsSignal.put`, but is here for bluesky compatibility

        If put completion is used for this EpicsSignal, the status object will
        complete once EPICS reports the put has completed.

        Otherwise, set_and_wait will be used (as in `Signal.set`)

        Parameters
        ----------
        value : any
        timeout : float, optional
            Maximum time to wait. Note that set_and_wait does not support
            an infinite timeout.
        settle_time: float, optional
            Delay after the set() has completed to indicate completion
            to the caller

        Returns
        -------
        st : Status

        See Also
        --------
        Signal.set
        '''
        if not self._put_complete:
            return super().set(value, timeout=timeout, settle_time=settle_time)

        # using put completion:
        # timeout and settle time is handled by the status object.
        st = Status(self, timeout=timeout, settle_time=settle_time)

        def put_callback(**kwargs):
            st._finished(success=True)

        self.put(value, use_complete=True, callback=put_callback)
        return st

    @property
    def setpoint(self):
        '''The setpoint PV value'''
        return self.get_setpoint()

    @setpoint.setter
    def setpoint(self, value):
        self.put(value)


class AttributeSignal(Signal):
    '''Signal derived from a Python object instance's attribute

    Parameters
    ----------
    attr : str
        The dotted attribute name, relative to this signal's parent.
    name : str, optional
        The signal name
    parent : Device, optional
        The parent device instance
    '''
    def __init__(self, attr, *, name=None, parent=None, **kwargs):
        super().__init__(name=name, parent=parent, **kwargs)

        if '.' in attr:
            self.attr_base, self.attr = attr.rsplit('.', 1)
        else:
            self.attr_base, self.attr = None, attr

    @property
    def full_attr(self):
        '''The full attribute name'''
        if not self.attr_base:
            return self.attr
        else:
            return '.'.join((self.attr_base, self.attr))

    @property
    def base(self):
        '''The parent instance which has the final attribute'''
        if self.attr_base is None:
            return self.parent

        obj = self.parent
        for i, part in enumerate(self.attr_base.split('.')):
            try:
                obj = getattr(obj, part)
            except AttributeError as ex:
                raise AttributeError('{}.{} ({})'.format(obj.name, part, ex))

        return obj

    def get(self, **kwargs):
        return getattr(self.base, self.attr)

    def put(self, value, **kwargs):
        return setattr(self.base, self.attr, value)

    def describe(self):
        value = self.value
        desc = {'source': 'PY:{}.{}'.format(self.parent.name, self.full_attr),
                'dtype': data_type(value),
                'shape': data_shape(value),
                }
        return {self.name: desc}


class ArrayAttributeSignal(AttributeSignal):
    '''An AttributeSignal which is cast to an ndarray on get

    This is used where data_type and data_shape may otherwise fail to determine
    how to store the data into metadatastore.
    '''
    def get(self, **kwargs):
        return np.asarray(super().get(**kwargs))
