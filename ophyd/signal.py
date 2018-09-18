# vi: ts=4 sw=4
import logging
import time
import threading

import numpy as np

from .utils import ReadOnlyError, LimitError, set_and_wait
from .utils.epics_pvs import (waveform_to_string,
                              raise_if_disconnected, data_type, data_shape,
                              AlarmStatus, AlarmSeverity, validate_pv_name)
from .ophydobj import OphydObject, Kind
from .status import Status
from .utils.errors import DisconnectedError
from . import get_cl

logger = logging.getLogger(__name__)


class Signal(OphydObject):
    r'''A signal, which can have a read-write or read-only value.

    Parameters
    ----------
    name : string, keyword only
    value : any, optional
        The initial value
    kind : a member the Kind IntEnum (or equivalent integer), optional
        Default is Kind.normal. See Kind for options.
    parent : Device, optional
        The parent Device holding this signal
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
    attr_name : str, optional
        The parent Device attribute name that corresponds to this Signal

    Attributes
    ----------
    rtolerance : any, optional
        The relative tolerance associated with the value
    '''
    SUB_VALUE = 'value'
    SUB_META = 'meta'
    _default_sub = SUB_VALUE

    def __init__(self, *, name, value=0., timestamp=None, parent=None,
                 labels=None, kind=Kind.hinted, tolerance=None,
                 rtolerance=None, cl=None, attr_name=''):

        super().__init__(name=name, parent=parent, kind=kind, labels=labels,
                         attr_name=attr_name)
        if cl is None:
            cl = get_cl()
        self.cl = cl
        self._readback = value

        if timestamp is None:
            timestamp = time.time()

        self._destroyed = False
        self._timestamp = timestamp
        self._set_thread = None
        self._tolerance = tolerance
        # self.tolerance is a property
        self.rtolerance = rtolerance

        # Signal defaults to being connected, with full read/write access.
        # Subclasses are expected to clear these on init, if applicable.
        self._metadata = dict(
            connected=True,
            read_access=True,
            write_access=True
        )

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
        try:
            value = self.value
        except Exception:
            value = None

        if value is not None:
            yield ('value', value)

        try:
            if self.timestamp is not None:
                yield ('timestamp', self.timestamp)
            if self.tolerance is not None:
                yield ('tolerance', self.tolerance)
        except DisconnectedError:
            ...

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
            if not self.write_access:
                raise ReadOnlyError('Signal does not allow write access')

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
                self.log.exception('set_and_wait(%r, %s) failed',
                                   self.name, value)
                success = False
            else:
                self.log.debug('set_and_wait(%r, %s) succeeded => %s',
                               self.name, value, self.value)
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
        val = self.value
        return {self.name: {'source': 'SIM:{}'.format(self.name),
                            'dtype': data_type(val),
                            'shape': data_shape(val)}}

    def read_configuration(self):
        "Subclasses may customize this."
        return self.read()

    def describe_configuration(self):
        "Subclasses may customize this."
        return self.describe()

    @property
    def limits(self):
        # NOTE: subclasses are expected to override this property
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

    @property
    def connected(self):
        'Is the signal connected to its associated hardware?'
        return self._metadata.get('connected')

    @property
    def read_access(self):
        'Can the signal be read?'
        return self._metadata.get('read_access')

    @property
    def write_access(self):
        'Can the signal be written to?'
        return self._metadata.get('write_access')

    @property
    def metadata(self):
        'All metadata associated with the signal'
        return dict(self._metadata)

    def destroy(self):
        '''Disconnect the Signal from the underlying control layer

        Clears all subscriptions on this Signal.  Once disconnected, the signal
        may no longer be used.
        '''
        self._destroyed = True
        super().destroy()

    def __del__(self):
        try:
            self.destroy()
        except Exception:
            ...


class DerivedSignal(Signal):
    def __init__(self, derived_from, *, write_access=None, name=None,
                 parent=None, **kwargs):
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

        if write_access is None:
            write_access = derived_from.write_access

        self._metadata.update(
            connected=derived_from.connected,
            read_access=derived_from.read_access,
            write_access=write_access,
        )

        if self.connected:
            # set up the initial timestamp reporting, if connected
            self._timestamp = derived_from.timestamp

        derived_from.subscribe(self._derived_value_callback,
                               event_type=self.SUB_VALUE,
                               run=self.connected)
        derived_from.subscribe(self._derived_metadata_callback,
                               event_type=self.SUB_META,
                               run=self.connected)

    @property
    def derived_from(self):
        '''Signal that this one is derived from'''
        return self._derived_from

    def describe(self):
        '''Description based on the original signal description'''
        desc = self._derived_from.describe()[self._derived_from.name]
        desc['derived_from'] = self._derived_from.name
        return {self.name: desc}

    def _derived_metadata_callback(self, *, connected, read_access,
                                   write_access, timestamp, **kwargs):
        self._metadata.update(
            connected=connected,
            read_access=read_access,
            write_access=write_access,
        )
        self._run_subs(sub_type=self.SUB_META,
                       timestamp=self._metadata.get('timestamp'),
                       **self._metadata)

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
        if not self.write_access:
            raise ReadOnlyError('DerivedSignal is marked as read-only')
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
    auto_monitor : bool, optional
        Use automonitor with epics.PV
    name : str, optional
        Name of signal.  If not given defaults to read_pv
    string : bool, optional
        Attempt to cast the EPICS PV value to a string by default
    '''
    def __init__(self, read_pv, *,
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

        self._lock = threading.RLock()
        self._read_pv = None
        self._string = bool(string)
        self._auto_monitor = auto_monitor
        self._pvs_ready_event = threading.Event()

        if name is None:
            name = read_pv

        super().__init__(name=name, **kwargs)

        validate_pv_name(read_pv)
        cl = self.cl

        # Keep track of all associated PV's connectivity and access rights
        # callbacks:
        # Note: these are {pvname: bool}
        self._connection_states = {
            read_pv: False
        }

        self._access_rights_valid = {
            read_pv: False
        }

        self._metadata['connected'] = False
        self._read_pv = cl.get_pv(
            read_pv, form=cl.pv_form, auto_monitor=auto_monitor,
            connection_callback=self._pv_connected,
            access_callback=self._pv_access_callback
        )

        with self._lock:
            self._read_pv.add_callback(self._read_changed,
                                       run_now=self._read_pv.connected)

    def _pv_connected(self, pvname, conn, pv):
        'Control-layer callback: PV has [dis]connected'
        if self._destroyed:
            return

        if not conn:
            self._pvs_ready_event.clear()
            self._access_rights_valid[pv.pvname] = False

        old_connected = self.connected
        self._connection_states[pvname] = conn
        self._metadata['connected'] = all(self._connection_states.values())
        if old_connected != self.connected:
            self._run_subs(sub_type=self.SUB_META,
                           timestamp=self._metadata.get('timestamp'),
                           **self._metadata)

        self._set_event_if_ready()

    def _set_event_if_ready(self):
        '''If connected and access rights received, set the "ready" event used
        in wait_for_connection.'''
        if self.connected and all(self._access_rights_valid.values()):
            self._pvs_ready_event.set()

    def _pv_access_callback(self, read_access, write_access, pv):
        'Control-layer callback: PV access rights have changed'
        self._access_rights_valid[pv.pvname] = True
        self._set_event_if_ready()

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
            if status is not None:
                return AlarmStatus(status)

    @property
    @raise_if_disconnected
    def alarm_severity(self):
        """PV alarm severity"""
        with self._lock:
            severity = self._read_pv.severity
            if severity is not None:
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

            self._connection_states[old_instance.pvname] = False
            self._access_rights_valid[old_instance.pvname] = False
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
                self._read_pv = self._reinitialize_pv(
                    self._read_pv, auto_monitor=True,
                    connection_callback=self._pv_connected,
                    access_callback=self._pv_access_callback)
                self._read_pv.add_callback(self._read_changed,
                                           run_now=self._read_pv.connected)

        return super().subscribe(callback, event_type=event_type, run=run)

    def _ensure_connected(self, pv, *, timeout):
        'Ensure that `pv` is connected, with access/connection callbacks run'
        with self._lock:
            if self.connected:
                return

            if not pv.wait_for_connection(timeout=timeout):
                raise TimeoutError('Failed to connect to %s' % pv.pvname)

        # Ensure callbacks are run prior to returning, as
        # @raise_if_disconnected can cause issues otherwise.
        try:
            self._pvs_ready_event.wait(timeout)
        except TimeoutError:
            raise TimeoutError('Control layer {} failed to send connection and '
                               'access rights information within {:.1f} sec'
                               ''.format(self.cl.name, float(timeout))) from None

    def wait_for_connection(self, timeout=1.0):
        '''Wait for the underlying signals to initialize or connect'''
        self._ensure_connected(self._read_pv, timeout=timeout)

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
        yield ('auto_monitor', self._auto_monitor)
        yield ('string', self._string)

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
            self._ensure_connected(self._read_pv, timeout=connection_timeout)
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

    def destroy(self):
        '''Disconnect the EpicsSignal from the underlying PV instance'''
        super().destroy()
        if self._read_pv is not None:
            self.cl.release_pvs(self._read_pv)
            self._read_pv = None


class EpicsSignalRO(EpicsSignalBase):
    '''A read-only EpicsSignal -- that is, one with no `write_pv`

    Keyword arguments are passed on to the base class (Signal) initializer

    Parameters
    ----------
    read_pv : str
        The PV to read from
    limits : bool, optional
        Check limits prior to writing value
    auto_monitor : bool, optional
        Use automonitor with epics.PV
    name : str, optional
        Name of signal.  If not given defaults to read_pv
    '''

    def __init__(self, read_pv, *, string=False, auto_monitor=False, name=None,
                 **kwargs):
        super().__init__(read_pv, string=string, auto_monitor=auto_monitor,
                         name=name, **kwargs)
        self._metadata['write_access'] = False

    def put(self, *args, **kwargs):
        raise ReadOnlyError('Cannot write to read-only EpicsSignal')

    def set(self, *args, **kwargs):
        raise ReadOnlyError('Read-only signals cannot be set')

    def _pv_access_callback(self, read_access, write_access, pv):
        'Control-layer callback: read PV access rights have changed'
        # Tweak write access here - this is a read-only signal!
        if self._destroyed:
            return

        self._metadata.update(
            read_access=read_access,
            write_access=False,
        )
        if self.connected:
            self._run_subs(sub_type=self.SUB_META, timestamp=None,
                           **self._metadata)

        super()._pv_access_callback(read_access, write_access, pv)


class EpicsSignal(EpicsSignalBase):
    '''An EPICS signal, comprised of either one or two EPICS PVs

    Keyword arguments are passed on to the base class (Signal) initializer

    Parameters
    ----------
    read_pv : str
        The PV to read from
    write_pv : str, optional
        The PV to write to if different from the read PV
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

    def __init__(self, read_pv, write_pv=None, *, put_complete=False,
                 string=False, limits=False, auto_monitor=False, name=None,
                 **kwargs):

        self._write_pv = None
        self._use_limits = bool(limits)
        self._put_complete = put_complete

        self._setpoint = None
        self._setpoint_ts = None

        if write_pv == read_pv:
            write_pv = None

        super().__init__(read_pv, string=string, auto_monitor=auto_monitor,
                         name=name, **kwargs)

        if write_pv is not None:
            validate_pv_name(write_pv)
            cl = self.cl
            self._connection_states[write_pv] = False
            self._write_pv = cl.get_pv(
                write_pv, form=cl.pv_form,
                auto_monitor=self._auto_monitor,
                connection_callback=self._pv_connected,
                access_callback=self._pv_access_callback
            )
            self._write_pv.add_callback(self._write_changed,
                                        run_now=self._write_pv.connected)
        else:
            self._write_pv = self._read_pv

        # NOTE: after this point, write_pv can either be:
        #  (1) the same as read_pv
        #  (2) a completely separate PV instance
        # It will not be None, until destroy() is called.

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
                self._write_pv = self._reinitialize_pv(
                    self._write_pv, auto_monitor=True,
                    connection_callback=self._pv_connected,
                    access_callback=self._pv_access_callback
                )
                self._write_pv.add_callback(self._write_changed,
                                            run_now=self._write_pv.connected)

        return super().subscribe(callback, event_type=event_type, run=run)

    def wait_for_connection(self, timeout=1.0):
        '''Wait for the underlying signals to initialize or connect'''
        super().wait_for_connection(timeout=timeout)

        self._ensure_connected(self._write_pv, timeout=timeout)

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
        yield ('write_pv', self._write_pv.pvname)
        yield ('limits', self._use_limits)
        yield ('put_complete', self._put_complete)

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
            self._ensure_connected(self._write_pv, timeout=connection_timeout)
            if use_complete is None:
                use_complete = self._put_complete

            if not self.write_access:
                raise ReadOnlyError('No write access to underlying EPICS PV')

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

    def _pv_access_callback(self, read_access, write_access, pv):
        'Control-layer callback: PV access rights have changed '
        if self._destroyed:
            return

        if pv is self._read_pv:
            self._metadata['read_access'] = read_access
        elif pv is self._write_pv:
            self._metadata['write_access'] = write_access

        if self.connected:
            self._run_subs(sub_type=self.SUB_META,
                           timestamp=self._metadata.get('timestamp'),
                           **self._metadata)

        super()._pv_access_callback(read_access, write_access, pv)

    def destroy(self):
        '''Destroy the EpicsSignal from the underlying PV instance'''
        super().destroy()
        if self._write_pv is not None:
            self.cl.release_pvs(self._write_pv)
            self._write_pv = None


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
    read_access : bool, optional
        Allow read access to the attribute
    write_access : bool, optional
        Allow write access to the attribute
    '''
    def __init__(self, attr, *, name=None, parent=None, write_access=True,
                 **kwargs):
        super().__init__(name=name, parent=parent, **kwargs)

        if '.' in attr:
            self.attr_base, self.attr = attr.rsplit('.', 1)
        else:
            self.attr_base, self.attr = None, attr

        self._metadata.update(
            read_access=True,
            write_access=write_access,
        )

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
        if not self.write_access:
            raise ReadOnlyError('AttributeSignal is marked as read-only')

        old_value = self.get()
        setattr(self.base, self.attr, value)
        self._run_subs(sub_type=self.SUB_VALUE, old_value=old_value,
                       value=value, timestamp=time.time())

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
