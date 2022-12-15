# vi: ts=4 sw=4
import os
import threading
import time
import warnings
import weakref

import numpy as np

from . import get_cl
from .ophydobj import Kind, OphydObject
from .status import Status
from .utils import DestroyedError, LimitError, ReadOnlyError, doc_annotation_forwarder
from .utils.epics_pvs import (
    AlarmSeverity,
    AlarmStatus,
    _set_and_wait,
    data_shape,
    data_type,
    raise_if_disconnected,
    validate_pv_name,
    waveform_to_string,
)

# Catch semi-frequent issue with scripts accidentally run from inside module
if __name__ != "ophyd.signal":
    raise RuntimeError(
        "A script tried to import ophyd.signal instead of the signal built-in "
        "module. This usually happens when a script is run from inside the "
        "ophyd directory and can cause extremely confusing bugs. Please "
        "run your script elsewhere for better results."
    )


# Sentinels used for default values; see set_defaults() below for details.
DEFAULT_AUTO_MONITOR = object()
DEFAULT_CONNECTION_TIMEOUT = object()
DEFAULT_TIMEOUT = object()
DEFAULT_WRITE_TIMEOUT = object()

# Sentinel to identify if we have never turned the crank on updating a PV
DEFAULT_EPICSSIGNAL_VALUE = object()


class ReadTimeoutError(TimeoutError):
    ...


class ConnectionTimeoutError(TimeoutError):
    ...


class Signal(OphydObject):
    r"""A signal, which can have a read-write or read-only value.

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
        set as follows

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
    """
    SUB_VALUE = "value"
    SUB_META = "meta"
    _default_sub = SUB_VALUE
    _metadata_keys = None
    _core_metadata_keys = ("connected", "read_access", "write_access", "timestamp")

    def __init__(
        self,
        *,
        name,
        value=0.0,
        timestamp=None,
        parent=None,
        labels=None,
        kind=Kind.hinted,
        tolerance=None,
        rtolerance=None,
        metadata=None,
        cl=None,
        attr_name="",
    ):

        super().__init__(
            name=name, parent=parent, kind=kind, labels=labels, attr_name=attr_name
        )

        if cl is None:
            cl = get_cl()
        self.cl = cl
        self._dispatcher = cl.get_dispatcher()
        self._metadata_thread_ctx = self._dispatcher.get_thread_context("monitor")
        self._readback = value

        if timestamp is None:
            timestamp = time.time()

        self._destroyed = False

        self._set_thread = None
        self._tolerance = tolerance
        # self.tolerance is a property
        self.rtolerance = rtolerance

        # Signal defaults to being connected, with full read/write access.
        # Subclasses are expected to clear these on init, if applicable.
        self._metadata = dict(
            connected=True,
            read_access=True,
            write_access=True,
            timestamp=timestamp,
            status=None,
            severity=None,
            precision=None,
        )

        if metadata is not None:
            self._metadata.update(**metadata)

        if self._metadata_keys is None:
            self._metadata_keys = tuple(self._metadata.keys())
        else:
            unset_metadata = {
                key: None for key in self._metadata_keys if key not in self._metadata
            }

            self._metadata.update(**unset_metadata)

    def trigger(self):
        """Call that is used by bluesky prior to read()"""
        # NOTE: this is a no-op that exists here for bluesky purposes
        #       it may need to be moved in the future
        d = Status(self)
        d._finished()
        return d

    def wait_for_connection(self, timeout=0.0):
        """Wait for the underlying signals to initialize or connect"""
        pass

    @property
    def metadata_keys(self):
        "Metadata keys that will be passed along on value subscriptions"
        return tuple(self._metadata_keys)

    @property
    def timestamp(self):
        """Timestamp of the readback value"""
        return self._metadata["timestamp"]

    @property
    def tolerance(self):
        """The absolute tolerance associated with the value."""
        return self._tolerance

    @tolerance.setter
    def tolerance(self, tolerance):
        self._tolerance = tolerance

    def _repr_info(self):
        "Yields pairs of (key, value) to generate the Signal repr"
        yield from super()._repr_info()
        try:
            value = self._readback
        except Exception:
            value = None

        if value is not DEFAULT_EPICSSIGNAL_VALUE:
            yield ("value", value)

        yield ("timestamp", self._metadata["timestamp"])

        if self.tolerance is not None:
            yield ("tolerance", self.tolerance)

        if self.rtolerance is not None:
            yield ("rtolerance", self.rtolerance)

        # yield ('metadata', self._metadata)

    def get(self, **kwargs):
        """The readback value"""
        return self._readback

    def put(
        self,
        value,
        *,
        timestamp=None,
        force=False,
        metadata=None,
        timeout=DEFAULT_WRITE_TIMEOUT,
        **kwargs,
    ):
        """
        Low-level method for writing to a Signal.

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
        metadata : dict, optional
            Further associated metadata with the value (such as alarm status,
            severity, etc.)
        force : bool, optional
            Check the value prior to setting it, defaults to False

        """
        self.control_layer_log.debug(
            "put(value=%s, timestamp=%s, force=%s, metadata=%s)",
            value,
            timestamp,
            force,
            metadata,
        )

        if kwargs:
            warnings.warn(
                "Signal.put no longer takes keyword arguments; "
                "These are ignored and will be deprecated. "
                f"Received kwargs={kwargs}"
            )

        if not force:
            if not self.write_access:
                raise ReadOnlyError("Signal does not allow write access")

            self.check_value(value)

        old_value = self._readback
        self._readback = value

        if metadata is None:
            metadata = {}

        if timestamp is None:
            timestamp = metadata.get("timestamp", time.time())

        metadata = metadata.copy()
        metadata["timestamp"] = timestamp
        self._metadata.update(**metadata)

        md_for_callback = {
            key: metadata[key] for key in self._metadata_keys if key in metadata
        }

        if "timestamp" not in self._metadata_keys:
            md_for_callback["timestamp"] = timestamp

        self._run_subs(
            sub_type=self.SUB_VALUE, old_value=old_value, value=value, **md_for_callback
        )

    def _set_and_wait(self, value, timeout, **kwargs):
        """
        Overridable hook for subclasses to override :meth:`.set` functionality.

        This will be called in a separate thread (`_set_thread`), but will not
        be called in parallel.

        Parameters
        ----------
        value : any
            The value
        timeout : float, optional
            Maximum time to wait for value to be successfully set, or None
        """
        return _set_and_wait(
            self,
            value,
            timeout=timeout,
            atol=self.tolerance,
            rtol=self.rtolerance,
            **kwargs,
        )

    def set(self, value, *, timeout=None, settle_time=None, **kwargs):
        """
        Set the value of the Signal and return a Status object.

        Returns
        -------
        st : Status
            This status object will be finished upon return in the
            case of basic soft Signals
        """
        self.log.debug(
            "set(value=%s, timeout=%s, settle_time=%s, kwargs=%s)",
            value,
            timeout,
            settle_time,
            kwargs,
        )

        def set_thread():
            try:
                self._set_and_wait(value, timeout, **kwargs)
            except TimeoutError:
                success = False
                self.log.warning(
                    "%s: _set_and_wait(value=%s, timeout=%s, atol=%s, rtol=%s, kwargs=%s)",
                    self.name,
                    value,
                    timeout,
                    self.tolerance,
                    self.rtolerance,
                    kwargs,
                )
            except Exception:
                success = False
                self.log.exception(
                    "%s: _set_and_wait(value=%s, timeout=%s, atol=%s, rtol=%s, kwargs=%s)",
                    self.name,
                    value,
                    timeout,
                    self.tolerance,
                    self.rtolerance,
                    kwargs,
                )
            else:
                success = True
                self.log.debug(
                    "%s: _set_and_wait(value=%s, timeout=%s, atol=%s, rtol=%s, kwargs=%s) succeeded => %s",
                    self.name,
                    value,
                    timeout,
                    self.tolerance,
                    self.rtolerance,
                    kwargs,
                    self._readback,
                )

                if settle_time is not None:
                    self.log.debug("settling for %d seconds", settle_time)
                    time.sleep(settle_time)
            finally:
                # keep a local reference to avoid any GC shenanigans
                th = self._set_thread
                # these two must be in this order to avoid a race condition
                self._set_thread = None
                st._finished(success=success)
                del th

        if self._set_thread is not None:
            raise RuntimeError(
                "Another set() call is still in progress " f"for {self.name}"
            )

        st = Status(self)
        self._status = st
        self._set_thread = self.cl.thread_class(target=set_thread)
        self._set_thread.daemon = True
        self._set_thread.start()
        return self._status

    @property
    def value(self):
        """The signal's value"""
        fix_msg = (
            "We are falling back to calling `.get` and interrogating "
            "the underlying control system, however this may cause several "
            "other problems:\n"
            "   1. This property access may take an arbitrarily long time\n"
            "   2. This property access, which you expect to be read only "
            "may change other state in the Signal.\n"
            "Your options to fix this are:\n"
            "  - do not use obj.value.\n"
            "    - If you are using this is in a plan you "
            "like want to be using bps.read, bps.rd, bpp.reset_positions_decorator, "
            "bpp.reset_positions_wrapper, bpp.relative_set_decorator, or "
            "bpp.relative_set_wrapper\n"
            "    - if you are doing this in an ophyd method use `self.get`\n"
            "  - set up the Signal to monitor\n\n"
            "This behavior will likely change in the future."
        )

        if self._readback is DEFAULT_EPICSSIGNAL_VALUE:
            # If we are here, then we have never turned the crank on this Signal.  The current
            # behavior is to fallback to poking the control system to get the value, however this
            # is problematic and we may want to change in the future so warn verbosely
            if not os.getenv("OPHYD_SILENCE_VALUE_WARNING") == "1":
                warnings.warn(
                    f"You have called obj.value on {self} "
                    f"({self.name}.{self.dotted_name}) "
                    "which has not gotten value from the control system yet.\n"
                    + fix_msg,
                    stacklevel=2,
                )
            return self.get()
        else:
            # if we are in here then we have put/get at least once and/or are monitored
            has_monitors = hasattr(self, "_monitors") and all(
                v is not None for v in self._monitors.values()
            )
            if not has_monitors:
                # If we are not monitored, then warn that this may change in the future.
                if not os.getenv("OPHYD_SILENCE_VALUE_WARNING") == "1":
                    warnings.warn(
                        f"You have called obj.value on {self} "
                        f"({self.name}.{self.dotted_name}) "
                        "which is a non-monitored signal.\n" + fix_msg,
                        stacklevel=2,
                    )
                return self.get()

            # else return our cached value and assume something else is keeping us up-to-date
            # so we can trust the latest news
            return self._readback

    @value.setter
    def value(self, value):
        self.put(value)

    @raise_if_disconnected
    def read(self):
        """Put the status of the signal into a simple dictionary format
        for data acquisition

        Returns
        -------
            dict
        """
        value = self.get()
        return {self.name: {"value": value, "timestamp": self.timestamp}}

    def describe(self):
        """Provide schema and meta-data for :meth:`~BlueskyInterface.read`

        This keys in the `OrderedDict` this method returns must match the
        keys in the `OrderedDict` return by :meth:`~BlueskyInterface.read`.

        This provides schema related information, (ex shape, dtype), the
        source (ex PV name), and if available, units, limits, precision etc.

        Returns
        -------
        data_keys : OrderedDict
            The keys must be strings and the values must be dict-like
            with the ``event_model.event_descriptor.data_key`` schema.
        """
        if self._readback is DEFAULT_EPICSSIGNAL_VALUE:
            val = self.get()
        else:
            val = self._readback
        try:
            return {
                self.name: {
                    "source": "SIM:{}".format(self.name),
                    "dtype": data_type(val),
                    "shape": data_shape(val),
                }
            }
        except ValueError as ve:
            # data_type(val) raises ValueError if type(val) is not bluesky-friendly
            # help the humans by reporting self.name in the exception chain
            raise ValueError(
                f"failed to describe '{self.name}' with value '{val}'"
            ) from ve

    def read_configuration(self):
        "Dictionary mapping names to value dicts with keys: value, timestamp"
        return self.read()

    def describe_configuration(self):
        """Provide schema & meta-data for :meth:`BlueskyInterface.read_configuration`

        This keys in the `OrderedDict` this method returns must match the keys
        in the `OrderedDict` return by :meth:`~BlueskyInterface.read`.

        This provides schema related information, (ex shape, dtype), the source
        (ex PV name), and if available, units, limits, precision etc.

        Returns
        -------
        data_keys : OrderedDict
            The keys must be strings and the values must be dict-like
            with the ``event_model.event_descriptor.data_key`` schema.
        """
        return self.describe()

    @property
    def limits(self):
        """The control limits (low, high), such that low <= value <= high"""
        # NOTE: subclasses are expected to override this property
        # Always override, never extend this
        return (0, 0)

    @property
    def low_limit(self):
        "The low, inclusive control limit for the Signal"
        return self.limits[0]

    @property
    def high_limit(self):
        "The high, inclusive control limit for the Signal"
        return self.limits[1]

    @property
    def hints(self):
        "Field hints for plotting"
        if (~Kind.normal & Kind.hinted) & self.kind:
            return {"fields": [self.name]}
        else:
            return {"fields": []}

    @property
    def connected(self):
        "Is the signal connected to its associated hardware, and ready to use?"
        return self._metadata["connected"] and not self._destroyed

    @property
    def read_access(self):
        "Can the signal be read?"
        return self._metadata["read_access"]

    @property
    def write_access(self):
        "Can the signal be written to?"
        return self._metadata["write_access"]

    @property
    def metadata(self):
        "A copy of the metadata dictionary associated with the signal"
        return self._metadata.copy()

    def destroy(self):
        """Disconnect the Signal from the underlying control layer; destroy it

        Clears all subscriptions on this Signal.  Once destroyed, the signal
        may no longer be used.
        """
        self._destroyed = True
        super().destroy()

    def _run_metadata_callbacks(self):
        "Run SUB_META in the appropriate dispatcher thread"
        self._metadata_thread_ctx.run(
            self._run_subs, sub_type=self.SUB_META, **self._metadata
        )


class SignalRO(Signal):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._metadata.update(
            connected=True,
            write_access=False,
        )

    def put(self, value, *, timestamp=None, force=False):
        raise ReadOnlyError("The signal {} is readonly.".format(self.name))

    def set(self, value, *, timestamp=None, force=False):
        raise ReadOnlyError("The signal {} is readonly.".format(self.name))


class DerivedSignal(Signal):
    def __init__(
        self, derived_from, *, write_access=None, name=None, parent=None, **kwargs
    ):
        """A signal which is derived from another one

        Calculations of the DerivedSignal value can be done in subclasses of
        DerivedSignal, overriding the `forward` and `inverse` methods.

        Metadata keys and write access are inherited from the main signal,
        referred to as `derived_from`.

        The description of this Signal, from `describe` will include an
        additional key indicating the signal name from where it was derived.

        Parameters
        ----------
        derived_from : Union[Signal, str]
            The signal from which this one is derived.  This may be a string
            attribute name that indicates a sibling to use.  When used in a
            Device, this is then simply the attribute name of another
            Component.
        name : str, optional
            The signal name
        parent : Device, optional
            The parent device
        """
        if isinstance(derived_from, str):
            derived_from = getattr(parent, derived_from)

        # Metadata keys from the class itself take precedence
        self._metadata_keys = getattr(self, "_metadata_keys", None)

        # However, if not specified, the keys from the original signal are used
        if self._metadata_keys is None:
            self._metadata_keys = getattr(derived_from, "metadata_keys", None)
            # And failing that, they are the defaults from all signals

        super().__init__(
            name=name, parent=parent, metadata=derived_from.metadata, **kwargs
        )

        self._derived_from = derived_from

        self._allow_writes = write_access is not False
        self._metadata["write_access"] = (
            derived_from.write_access and self._allow_writes
        )

        if self.connected:
            # set up the initial timestamp reporting, if connected
            self._metadata["timestamp"] = derived_from.timestamp

        derived_from.subscribe(
            self._derived_value_callback, event_type=self.SUB_VALUE, run=self.connected
        )
        derived_from.subscribe(
            self._derived_metadata_callback,
            event_type=self.SUB_META,
            run=self.connected,
        )

    @property
    def derived_from(self):
        """Signal that this one is derived from"""
        return self._derived_from

    def describe(self):
        """Description based on the original signal description"""
        desc = super().describe()[self.name]  # Description of this signal
        desc["derived_from"] = self._derived_from.name
        # Description of the derived signal
        derived_desc = self._derived_from.describe()[self._derived_from.name]
        derived_desc.update(desc)
        return {self.name: derived_desc}

    def _update_metadata_from_callback(self, **kwargs):
        updated_md = {key: kwargs[key] for key in self.metadata_keys if key in kwargs}

        if "write_access" in updated_md:
            updated_md["write_access"] = (
                updated_md["write_access"] and self._allow_writes
            )
        self._metadata.update(**updated_md)
        return updated_md

    def _derived_metadata_callback(
        self, *, connected, read_access, write_access, timestamp, **kwargs
    ):
        "Main signal metadata updated - update the DerivedSignal"
        self._update_metadata_from_callback(
            connected=connected,
            read_access=read_access,
            write_access=write_access,
            timestamp=timestamp,
            **kwargs,
        )

        self._run_metadata_callbacks()

    def _derived_value_callback(self, value, **kwargs):
        "Main signal value updated - update the DerivedSignal"
        # if some how we get cycled with the default value sentinel, just bail
        if value is DEFAULT_EPICSSIGNAL_VALUE:
            return
        value = self.inverse(value)
        self._readback = value
        updated_md = self._update_metadata_from_callback(**kwargs)
        self._run_subs(sub_type=self.SUB_VALUE, value=value, **updated_md)

    def get(self, **kwargs):
        "Get the value from the original signal, with `inverse` applied to it"
        value = self._derived_from.get(**kwargs)
        self._readback = self.inverse(value)
        self._metadata["timestamp"] = self._derived_from.timestamp
        return self._readback

    def inverse(self, value):
        """Compute original signal value -> derived signal value"""
        return value

    def put(self, value, **kwargs):
        """Put the value to the original signal"""
        if not self.write_access:
            raise ReadOnlyError("DerivedSignal is marked as read-only")
        value = self.forward(value)
        res = self._derived_from.put(value, **kwargs)
        self._metadata["timestamp"] = self._derived_from.timestamp
        return res

    def forward(self, value):
        """Compute derived signal value -> original signal value"""
        return value

    def wait_for_connection(self, timeout=0.0):
        """Wait for the original signal to connect"""
        return self._derived_from.wait_for_connection(timeout=timeout)

    @property
    def connected(self):
        """Mirrors the connection state of the original signal"""
        return self._derived_from.connected

    @property
    def limits(self):
        """Limits from the original signal (low, high), such that low <= value <= high"""
        return tuple(sorted(self.inverse(v) for v in self._derived_from.limits))

    def _repr_info(self):
        "Yields pairs of (key, value) to generate the Signal repr"
        yield from super()._repr_info()
        if self.parent is not None:
            yield ("derived_from", self._derived_from.dotted_name)
        else:
            yield ("derived_from", self._derived_from)


class InternalSignalMixin:
    """
    Mix-in class for adding the `InternalSignal` behavior to any signal class.

    A signal class with this mixin will reject all sets and puts unless
    internal=True is passed as an argument.

    The intended use for this is to signify that a signal is for internal use
    by the class only. That is, it would be a mistake to try to cause puts to
    this signal by code external to the Device class.

    Some more concrete use-cases would be things like soft "status" type
    signals that should be read-only except that the class needs to edit it,
    or EPICS signals that should be written to by the class but are likely to
    cause issues for external writes due to behavior complexity.
    """

    def put(self, *args, internal: bool = False, **kwargs):
        """
        Write protection for an internal signal.

        This method is not intended to be used from outside of the device
        that defined this signal. All writes must be done with internal=True.
        """
        if not internal:
            raise InternalSignalError()
        return super().put(*args, **kwargs)

    def set(self, *args, internal: bool = False, **kwargs):
        """
        Write protection for an internal signal.

        This method is not intended to be used from outside of the device
        that defined this signal. All writes must be done with internal=True.
        """
        if not internal:
            raise InternalSignalError()
        return super().set(*args, internal=internal, **kwargs)


class InternalSignal(InternalSignalMixin, Signal):
    """
    A soft Signal that stores data but should only be updated by the Device.

    Unlike SignalRO, which will unilaterally block all writes, this will
    allow writes with internal=True.

    The intended use for this is to signify that a signal is for internal use
    by the class only. That is, it would be a mistake to try to cause puts to
    this signal by code external to the Device class.

    Some more concrete use-cases would be things like soft "status" type
    signals that should be read-only except that the class needs to edit it,
    or calculated "done" signals for positioner classes.
    """


class InternalSignalError(ReadOnlyError):
    """
    A read-only error sourced from trying to write to an internal signal.
    """

    def __init__(self, message=None):
        if message is None:
            message = (
                "This signal is for internal use only. "
                "You should not be writing to it from outside "
                "the parent class. If you do need to write to "
                "this signal, you can use signal.put(value, internal=True)."
            )
        super().__init__(message)


class EpicsSignalBase(Signal):
    """A read-only EpicsSignal -- that is, one with no `write_pv`

    Keyword arguments are passed on to the base class (Signal) initializer

    Parameters
    ----------
    read_pv : str
        The PV to read from
    string : bool, optional
        Attempt to cast the EPICS PV value to a string by default
    auto_monitor : bool, optional
        Use automonitor with epics.PV
    name : str, optional
        Name of signal.  If not given defaults to read_pv
    metadata : dict
        Merged with metadata received from EPICS
    all_pvs : set
        Set of PVs to watch for connection and access rights callbacks.
        Defaults to ``{read_pvs}``.
    timeout : float or None, optional
        The timeout for serving a read request on a connected channel. This is
        only applied if the PV is connected within connection_timeout (below).

        The default value DEFAULT_TIMEOUT means, "Fall back to class-wide
        default." See EpicsSignalBase.set_defaults to configure class
        defaults.

        Explicitly passing None means, "Wait forever."
    write_timeout : float or None, optional
        The timeout for a reply when put completion is used. This is
        only applied if the PV is connected within connection_timeout (below).

        This is very different than the connection and read timeouts
        above. It relates to how long an action takes to complete, such motor
        motion or data acquisition. Any default value we choose here is likely
        to cause problems---either by being too short and giving up too early
        on a lengthy action or being too long and delaying the report of a
        failure. A finite value can be injected here or, perhaps more usefully,
        via `set` at the Device level, where a context-appropriate value can be
        chosen.
    connection_timeout : float or None, optional
        Timeout for connection. This includes the time to search and establish
        a channel.

        The default value DEFAULT_CONNECTION_TIMEOUT means, "Fall back to
        class-wide default." See EpicsSignalBase.set_defaults to
        configure class defaults.

        Explicitly passing None means, "Wait forever."
    """

    # This is set to True when the first instance is made. It is used to ensure
    # that certain class-global settings can only be made before any
    # instantiation.
    __any_instantiated = False

    # See set_defaults() for more on these.
    __default_connection_timeout = 1.0
    __default_timeout = 2.0  # *read* timeout
    __default_write_timeout = None  # Wait forever.
    __default_auto_monitor = False

    _read_pv_metadata_key_map = dict(
        status=("status", AlarmStatus),
        severity=("severity", AlarmSeverity),
        precision=("precision", None),
        lower_ctrl_limit=("lower_ctrl_limit", None),
        upper_ctrl_limit=("upper_ctrl_limit", None),
        timestamp=("timestamp", None),
        units=("units", None),
        enum_strs=("enum_strs", tuple),
        # ignored: read_access, write_access, connected, etc.
    )

    _metadata_keys = Signal._core_metadata_keys + (
        "status",
        "severity",
        "precision",
        "lower_ctrl_limit",
        "upper_ctrl_limit",
        "units",
        "enum_strs",
    )

    def __init__(
        self,
        read_pv,
        *,
        string=False,
        auto_monitor=DEFAULT_AUTO_MONITOR,
        name=None,
        metadata=None,
        all_pvs=None,
        timeout=DEFAULT_TIMEOUT,
        write_timeout=DEFAULT_WRITE_TIMEOUT,
        connection_timeout=DEFAULT_CONNECTION_TIMEOUT,
        **kwargs,
    ):
        self._metadata_lock = threading.RLock()
        self._read_pv = None
        self._read_pvname = read_pv
        self._string = bool(string)

        self._signal_is_ready = threading.Event()
        self._first_connection = True

        if auto_monitor is DEFAULT_AUTO_MONITOR:
            auto_monitor = self.__default_auto_monitor
        self._auto_monitor = auto_monitor
        if connection_timeout is DEFAULT_CONNECTION_TIMEOUT:
            connection_timeout = self.__default_connection_timeout
        self._connection_timeout = connection_timeout
        if timeout is DEFAULT_TIMEOUT:
            timeout = self.__default_timeout
        self._timeout = timeout
        if write_timeout is DEFAULT_WRITE_TIMEOUT:
            write_timeout = self.__default_write_timeout
        self._write_timeout = write_timeout

        if name is None:
            name = read_pv

        if metadata is None:
            metadata = {}

        metadata.update(
            connected=False,
        )

        kwargs.setdefault("value", DEFAULT_EPICSSIGNAL_VALUE)
        super().__init__(name=name, metadata=metadata, **kwargs)

        validate_pv_name(read_pv)

        # Keep track of all associated PV's connectivity and access rights
        # callbacks. These map `pvname` to bool:
        if all_pvs is None:
            all_pvs = {read_pv}
        self._connection_states = {pv: False for pv in all_pvs}
        self._access_rights_valid = {pv: False for pv in all_pvs}
        self._received_first_metadata = {pv: False for pv in all_pvs}
        self._monitors = {pv: None for pv in all_pvs}

        self._metadata_key_map = {read_pv: self._read_pv_metadata_key_map}

        for pv in all_pvs:
            if pv not in self._metadata_key_map:
                self._metadata_key_map[pv] = {}

        self._read_pv = self.cl.get_pv(
            read_pv,
            auto_monitor=self._auto_monitor,
            connection_callback=self._pv_connected,
            access_callback=self._pv_access_callback,
        )
        self._read_pv._reference_count += 1

        if not self.__any_instantiated:
            self.log.debug(
                "This is the first instance of EpicsSignalBase. "
                "name={self.name}, id={id(self)}"
            )
            EpicsSignalBase._mark_as_instantiated()

        def finalize(read_pv, cl):
            cl.release_pvs(read_pv)

        self._read_pv_finalizer = weakref.finalize(
            self, finalize, self._read_pv, self.cl
        )

    def destroy(self):
        super().destroy()
        self._read_pv_finalizer()

    @classmethod
    def _mark_as_instantiated(cls):
        "Update state indicated that this class has been instantiated."
        cls.__any_instantiated = True

    @classmethod
    def set_defaults(
        cls,
        *,
        timeout=__default_timeout,
        connection_timeout=__default_connection_timeout,
        write_timeout=__default_write_timeout,
        auto_monitor=__default_auto_monitor,
    ):
        """
        Set class-wide defaults for EPICS CA communications

        This may be called only before any instances of EpicsSignalBase are
        made.

        This setting applies to the class it is called on and all its
        subclasses. For example,

        >>> EpicsSignalBase.set_defaults(...)

        will apply to ``EpicsSignalRO`` and ``EpicsSignal``, which are both
        subclasses of ``EpicsSignalBase``.

        but

        >>> EpicsSignal.set_defaults(...)

        will not apply to ``EpicsSignalRO``.

        Parameters
        ----------
        auto_monitor: bool, optional
            If ``True``, update cached value from EPICS CA monitor callbacks.
            If ``False``, request new value from EPICS each time get() is called.
        connection_timeout: float, optional
            Time (seconds) allocated for establishing a connection with the
            IOC.
        timeout: float, optional
            Total time budget (seconds) for reading, not including connection time.
        write_timeout: float, optional
            Time (seconds) allocated for writing, not including connection time.
            The write_timeout is very different than the connection and read timeouts
            above. It relates to how long an action takes to complete. Any
            default value we choose here is likely to cause problems---either
            by being too short and giving up too early on a lengthy action or
            being too long and delaying the report of a failure. The default,
            None, waits forever.

        Raises
        ------
        RuntimeError
            If called after :class:`EpicsSignalBase` has been instantiated for
            the first time.
        """
        if EpicsSignalBase.__any_instantiated:
            raise RuntimeError(
                "The method EpicsSignalBase.set_defaults may only "
                "be called before the first instance of EpicsSignalBase is "
                "created. This is to ensure that all instances are created "
                "with the same default settings in place."
            )

        cls.__default_auto_monitor = auto_monitor
        cls.__default_connection_timeout = connection_timeout
        cls.__default_timeout = timeout
        # The write_timeout is very different than the connection and read timeouts
        # above. It relates to how long an action takes to complete. Any
        # default value we choose here is likely to cause problems---either
        # by being too short and giving up too early on a lengthy action or
        # being too long and delaying the report of a failure.
        cls.__default_write_timeout = write_timeout

        # TODO Is there a good reason to prohibit setting these three timeout
        # properties?

    @classmethod
    def set_default_timeout(cls, **kwargs):
        warnings.warn(
            "set_default_timeout() will be removed "
            "in a future release. Use set_defaults() instead."
        )
        cls.set_defaults(**kwargs)

    @property
    def connection_timeout(self):
        return self._connection_timeout

    @property
    def timeout(self):
        return self._timeout

    @property
    def write_timeout(self):
        return self._write_timeout

    def __getnewargs_ex__(self):
        args, kwargs = super().__getnewargs_ex__()
        # 'value' shows up in the EpicsSignal repr, but should not be used to
        # copy the Signal
        kwargs.pop("value", None)
        return (args, kwargs)

    def _initial_metadata_callback(self, pvname, cl_metadata):
        "Control-layer callback: all initial metadata - control and status"
        self._metadata_changed(
            pvname, cl_metadata, require_timestamp=True, update=True, from_monitor=False
        )
        self._received_first_metadata[pvname] = True
        self._set_event_if_ready()

    def _metadata_changed(
        self, pvname, cl_metadata, *, from_monitor, update, require_timestamp=False
    ):
        "Notification: the metadata of a single PV has changed"
        metadata = self._get_metadata_from_kwargs(
            pvname, cl_metadata, require_timestamp=require_timestamp
        )
        if update:
            self._metadata.update(**metadata)
        return metadata

    def _pv_connected(self, pvname, conn, pv):
        "Control-layer callback: PV has [dis]connected"
        if self._destroyed:
            return

        was_connected = self.connected
        if not conn:
            self._signal_is_ready.clear()
            self._metadata["connected"] = False
            self._access_rights_valid[pvname] = False

        self._connection_states[pvname] = conn

        if conn and not self._received_first_metadata[pvname]:
            pv.get_all_metadata_callback(self._initial_metadata_callback, timeout=10)

        self._set_event_if_ready()

        if was_connected and not conn:
            # Send a notification of disconnection
            self._run_metadata_callbacks()

        if self._auto_monitor:
            if getattr(self, "_read_pvname", None) == pvname:
                self._add_callback(pvname, pv, self._read_changed)
            if getattr(self, "_setpoint_pvname", None) == pvname:
                self._add_callback(pvname, pv, self._write_changed)

    def _set_event_if_ready(self):
        """If connected and access rights received, set the "ready" event used
        in wait_for_connection."""
        with self._metadata_lock:
            already_connected = self._metadata["connected"]
            if self._destroyed or already_connected:
                return
            elif not all(
                [
                    *self._connection_states.values(),
                    *self._access_rights_valid.values(),
                    *self._received_first_metadata.values(),
                ]
            ):
                if self._metadata["connected"]:
                    self._metadata["connected"] = False
                    # subs are run in _pv_connected
                return

            self._metadata["connected"] = True
            self._signal_is_ready.set()

        self._run_metadata_callbacks()

    def _pv_access_callback(self, read_access, write_access, pv):
        "Control-layer callback: PV access rights have changed"
        self._access_rights_valid[pv.pvname] = True

    @property
    def as_string(self):
        """Attempt to cast the EPICS PV value to a string by default"""
        return self._string

    @property
    def precision(self):
        """The precision of the read PV, as reported by EPICS"""
        return self._metadata["precision"]

    @property
    def enum_strs(self):
        """List of strings if PV is an enum type"""
        return self._metadata["enum_strs"]

    @property
    def alarm_status(self):
        """PV status"""
        return self._metadata["status"]

    @property
    def alarm_severity(self):
        """PV alarm severity"""
        return self._metadata["severity"]

    def _add_callback(self, pvname, pv, cb):
        with self._metadata_lock:
            if not self._monitors[pvname]:
                mon = pv.add_callback(cb, run_now=pv.connected)
                self._monitors[pvname] = mon

    @doc_annotation_forwarder(Signal)
    def subscribe(self, callback, event_type=None, run=True):
        if event_type is None:
            event_type = self._default_sub
        if event_type == self.SUB_VALUE:
            self._add_callback(self._read_pvname, self._read_pv, self._read_changed)

        return super().subscribe(callback, event_type=event_type, run=run)

    def _ensure_connected(self, *pvs, timeout):
        "Ensure that `pv` is connected, with access/connection callbacks run"
        with self._metadata_lock:
            if self.connected:
                return
            elif self._destroyed:
                raise DestroyedError("Cannot re-use a destroyed Signal")

        for pv in pvs:
            if not pv.wait_for_connection(timeout=timeout):
                raise TimeoutError(
                    f"{pv.pvname} could not connect within "
                    f"{float(timeout):.3}-second timeout."
                )

        for pv in pvs:
            if not self._received_first_metadata[pv.pvname]:
                # Utility threads can get backed up in cases of PV connection
                # storms.  Since the user is specifically blocking on this PV,
                # make it a priority and perform the request in the current
                # thread.
                md = pv.get_all_metadata_blocking(timeout=timeout)
                self._initial_metadata_callback(pv.pvname, md)

        # Ensure callbacks are run prior to returning, as
        # @raise_if_disconnected can cause issues otherwise.
        if not self._signal_is_ready.wait(timeout):
            raise TimeoutError(
                f"Control layer {self.cl.name} failed to send connection and "
                f"access rights information within {float(timeout):.1f} sec"
            )

    def wait_for_connection(self, timeout=DEFAULT_CONNECTION_TIMEOUT):
        """Wait for the underlying signals to initialize or connect"""
        if timeout is DEFAULT_CONNECTION_TIMEOUT:
            timeout = self.connection_timeout
        try:
            self._ensure_connected(self._read_pv, timeout=timeout)
        except TimeoutError:
            if self._destroyed:
                raise DestroyedError("Signal has been destroyed")
            raise

    @property
    def timestamp(self):
        """Timestamp of readback PV, according to EPICS"""
        return self._metadata["timestamp"]

    @property
    def pvname(self):
        """The readback PV name"""
        return self._read_pvname

    def _repr_info(self):
        "Yields pairs of (key, value) to generate the Signal repr"
        yield ("read_pv", self.pvname)
        yield from super()._repr_info()
        yield ("auto_monitor", self._auto_monitor)
        yield ("string", self._string)

    @property
    def limits(self):
        """The PV control limits (low, high), such that low <= value <= high"""
        # This overrides the base Signal limits
        return (self._metadata["lower_ctrl_limit"], self._metadata["upper_ctrl_limit"])

    def _get_with_timeout(
        self, pv, timeout, connection_timeout, as_string, form, use_monitor
    ):
        """
        Utility method implementing a retry loop for get and get_setpoint

        Returns info from pv.read_with_metadata(...) or raises TimeoutError
        """
        # Fall back to instance default if no value is given.
        if timeout is DEFAULT_TIMEOUT:
            timeout = self.timeout
        if connection_timeout is DEFAULT_CONNECTION_TIMEOUT:
            connection_timeout = self.connection_timeout

        if connection_timeout is not None:
            connection_timeout = float(connection_timeout)

        try:
            self.wait_for_connection(timeout=connection_timeout)
        except TimeoutError as err:
            raise ConnectionTimeoutError(
                f"Failed to connect to {pv.pvname} "
                f"within {connection_timeout:.2f} sec"
            ) from err
        # Pyepics returns None when a read request times out.  Raise a
        # TimeoutError on its behalf.
        self.control_layer_log.debug(
            "pv[%s].get_with_metadata(as_string=%s, form=%s, timeout=%s)",
            pv.pvname,
            as_string,
            form,
            timeout,
        )
        info = pv.get_with_metadata(
            as_string=as_string, form=form, timeout=timeout, use_monitor=use_monitor
        )
        self.control_layer_log.debug(
            "pv[%s].get_with_metadata(...) returned", pv.pvname
        )

        if info is None:
            raise ReadTimeoutError(
                f"Failed to read {pv.pvname} " f"within {timeout:.2f} sec"
            )

        return info

    def get(
        self,
        *,
        as_string=None,
        timeout=DEFAULT_TIMEOUT,
        connection_timeout=DEFAULT_CONNECTION_TIMEOUT,
        form="time",
        use_monitor=None,
        **kwargs,
    ):
        """Get the readback value through an explicit call to EPICS.

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
        form : {'time', 'ctrl'}
            PV form to request

        """
        if kwargs:
            warnings.warn(
                "Signal.get no longer takes keyword arguments; "
                "These are ignored and will be deprecated.",
                DeprecationWarning,
            )
        if as_string is None:
            as_string = self._string

        if use_monitor is None:
            use_monitor = self._auto_monitor

        info = self._get_with_timeout(
            self._read_pv, timeout, connection_timeout, as_string, form, use_monitor
        )

        value = info.pop("value")
        if as_string:
            value = waveform_to_string(value)

        has_monitor = self._monitors[self.pvname] is not None
        if form != "time" or not has_monitor:
            # Different form such as 'ctrl' holds additional data not available
            # through the DBR_TIME channel access monitor
            self._metadata_changed(
                self.pvname,
                info,
                update=True,
                require_timestamp=True,
                from_monitor=False,
            )

        if not has_monitor:
            # No monitor - readback can only be updated here
            self._readback = value
        return self._fix_type(value)

    def _fix_type(self, value):
        "Cast the given value according to the data type of this EpicsSignal"
        if self._string:
            value = waveform_to_string(value)

        return value

    def _get_metadata_from_kwargs(
        self, pvname, cl_metadata, *, require_timestamp=False
    ):
        "Metadata from the control layer -> metadata for this Signal"

        def fix_value(fixer_function, value):
            return (
                fixer_function(value)
                if fixer_function is not None and value is not None
                else value
            )

        metadata = {
            md_key: fix_value(fixer_function, cl_metadata[cl_key])
            for cl_key, (md_key, fixer_function) in self._metadata_key_map[
                pvname
            ].items()
            if cl_metadata.get(cl_key, None) is not None
        }

        if require_timestamp and metadata.get("timestamp", None) is None:
            metadata["timestamp"] = time.time()
        return metadata

    def _read_changed(self, value=None, **kwargs):
        "CA monitor callback indicating that the read value has changed"
        metadata = self._metadata_changed(
            self.pvname, kwargs, update=False, require_timestamp=True, from_monitor=True
        )

        if self._string and "char_value" in kwargs:
            value = kwargs["char_value"]

        # super().put updates self._readback and runs SUB_VALUE
        super().put(
            value=value,
            timestamp=metadata.pop("timestamp"),
            metadata=metadata,
            force=True,
        )

    def describe(self):
        """Return the description as a dictionary

        Returns
        -------
        dict
            Dictionary of name and formatted description string
        """
        if self._readback is DEFAULT_EPICSSIGNAL_VALUE:
            val = self.get()
        else:
            val = self._readback
        lower_ctrl_limit, upper_ctrl_limit = self.limits
        desc = dict(
            source="PV:{}".format(self._read_pvname),
            dtype=data_type(val),
            shape=data_shape(val),
            units=self._metadata["units"],
            lower_ctrl_limit=lower_ctrl_limit,
            upper_ctrl_limit=upper_ctrl_limit,
        )

        if self.precision is not None:
            desc["precision"] = self.precision

        if self.enum_strs is not None:
            desc["enum_strs"] = tuple(self.enum_strs)

        return {self.name: desc}


class EpicsSignalRO(EpicsSignalBase):
    """A read-only EpicsSignal -- that is, one with no `write_pv`

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
    timeout : float or None, optional
        The timeout for serving a read request on a connected channel. This is
        only applied if the PV is connected within connection_timeout (below).

        The default value DEFAULT_TIMEOUT means, "Fall back to class-wide
        default." See EpicsSignalBase.set_defaults to configure class
        defaults.

        Explicitly passing None means, "Wait forever."
    write_timeout : float or None, optional
        The timeout for a reply when put completion is used. This is
        only applied if the PV is connected within connection_timeout (below).

        This is very different than the connection and read timeouts
        above. It relates to how long an action takes to complete, such motor
        motion or data acquisition. Any default value we choose here is likely
        to cause problems---either by being too short and giving up too early
        on a lengthy action or being too long and delaying the report of a
        failure. A finite value can be injected here or, perhaps more usefully,
        via `set` at the Device level, where a context-appropriate value can be
        chosen.
    connection_timeout : float or None, optional
        Timeout for connection. This includes the time to search and establish
        a channel.

        The default value DEFAULT_CONNECTION_TIMEOUT means, "Fall back to
        class-wide default." See EpicsSignalBase.set_defaults to
        configure class defaults.

        Explicitly passing None means, "Wait forever."
    """

    def __init__(self, read_pv, *, string=False, name=None, **kwargs):
        super().__init__(read_pv, string=string, name=name, **kwargs)
        self._metadata["write_access"] = False

    def put(self, *args, **kwargs):
        "Disabled for a read-only signal"
        raise ReadOnlyError("Cannot write to read-only EpicsSignal")

    def set(self, *args, **kwargs):
        "Disabled for a read-only signal"
        raise ReadOnlyError(f"Read-only signal {self} cannot be set to {args}")

    def _pv_access_callback(self, read_access, write_access, pv):
        "Control-layer callback: read PV access rights have changed"
        # Tweak write access here - this is a read-only signal!
        if self._destroyed:
            return

        self._metadata.update(
            read_access=read_access,
            write_access=False,
        )

        was_connected = self.connected
        super()._pv_access_callback(read_access, write_access, pv)
        self._set_event_if_ready()

        if was_connected:
            # _set_event_if_ready, above, will run metadata callbacks
            self._run_metadata_callbacks()


class EpicsSignalNoValidation(EpicsSignalBase):
    """An EpicsSignal that does not verify values on set.
    This signal does support readback, but does not guarantee that
    the readback will match the set value.

    Keyword arguments are passed on to the base class (Signal) initializer

    Parameters
    ----------
    write_pv : str
        The PV to write to
    name : str, optional
        Name of signal.  If not given defaults to write_pv
    write_timeout : float or None, optional
        The timeout for a reply when put completion is used. This is
        only applied if the PV is connected within connection_timeout (below).

        This is very different than the connection and read timeouts
        above. It relates to how long an action takes to complete, such motor
        motion or data acquisition. Any default value we choose here is likely
        to cause problems---either by being too short and giving up too early
        on a lengthy action or being too long and delaying the report of a
        failure. A finite value can be injected here or, perhaps more usefully,
        via `set` at the Device level, where a context-appropriate value can be
        chosen.
    connection_timeout : float or None, optional
        Timeout for connection. This includes the time to search and establish
        a channel.

        The default value DEFAULT_CONNECTION_TIMEOUT means, "Fall back to
        class-wide default." See EpicsSignalBase.set_defaults to
        configure class defaults.

        Explicitly passing None means, "Wait forever."
    """

    def set(self, value, *args, **kwargs):
        """
        Set the value of this signal, and return a completed Status
        object, bypassing any readback verification

        Returns
        -------
        st : Status
            This status object will be finished
        """
        self.put(value)

        st = Status(self)
        st.set_finished()
        st.wait()
        return st


class EpicsSignal(EpicsSignalBase):
    """An EPICS signal, comprised of either one or two EPICS PVs

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
    timeout : float or None, optional
        The timeout for serving a read request on a connected channel. This is
        only applied if the PV is connected within connection_timeout (below).

        The default value DEFAULT_TIMEOUT means, "Fall back to class-wide
        default." See EpicsSignalBase.set_defaults to configure class
        defaults.

        Explicitly passing None means, "Wait forever."
    write_timeout : float or None, optional
        The timeout for a reply when put completion is used. This is
        only applied if the PV is connected within connection_timeout (below).

        This is very different than the connection and read timeouts
        above. It relates to how long an action takes to complete, such motor
        motion or data acquisition. Any default value we choose here is likely
        to cause problems---either by being too short and giving up too early
        on a lengthy action or being too long and delaying the report of a
        failure. A finite value can be injected here or, perhaps more usefully,
        via `set` at the Device level, where a context-appropriate value can be
        chosen.
    connection_timeout : float or None, optional
        Timeout for connection. This includes the time to search and establish
        a channel.

        The default value DEFAULT_CONNECTION_TIMEOUT means, "Fall back to
        class-wide default." See EpicsSignalBase.set_defaults to
        configure class defaults.

        Explicitly passing None means, "Wait forever."
    """

    SUB_SETPOINT = "setpoint"
    SUB_SETPOINT_META = "setpoint_meta"

    _write_pv_metadata_key_map = dict(
        status=("setpoint_status", AlarmStatus),
        severity=("setpoint_severity", AlarmSeverity),
        precision=("setpoint_precision", None),
        timestamp=("setpoint_timestamp", None),
        # Override the readback ones, as we write to the setpoint:
        lower_ctrl_limit=("lower_ctrl_limit", None),
        upper_ctrl_limit=("upper_ctrl_limit", None),
    )

    _metadata_keys = EpicsSignalBase._metadata_keys + (
        "setpoint_status",
        "setpoint_severity",
        "setpoint_precision",
        "setpoint_timestamp",
    )

    def __init__(
        self,
        read_pv,
        write_pv=None,
        *,
        put_complete=False,
        string=False,
        limits=False,
        name=None,
        **kwargs,
    ):

        self._write_pv = None
        self._use_limits = bool(limits)
        self._put_complete = put_complete
        self._setpoint = None

        metadata = dict(
            setpoint_timestamp=None,
            setpoint_status=None,
            setpoint_severity=None,
            lower_ctrl_limit=None,
            upper_ctrl_limit=None,
        )

        if write_pv is None:
            write_pv = read_pv

        self._setpoint_pvname = write_pv

        super().__init__(
            read_pv,
            string=string,
            name=name,
            metadata=metadata,
            all_pvs={read_pv, write_pv},
            **kwargs,
        )

        if read_pv == write_pv:
            self._write_pv = self._read_pv
        else:
            validate_pv_name(write_pv)
            self._metadata_key_map = {
                write_pv: self._write_pv_metadata_key_map,
                read_pv: {
                    key: value
                    for key, value in self._metadata_key_map[read_pv].items()
                    if key not in ("lower_ctrl_limit", "upper_ctrl_limit")
                },
            }

            self._write_pv = self.cl.get_pv(
                write_pv,
                auto_monitor=self._auto_monitor,
                connection_callback=self._pv_connected,
                access_callback=self._pv_access_callback,
            )

        self._write_pv._reference_count += 1

        # NOTE: after this point, write_pv can either be:
        #  (1) the same as read_pv
        #  (2) a completely separate PV instance
        # It will not be None, until destroy() is called.

        def finalize(write_pv, cl):
            cl.release_pvs(write_pv)

        self._write_pv_finalizer = weakref.finalize(
            self, finalize, self._write_pv, self.cl
        )

    def destroy(self):
        super().destroy()
        self._write_pv_finalizer()

    @doc_annotation_forwarder(EpicsSignalBase)
    def subscribe(self, callback, event_type=None, run=True):
        if event_type is None:
            event_type = self._default_sub

        if event_type == self.SUB_SETPOINT:
            self._add_callback(
                self._setpoint_pvname, self._write_pv, self._write_changed
            )

        return super().subscribe(callback, event_type=event_type, run=run)

    def wait_for_connection(self, timeout=DEFAULT_CONNECTION_TIMEOUT):
        """Wait for the underlying signals to initialize or connect"""
        if timeout is DEFAULT_CONNECTION_TIMEOUT:
            timeout = self.connection_timeout
        self._ensure_connected(self._read_pv, self._write_pv, timeout=timeout)

    @property
    def tolerance(self):
        """The tolerance of the write PV, as reported by EPICS

        Can be overidden by the user at the EpicsSignal level.

        Returns
        -------
        tolerance : float or None
        Using the write PV's precision:
            If precision == 0, tolerance will be None
            If precision > 0, calculated to be 10**(-precision)
        """
        # NOTE: overrides Signal.tolerance property
        if self._tolerance is not None:
            return self._tolerance

        precision = self.precision
        if precision == 0 or precision is None:
            return None

        return 10.0 ** (-precision)

    @tolerance.setter
    def tolerance(self, tolerance):
        self._tolerance = tolerance

    @property
    def setpoint_ts(self):
        """Timestamp of setpoint PV, according to EPICS"""
        return self._metadata["setpoint_timestamp"]

    @property
    def setpoint_pvname(self):
        """The setpoint PV name"""
        return self._setpoint_pvname

    @property
    def setpoint_alarm_status(self):
        """Setpoint PV status"""
        return self._metadata["setpoint_status"]

    @property
    def setpoint_alarm_severity(self):
        """Setpoint PV alarm severity"""
        return self._metadata["setpoint_severity"]

    def _repr_info(self):
        "Yields pairs of (key, value) to generate the Signal repr"
        yield from super()._repr_info()
        yield ("write_pv", self._setpoint_pvname)
        yield ("limits", self._use_limits)
        yield ("put_complete", self._put_complete)

    def check_value(self, value):
        """Check if the value is within the setpoint PV's control limits

        Raises
        ------
        ValueError
        """
        super().check_value(value)

        if value is None:
            raise ValueError("Cannot write None to epics PVs")
        if not self._use_limits:
            return

        low_limit, high_limit = self.limits
        if low_limit >= high_limit:
            return

        if not (low_limit <= value <= high_limit):
            raise LimitError(
                "{}: value {} outside of range: [{}, {}]".format(
                    self.name, value, low_limit, high_limit
                )
            )

    def get_setpoint(
        self,
        *,
        as_string=None,
        timeout=DEFAULT_TIMEOUT,
        connection_timeout=DEFAULT_CONNECTION_TIMEOUT,
        use_monitor=None,
        form="time",
        **kwargs,
    ):
        """Get the setpoint value (if setpoint PV and readback PV differ)

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
        form : {'time', 'ctrl'}
            PV form to request
        """
        if kwargs:
            warnings.warn(
                "Signal.get_setpoint no longer takes keyword arguments; "
                "These are ignored and will be deprecated.",
                DeprecationWarning,
            )
        if as_string is None:
            as_string = self._string

        if use_monitor is None:
            use_monitor = self._auto_monitor

        info = self._get_with_timeout(
            self._write_pv, timeout, connection_timeout, as_string, form, use_monitor
        )

        value = info.pop("value")
        if as_string:
            value = waveform_to_string(value)

        has_monitor = self._monitors[self.setpoint_pvname] is not None
        if form != "time" or not has_monitor:
            # Different form such as 'ctrl' holds additional data not available
            # through the DBR_TIME channel access monitor
            self._metadata_changed(
                self.setpoint_pvname,
                info,
                update=True,
                from_monitor=False,
                require_timestamp=True,
            )

        if not has_monitor:
            # No monitor - setpoint can only be updated here
            self._setpoint = self._fix_type(value)
        return self._fix_type(value)

    def _pv_access_callback(self, read_access, write_access, pv):
        "Control-layer callback: PV access rights have changed"
        if self._destroyed:
            return

        md_update = {}
        if pv.pvname == self.pvname:
            md_update["read_access"] = read_access

        if pv.pvname == self.setpoint_pvname:
            md_update["write_access"] = write_access

        if md_update:
            self._metadata.update(**md_update)

        if self.connected:
            self._run_metadata_callbacks()

        super()._pv_access_callback(read_access, write_access, pv)
        self._set_event_if_ready()

    def _metadata_changed(
        self, pvname, cl_metadata, *, from_monitor, update, require_timestamp=False
    ):
        "Metadata for one PV has changed"
        metadata = super()._metadata_changed(
            pvname,
            cl_metadata,
            from_monitor=from_monitor,
            update=update,
            require_timestamp=require_timestamp,
        )

        if all(
            (
                from_monitor,
                self.setpoint_pvname != self.pvname,
                self.setpoint_pvname == pvname,
            )
        ):
            # Setpoint has its own metadata
            self._metadata_thread_ctx.run(
                self._run_subs,
                sub_type=self.SUB_SETPOINT_META,
                timestamp=self._metadata["setpoint_timestamp"],
                status=self._metadata["setpoint_status"],
                severity=self._metadata["setpoint_severity"],
                precision=self._metadata["setpoint_precision"],
                lower_ctrl_limit=self._metadata["lower_ctrl_limit"],
                upper_ctrl_limit=self._metadata["upper_ctrl_limit"],
                units=self._metadata["units"],
            )
        return metadata

    def _write_changed(self, value=None, timestamp=None, **kwargs):
        "CA monitor: callback indicating the setpoint PV value has changed"
        if timestamp is None:
            timestamp = time.time()

        self._metadata_changed(
            self.setpoint_pvname,
            kwargs,
            require_timestamp=True,
            from_monitor=True,
            update=True,
        )

        old_value = self._setpoint
        self._setpoint = self._fix_type(value)

        self._run_subs(
            sub_type=self.SUB_SETPOINT,
            old_value=old_value,
            value=value,
            timestamp=self._metadata["setpoint_timestamp"],
            status=self._metadata["setpoint_status"],
            severity=self._metadata["setpoint_severity"],
        )

    def put(
        self,
        value,
        force=False,
        connection_timeout=DEFAULT_CONNECTION_TIMEOUT,
        callback=None,
        use_complete=None,
        timeout=DEFAULT_WRITE_TIMEOUT,
        **kwargs,
    ):
        """
        Using channel access, set the write PV to ``value``.

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
        callback : callable
            Callback for when the put has completed
        timeout : float, optional
            Timeout before assuming that put has failed. (Only relevant if
            put completion is used.)
        """
        if not force:
            self.check_value(value)

        if connection_timeout is DEFAULT_CONNECTION_TIMEOUT:
            connection_timeout = self.connection_timeout
        if timeout is DEFAULT_WRITE_TIMEOUT:
            timeout = self.write_timeout
        self.wait_for_connection(timeout=connection_timeout)
        if use_complete is None:
            use_complete = self._put_complete

        if not self.write_access:
            raise ReadOnlyError("No write access to underlying EPICS PV")

        self.control_layer_log.debug(
            "_write_pv.put(value=%s, use_complete=%s, callback=%s, kwargs=%s)",
            value,
            use_complete,
            callback,
            kwargs,
        )
        self._write_pv.put(
            value,
            use_complete=use_complete,
            callback=callback,
            timeout=timeout,
            **kwargs,
        )

        old_value = self._setpoint
        self._setpoint = value

        if self.pvname == self.setpoint_pvname:
            timestamp = time.time()
            super().put(value, timestamp=timestamp, force=True)
            self._run_subs(
                sub_type=self.SUB_SETPOINT,
                old_value=old_value,
                value=value,
                timestamp=timestamp,
            )

    def set(self, value, *, timeout=DEFAULT_WRITE_TIMEOUT, settle_time=None):
        """
        Set the value of the Signal and return a Status object.

        If put completion is used for this EpicsSignal, the status object will
        complete once EPICS reports the put has completed.

        Otherwise the readback will be polled until equal to the set point (as
        in `Signal.set`)

        Parameters
        ----------
        value : any
        timeout : float, optional
            Maximum time to wait.
        settle_time: float, optional
            Delay after the set() has completed to indicate completion
            to the caller

        Returns
        -------
        st : Status

        See Also
        --------
        Signal.set

        """
        if timeout is DEFAULT_WRITE_TIMEOUT:
            timeout = self.write_timeout

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
        """The setpoint PV value"""
        if self._setpoint is not None:
            return self._setpoint

        return self.get_setpoint()

    @setpoint.setter
    def setpoint(self, value):
        warnings.warn(
            "Setting EpicsSignal.setpoint is deprecated and " "will be removed"
        )
        self.put(value)

    @property
    def put_complete(self):
        "Use put completion when writing the value"
        return self._put_complete

    @put_complete.setter
    def put_complete(self, value):
        self._put_complete = bool(value)

    @property
    def use_limits(self):
        "Check value against limits prior to sending to EPICS"
        return self._use_limits

    @use_limits.setter
    def use_limits(self, value):
        self._use_limits = bool(value)


class AttributeSignal(Signal):
    """Signal derived from a Python object instance's attribute

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
    """

    def __init__(self, attr, *, name=None, parent=None, write_access=True, **kwargs):
        super().__init__(name=name, parent=parent, **kwargs)

        if "." in attr:
            self.attr_base, self.attr = attr.rsplit(".", 1)
        else:
            self.attr_base, self.attr = None, attr

        self._metadata.update(
            read_access=True,
            write_access=write_access,
        )

    @property
    def full_attr(self):
        """The full attribute name"""
        if not self.attr_base:
            return self.attr
        else:
            return ".".join((self.attr_base, self.attr))

    @property
    def base(self):
        """The parent instance which has the final attribute"""
        if self.attr_base is None:
            return self.parent

        obj = self.parent
        for i, part in enumerate(self.attr_base.split(".")):
            try:
                obj = getattr(obj, part)
            except AttributeError as ex:
                raise AttributeError("{}.{} ({})".format(obj.name, part, ex))

        return obj

    def get(self, **kwargs):
        "Get the value from the associated attribute"
        self._readback = getattr(self.base, self.attr)
        return self._readback

    def put(self, value, **kwargs):
        "Write to the associated attribute"
        if not self.write_access:
            raise ReadOnlyError("AttributeSignal is marked as read-only")

        old_value = self.get()
        setattr(self.base, self.attr, value)
        self._run_subs(
            sub_type=self.SUB_VALUE,
            old_value=old_value,
            value=value,
            timestamp=time.time(),
        )

    def describe(self):
        value = self.get()
        desc = {
            "source": "PY:{}.{}".format(self.parent.name, self.full_attr),
            "dtype": data_type(value),
            "shape": data_shape(value),
        }
        return {self.name: desc}


class ArrayAttributeSignal(AttributeSignal):
    """An AttributeSignal which is cast to an ndarray on get

    This is used where data_type and data_shape may otherwise fail to determine
    how to store the data into metadatastore.
    """

    def get(self, **kwargs):
        return np.asarray(super().get(**kwargs))
