# type: ignore

from __future__ import annotations

import collections
import contextlib
import functools
import inspect
import itertools
import logging
import operator
import textwrap
import time as ttime
import typing
import warnings
from collections import OrderedDict, namedtuple
from collections.abc import Iterable, MutableSequence
from enum import Enum
from typing import (
    Any,
    Callable,
    ClassVar,
    DefaultDict,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from .ophydobj import Kind, OphydObject
from .signal import Signal
from .status import DeviceStatus, StatusBase
from .utils import (
    ExceptionBundle,
    RedundantStaging,
    doc_annotation_forwarder,
    getattrs,
    underscores_to_camel_case,
)

A, B = TypeVar("A"), TypeVar("B")
ALL_COMPONENTS = object()
# This attrs are defined at instanitation time and must not
# collide with class attributes.
DEVICE_INSTANCE_ATTRS = {
    "name",
    "parent",
    "component_names",
    "_signals",
    "_sig_attrs",
    "_sub_devices",
}
# These attributes are part of the bluesky interface and cannot be
# used as component names.
DEVICE_RESERVED_ATTRS = {
    "read",
    "describe",
    "trigger",
    "configure",
    "read_configuration",
    "describe_configuration",
    "describe_collect",
    "set",
    "stage",
    "unstage",
    "pause",
    "resume",
    "kickoff",
    "complete",
    "collect",
    "position",
    "stop",
    # from OphydObject
    "subscribe",
    "clear_sub",
    "event_types",
    "root",
    # for back-compat
    "signal_names",
}


class OrderedDictType(Dict[A, B]):
    ...


logger = logging.getLogger(__name__)


class Staged(Enum):
    """Three-state switch"""

    yes = "yes"
    no = "no"
    partially = "partially"


ComponentWalk = namedtuple("ComponentWalk", "ancestors dotted_name item")


K = TypeVar("K", bound=OphydObject)


class Component(typing.Generic[K]):
    """A descriptor representing a device component (or signal)

    Unrecognized keyword arguments will be passed directly to the component
    class initializer.

    Parameters
    ----------
    cls : class
        Class of signal to create.  The required signature of `cls.__init__` is
        (if `suffix` is given)::

            def __init__(self, pv_name, parent=None, **kwargs):

        or (if suffix is None) ::

            def __init__(self, parent=None, **kwargs):

        The class may have a `wait_for_connection()` which is called during the
        component instance creation.

    suffix : str, optional
        The PV suffix, which gets appended onto ``parent.prefix`` to generate
        the final PV that the instance component will bind to.
        Also see ``add_prefix``

    lazy : bool, optional
        Lazily instantiate the signal. If ``False``, the signal will be
        instantiated upon component instantiation.  Defaults to
        ``component.lazy_default``.

    trigger_value : any, optional
        Mark as a signal to be set on trigger. The value is sent to the signal
        at trigger time.

    add_prefix : sequence, optional
        Keys in the kwargs to prefix with the Device PV prefix during creation
        of the component instance.
        Defaults to ``('suffix', 'write_pv', )``

    doc : str, optional
        string to attach to component DvcClass.component.__doc__
    """

    #: Default laziness for the component class.
    lazy_default: ClassVar[bool] = False

    #: The attribute name of the component.
    attr: Optional[str]
    #: The class to instantiate when the device is created.
    cls: Type[K]
    #: Keyword arguments for the device creation.
    kwargs: Dict[str, Any]
    #: Lazily create components on access.
    lazy: bool
    #: PV or identifier suffix.
    suffix: Optional[str]
    #: Documentation string.
    doc: Optional[str]
    #: Value to send on ``trigger()``
    trigger_value: Optional[Any]
    #: The data acquisition kind.
    kind: Kind
    #: Names of kwarg keys to prepend the device PV prefix to.
    add_prefix: Tuple[str, ...]
    #: Subscription name -> subscriptions marked by decorator.
    _subscriptions: DefaultDict[str, List[Callable]]

    def __init__(
        self,
        cls: Type[K],
        suffix: Optional[str] = None,
        *,
        lazy: Optional[bool] = None,
        trigger_value: Optional[Any] = None,
        add_prefix: Optional[Sequence[str]] = None,
        doc: Optional[str] = None,
        kind: Union[str, Kind] = Kind.normal,
        **kwargs,
    ):
        self.attr = None  # attr is set later by the device when known
        self.cls = cls
        self.kwargs = kwargs
        self.lazy = lazy if lazy is not None else self.lazy_default
        self.suffix = suffix
        self.doc = doc
        self.trigger_value = trigger_value  # TODO discuss
        self.kind = Kind[kind.lower()] if isinstance(kind, str) else Kind(kind)
        if add_prefix is None:
            add_prefix = ("suffix", "write_pv")
        self.add_prefix = tuple(add_prefix)
        self._subscriptions = collections.defaultdict(list)

    def _get_class_from_annotation(self) -> Optional[Type[K]]:
        """Get a class from the Component[cls] annotation."""
        annotation = getattr(self, "__orig_class__", None)
        if not annotation:
            return None

        args = typing.get_args(annotation)
        if not args or not len(args) == 1:
            return None
        return args[0]

    def __set_name__(self, owner, attr_name: str):
        self.attr = attr_name
        if self.doc is None:
            self.doc = self.make_docstring(owner)

    @property
    def is_device(self):
        "Does this Component contain a Device?"
        return isinstance(self.cls, type) and issubclass(self.cls, Device)

    @property
    def is_signal(self):
        "Does this Component contain a Signal?"
        return isinstance(self.cls, type) and issubclass(self.cls, Signal)

    def maybe_add_prefix(self, instance, kw, suffix):
        """Add prefix to a suffix if kw is in self.add_prefix

        Parameters
        ----------
        instance : Device
            The instance to extract the prefix to maybe append to the
            suffix from.

        kw : str
            The key of associated with the suffix.  If this key is
            self.add_prefix than prepend the prefix to the suffix and
            return, else just return the suffix.

        suffix : str
            The suffix to maybe have something prepended to.

        Returns
        -------
        str
        """
        if kw in self.add_prefix:
            return f"{instance.prefix}{suffix}"
        return suffix

    def create_component(self, instance):
        "Instantiate the object described by this Component for a Device"
        kwargs = self.kwargs.copy()
        kwargs.update(
            name=f"{instance.name}_{self.attr}",
            kind=instance._component_kinds[self.attr],
            attr_name=self.attr,
        )

        for kw, val in list(kwargs.items()):
            kwargs[kw] = self.maybe_add_prefix(instance, kw, val)

        if self.suffix is not None:
            pv_name = self.maybe_add_prefix(instance, "suffix", self.suffix)
            cpt_inst = self.cls(pv_name, parent=instance, **kwargs)
        else:
            cpt_inst = self.cls(parent=instance, **kwargs)

        if self.lazy and hasattr(self.cls, "wait_for_connection"):
            if getattr(instance, "lazy_wait_for_connection", True):
                cpt_inst.wait_for_connection()

        return cpt_inst

    def make_docstring(self, parent_class):
        "Create a docstring for the Component"
        if self.doc is not None:
            return self.doc

        doc = [
            "{} attribute".format(self.__class__.__name__),
            "::",
            "",
        ]

        doc.append(textwrap.indent(repr(self), prefix=" " * 4))
        doc.append("")
        return "\n".join(doc)

    def __repr__(self):
        repr_dict = self.kwargs.copy()
        repr_dict.pop("read_attrs", None)
        repr_dict.pop("configuration_attrs", None)
        repr_dict["kind"] = self.kind.name

        kw_str = ", ".join(f"{k}={v!r}" for k, v in repr_dict.items())
        suffix = repr(self.suffix) if self.suffix else ""

        component_class = self.cls.__name__
        args = ", ".join(s for s in (component_class, suffix, kw_str) if s)

        this_class = self.__class__.__name__
        return f"{this_class}({args})"

    __str__ = __repr__

    @typing.overload
    def __get__(self, instance: None, owner: type) -> Component[K]:
        ...

    @typing.overload
    def __get__(self, instance: Device, owner: type) -> K:
        ...

    def __get__(
        self,
        instance: Optional[Device],
        owner: type,
    ) -> Union[Component, K]:
        if instance is None:
            return self

        try:
            return instance._signals[self.attr]
        except KeyError:
            return instance._instantiate_component(self.attr)

    def __set__(self, instance, owner):
        raise RuntimeError("Do not use setattr with components; use " "cpt.put(value)")

    def subscriptions(self, event_type):
        """(Decorator) Specify subscriptions callbacks in the Device definition

        Parameters
        ----------
        event_type : str or None
            Event type to subscribe to. `ophyd.Signal` supports at least
            {'value', 'meta'}.  An `event_type` of `None` indicates that the
            default event type for the signal is to be used.

        Returns
        -------
        subscriber : callable
            Callable with signature `subscriber(func)`, where `func` is the
            method to call when the subscription of event_type is fired.
        """

        def subscriber(func):
            self._subscriptions[event_type].append(func)
            if not hasattr(func, "_subscriptions"):
                func._subscriptions = []
            func._subscriptions.append((self, event_type))
            return func

        return subscriber

    def sub_default(self, func):
        "Default subscription decorator"
        return self.subscriptions(None)(func)

    def sub_meta(self, func):
        "Metadata subscription decorator"
        return self.subscriptions("meta")(func)

    def sub_value(self, func):
        "Value subscription decorator"
        return self.subscriptions("value")(func)


class FormattedComponent(Component[K]):
    """A Component which takes a dynamic format string

    This differs from Component in that the parent prefix is not automatically
    added onto the Component suffix. Additionally, `str.format()` style strings
    are accepted, allowing access to Device instance attributes:

    >>> from ophyd import (Component as Cpt, FormattedComponent as FCpt)
    >>> class MyDevice(Device):
    ...     # A normal component, where 'suffix' is added to prefix verbatim
    ...     cpt = Cpt(EpicsSignal, 'suffix')
    ...     # A formatted component, where 'self' refers to the Device instance
    ...     ch = FCpt(EpicsSignal, '{self.prefix}{self._ch_name}')
    ...     # A formatted component, where 'self' is assumed
    ...     ch = FCpt(EpicsSignal, '{prefix}{_ch_name}')
    ...
    ...     def __init__(self, prefix, ch_name=None, **kwargs):
    ...         self._ch_name = ch_name
    ...         super().__init__(prefix, **kwargs)

    >>> dev = MyDevice('prefix:', ch_name='some_channel', name='dev')
    >>> print(dev.cpt.pvname)
    prefix:suffix
    >>> print(dev.ch.pvname)
    prefix:some_channel

    For additional documentation, refer to Component.
    """

    def maybe_add_prefix(self, instance, kw, suffix):
        if kw not in self.add_prefix:
            return suffix

        format_dict = dict(instance.__dict__)
        format_dict["self"] = instance
        return suffix.format(**format_dict)


class DynamicDeviceComponent(Component["Device"]):
    """An Device component that dynamically creates an ophyd Device

    Parameters
    ----------
    defn : OrderedDict
        The definition of all attributes to be created, in the form of::

            defn['attribute_name'] = (SignalClass, pv_suffix, keyword_arg_dict)

        This will create an attribute on the sub-device of type `SignalClass`,
        with a suffix of pv_suffix, which looks something like this::

            parent.sub.attribute_name = Cpt(SignalClass, pv_suffix, **keyword_arg_dict)

        Keep in mind that this is actually done in the metaclass creation, and
        not exactly as written above.
    clsname : str, optional
        The name of the class to be generated
        This defaults to {parent_name}{this_attribute_name.capitalize()}
    doc : str, optional
        The docstring to put on the dynamically generated class
    default_read_attrs : list, optional
        A class attribute to put on the dynamically generated class
    default_configuration_attrs : list, optional
        A class attribute to put on the dynamically generated class
    component_class : class, optional
        Defaults to Component
    base_class : class, optional
        Defaults to Device
    """

    def __init__(
        self,
        defn,
        *,
        clsname=None,
        doc=None,
        kind=Kind.normal,
        default_read_attrs=None,
        default_configuration_attrs=None,
        component_class=Component,
        base_class=None,
    ):
        if isinstance(default_read_attrs, Iterable):
            default_read_attrs = tuple(default_read_attrs)

        if isinstance(default_configuration_attrs, Iterable):
            default_configuration_attrs = tuple(default_configuration_attrs)

        self.defn = defn
        self.clsname = clsname
        self.default_read_attrs = default_read_attrs
        self.default_configuration_attrs = default_configuration_attrs
        self.attrs = list(defn.keys())
        self.component_class = component_class
        self.base_class = base_class if base_class is not None else Device
        self.components = {
            attr: component_class(cls, suffix, **kwargs)
            for attr, (cls, suffix, kwargs) in self.defn.items()
        }

        # NOTE: cls is None here, as it gets created in __set_name__, below
        super().__init__(cls=None, suffix="", lazy=False, kind=kind)

        # Allow easy access to all generated components directly in the
        # DynamicDeviceComponent instance
        for attr, cpt in self.components.items():
            if not hasattr(self, attr):
                setattr(self, attr, cpt)

    def __getnewargs_ex__(self):
        "Get arguments needed to copy this class (used for pickle/copy)"
        kwargs = dict(
            clsname=self.clsname,
            doc=self.doc,
            kind=self.kind,
            default_read_attrs=self.default_read_attrs,
            default_configuration_attrs=self.default_configuration_attrs,
            component_class=self.component_class,
            base_class=self.base_class,
        )
        return ((self.defn,), kwargs)

    def __set_name__(self, owner, attr_name):
        if self.clsname is None:
            self.clsname = underscores_to_camel_case(attr_name)
        super().__set_name__(owner, attr_name)
        self.cls = create_device_from_components(
            self.clsname,
            default_read_attrs=self.default_read_attrs,
            default_configuration_attrs=self.default_configuration_attrs,
            base_class=self.base_class,
            **self.components,
        )

    def __repr__(self):
        return "\n".join(f"{attr} = {cpt!r}" for attr, cpt in self.components.items())

    def subscriptions(self, event_type):
        raise NotImplementedError(
            "DynamicDeviceComponent does not yet " "support decorator subscriptions"
        )


# These stub 'Interface' classes are the apex of the mro heirarchy for
# their respective methods. They make multiple interitance more
# forgiving, and let us define classes that customize these methods
# but are not full Devices.


class BlueskyInterface:
    """Classes that inherit from this can safely customize the
    these methods without breaking mro.

    """

    def __init__(self, *args, **kwargs):
        # Subclasses can populate this with (signal, value) pairs, to be
        # set by stage() and restored back by unstage().
        self.stage_sigs = OrderedDict()

        self._staged = Staged.no
        self._original_vals = OrderedDict()
        super().__init__(*args, **kwargs)

    def trigger(self) -> StatusBase:
        """Trigger the device and return status object.

        This method is responsible for implementing 'trigger' or
        'acquire' functionality of this device.

        If there is an appreciable time between triggering the device
        and it being able to be read (via the
        :meth:`~BlueskyInterface.read` method) then this method is
        also responsible for arranging that the
        :obj:`~ophyd.status.StatusBase` object returned by this method
        is notified when the device is ready to be read.

        If there is no delay between triggering and being readable,
        then this method must return a :obj:`~ophyd.status.StatusBase`
        object which is already completed.

        Returns
        -------
        status : StatusBase
            :obj:`~ophyd.status.StatusBase` object which will be marked
            as complete when the device is ready to be read.

        """
        pass

    def read(self) -> OrderedDictType[str, Dict[str, Any]]:
        """Read data from the device.

        This method is expected to be as instantaneous as possible,
        with any substantial acquisition time taken care of in
        :meth:`~BlueskyInterface.trigger`.

        The `OrderedDict` returned by this method must have identical
        keys (in the same order) as the `OrderedDict` returned by
        :meth:`~BlueskyInterface.describe()`.

        By convention, the first key in the return is the 'primary' key
        and maybe used by heuristics in :mod:`bluesky`.

        The values in the ordered dictionary must be dict (-likes) with the
        keys ``{'value', 'timestamp'}``.  The ``'value'`` may have any type,
        the timestamp must be a float UNIX epoch timestamp in UTC.

        Returns
        -------
        data : OrderedDict
            The keys must be strings and the values must be dict-like
            with the keys ``{'value', 'timestamp'}``

        """
        return OrderedDict()

    def describe(self) -> OrderedDictType[str, Dict[str, Any]]:
        """Provide schema and meta-data for :meth:`~BlueskyInterface.read`.

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
        return OrderedDict()

    def stage(self) -> List[object]:
        """Stage the device for data collection.

        This method is expected to put the device into a state where
        repeated calls to :meth:`~BlueskyInterface.trigger` and
        :meth:`~BlueskyInterface.read` will 'do the right thing'.

        Staging not idempotent and should raise
        :obj:`RedundantStaging` if staged twice without an
        intermediate :meth:`~BlueskyInterface.unstage`.

        This method should be as fast as is feasible as it does not return
        a status object.

        The return value of this is a list of all of the (sub) devices
        stage, including it's self.  This is used to ensure devices
        are not staged twice by the :obj:`~bluesky.run_engine.RunEngine`.

        This is an optional method, if the device does not need
        staging behavior it should not implement `stage` (or
        `unstage`).

        Returns
        -------
        devices : list
            list including self and all child devices staged

        """
        if self._staged == Staged.no:
            pass  # to short-circuit checking individual cases
        elif self._staged == Staged.yes:
            raise RedundantStaging(
                "Device {!r} is already staged. " "Unstage it first.".format(self)
            )
        elif self._staged == Staged.partially:
            raise RedundantStaging(
                "Device {!r} has been partially staged. "
                "Maybe the most recent unstaging "
                "encountered an error before finishing. "
                "Try unstaging again.".format(self)
            )
        self.log.debug("Staging %s", self.name)
        self._staged = Staged.partially

        # Resolve any stage_sigs keys given as strings: 'a.b' -> self.a.b
        stage_sigs = OrderedDict()
        for k, v in self.stage_sigs.items():
            if isinstance(k, str):
                # Device.__getattr__ handles nested attr lookup
                stage_sigs[getattr(self, k)] = v
            else:
                stage_sigs[k] = v

        # Read current values, to be restored by unstage()
        original_vals = {sig: sig.get() for sig in stage_sigs}

        # We will add signals and values from original_vals to
        # self._original_vals one at a time so that
        # we can undo our partial work in the event of an error.

        # Apply settings.
        devices_staged = []
        try:
            for sig, val in stage_sigs.items():
                self.log.debug(
                    "Setting %s to %r (original value: %r)",
                    sig.name,
                    val,
                    original_vals[sig],
                )
                sig.set(val).wait()
                # It worked -- now add it to this list of sigs to unstage.
                self._original_vals[sig] = original_vals[sig]
            devices_staged.append(self)

            # Call stage() on child devices.
            for attr in self._sub_devices:
                device = getattr(self, attr)
                if hasattr(device, "stage"):
                    device.stage()
                    devices_staged.append(device)
        except Exception:
            self.log.debug(
                "An exception was raised while staging %s or "
                "one of its children. Attempting to restore "
                "original settings before re-raising the "
                "exception.",
                self.name,
            )
            self.unstage()
            raise
        else:
            self._staged = Staged.yes
        return devices_staged

    def unstage(self) -> List[object]:
        """Unstage the device.

        This method returns the device to the state it was prior to the
        last `stage` call.

        This method should be as fast as feasible as it does not
        return a status object.

        This method must be idempotent, multiple calls (without a new
        call to 'stage') have no effect.

        Returns
        -------
        devices : list
            list including self and all child devices unstaged

        """
        self.log.debug("Unstaging %s", self.name)
        self._staged = Staged.partially
        devices_unstaged = []

        # Call unstage() on child devices.
        for attr in self._sub_devices[::-1]:
            device = getattr(self, attr)
            if hasattr(device, "unstage"):
                device.unstage()
                devices_unstaged.append(device)

        # Restore original values.
        for sig, val in reversed(list(self._original_vals.items())):
            self.log.debug("Setting %s back to its original value: %r", sig.name, val)
            sig.set(val).wait()
            self._original_vals.pop(sig)
        devices_unstaged.append(self)

        self._staged = Staged.no
        return devices_unstaged

    def pause(self) -> None:
        """Attempt to 'pause' the device.

        This is called when ever the
        :obj:`~bluesky.run_engine.RunEngine` is interrupted.

        A device may have internal state that means plans can not
        safely be re-wound.  This method may: put the device in a
        'paused' state and/or raise
        :obj:`~bluesky.run_engine.NoReplayAllowed` to indicate that
        the plan can not be rewound.

        Raises
        ------
        bluesky.run_engine.NoReplayAllowed

        """
        pass

    def resume(self) -> None:
        """Resume a device from a 'paused' state.

        This is called by the :obj:`bluesky.run_engine.RunEngine`
        when it resumes from an interruption and is responsible for
        ensuring that the device is ready to take data again.
        """
        pass

    def _validate_kind(self, val):
        return super()._validate_kind(val)


class GenerateDatumInterface:
    """Classes that inherit from this can safely customize the
    `generate_datum` method without breaking mro. If used along with the
    BlueskyInterface, inherit from this second."""

    def generate_datum(self, key, timestamp, datum_kwargs):
        pass


class Device(BlueskyInterface, OphydObject):
    """Base class for device objects

    This class provides attribute access to one or more Signals, which can be
    a mixture of read-only and writable. All must share the same base_name.

    Parameters
    ----------
    prefix : str, optional
        The PV prefix for all components of the device
    name : str, keyword only
        The name of the device (as will be reported via read()`
    kind : a member of the :class:`~ophydobj.Kind` :class:`~enum.IntEnum`
        (or equivalent integer), optional
        Default is ``Kind.normal``. See :class:`~ophydobj.Kind` for options.
    read_attrs : sequence of attribute names
        DEPRECATED: the components to include in a normal reading
        (i.e., in ``read()``)
    configuration_attrs : sequence of attribute names
        DEPRECATED: the components to be read less often (i.e., in
        ``read_configuration()``) and to adjust via ``configure()``
    parent : instance or None, optional
        The instance of the parent device, if applicable

    Attributes
    ----------
    lazy_wait_for_connection : bool
        When instantiating a lazy signal upon first access, wait for it to
        connect before returning control to the user.  See also the context
        manager helpers: ``wait_for_lazy_connection`` and
        ``do_not_wait_for_lazy_connection``.

    Subscriptions
    -------------
    SUB_ACQ_DONE
        A one-time subscription indicating the requested trigger-based
        acquisition has completed.
    """

    SUB_ACQ_DONE = "acq_done"  # requested acquire

    # Over-ride in sub-classes to control the default contents of read and
    # configuration attrs lists.
    # For read attributes, if `None`, defaults to `self.component_names'
    _default_read_attrs = None

    # For configuration attributes, if `None`, defaults to `[]`
    _default_configuration_attrs = None

    # When instantiating a lazy signal upon first access, wait for it to
    # connect before returning control to the user
    lazy_wait_for_connection = True

    def __init__(
        self,
        prefix="",
        *,
        name,
        kind=None,
        read_attrs=None,
        configuration_attrs=None,
        parent=None,
        **kwargs,
    ):
        self._destroyed = False

        # Store EpicsSignal objects (only created once they are accessed)
        self._signals = {}

        # Copy the Device-defined signal kinds, for user modification
        self._component_kinds = self._component_kinds.copy()

        # Subscriptions to run or general methods necessary to call prior to
        # marking the Device as connected
        self._required_for_connection = self._required_for_connection.copy()

        self.prefix = prefix
        if self.component_names and prefix is None:
            raise ValueError("Must specify prefix if device signals are being " "used")

        super().__init__(name=name, parent=parent, kind=kind, **kwargs)

        # The logic of these if blocks is:
        # - If the user did not provide read_attrs, fall back on the default
        # specified by the class, which ultimately falls back to Device, if no
        # subclass overrides it. Either way, we now have a read_attrs.
        # - If it is set to the sentinel ALL_COMPONENTS, ignore whatever the
        # 'kind' settings are; just include everything. This is an escape catch
        # for getting what _default_read_attrs=None used to do before 'kind'
        # was implemented.
        # - If it is set to a list, ignore whatever the 'kind' settings are and
        # just include that list.
        # - If it is set to None, respect whatever the 'kind' settings of the
        # components are.

        # If any sub-Devices are to be removed from configuration_attrs and
        # read_attrs, we have to remove them from read_attrs first, or they
        # will not allow themselves to be removed from configuration_attrs.
        if read_attrs is None:
            read_attrs = self._default_read_attrs
        if read_attrs is ALL_COMPONENTS:
            read_attrs = self.component_names
        if read_attrs is not None:
            self.read_attrs = list(read_attrs)

        if configuration_attrs is None:
            configuration_attrs = self._default_configuration_attrs
        if configuration_attrs is ALL_COMPONENTS:
            configuration_attrs = self.component_names
        if configuration_attrs is not None:
            self.configuration_attrs = list(configuration_attrs)

        with do_not_wait_for_lazy_connection(self):
            # Instantiate non-lazy signals and lazy signals with subscriptions
            [
                getattr(self, attr)
                for attr, cpt in self._sig_attrs.items()
                if not cpt.lazy or cpt._subscriptions
            ]

    @classmethod
    def _initialize_device(cls):
        """Initializes the Device and all of its Components

        Initializes the following attributes from the Components::
            - _sig_attrs - dict of attribute name to Component
            - component_names - a list of attribute names used for components
            - _device_tuple - An auto-generated namedtuple based on all
              existing Components in the Device
            - _sub_devices - a list of attributes which hold a Device
            - _required_for_connection - a dictionary of object-to-description
              for additional things that block this from being reported as
              connected
        """

        for attr in DEVICE_INSTANCE_ATTRS:
            if attr in cls.__dict__:
                raise TypeError(
                    "The attribute name %r is reserved for "
                    "use by the Device class. Choose a different "
                    "name." % attr
                )

        # this is so that the _sig_attrs class attribute includes the sigattrs
        # from all of its class-inheritance-parents so we do not have to do
        # this look up everytime we look at it.
        base_devices = [
            base for base in reversed(cls.__bases__) if hasattr(base, "_sig_attrs")
        ]

        cls._sig_attrs = OrderedDict(
            (attr, cpt)
            for base in base_devices
            for attr, cpt in base._sig_attrs.items()
            if getattr(cls, attr) is not None
        )

        # map component classes to their attribute names from this class
        this_sig_attrs = {
            attr: cpt
            for attr, cpt in cls.__dict__.items()
            if isinstance(cpt, Component)
        }

        cls._sig_attrs.update(**this_sig_attrs)

        # Record the class-defined kinds - these can be updated on a
        # per-instance basis
        cls._component_kinds = {attr: cpt.kind for attr, cpt in cls._sig_attrs.items()}

        bad_attrs = set(cls._sig_attrs).intersection(DEVICE_RESERVED_ATTRS)
        if bad_attrs:
            raise TypeError(
                f"The attribute name(s) {bad_attrs} are part of"
                f" the bluesky interface and cannot be used as "
                f"component names. Choose a different name."
            )

        # List Signal attribute names.
        cls.component_names = tuple(cls._sig_attrs)

        # The namedtuple associated with the device
        cls._device_tuple = namedtuple(
            f"{cls.__name__}Tuple",
            [comp for comp in cls.component_names[:254] if not comp.startswith("_")],
        )

        # List the attributes that are Devices (not Signals).
        # This list is used by stage/unstage. Only Devices need to be staged.
        cls._sub_devices = [
            attr for attr, cpt in cls._sig_attrs.items() if cpt.is_device
        ]

        # All (obj, description) that may block the Device from being shown as
        # connected:
        cls._required_for_connection = dict(
            obj._required_for_connection
            for attr, obj in cls.__dict__.items()
            if getattr(obj, "_required_for_connection", False)
        )

    def __init_subclass__(cls, **kwargs):
        "This is called automatically in Python for all subclasses of Device"
        super().__init_subclass__(**kwargs)
        cls._initialize_device()

    @classmethod
    def walk_components(cls):
        """Walk all components in the Device hierarchy

        Yields
        ------
        ComponentWalk
            Where ancestors is all ancestors of the signal, including the
            top-level device `walk_components` was called on.
        """
        for attr, cpt in cls._sig_attrs.items():
            yield ComponentWalk(ancestors=(cls,), dotted_name=attr, item=cpt)
            if issubclass(cpt.cls, Device) or hasattr(cpt.cls, "walk_components"):
                sub_dev = cpt.cls
                for walk in sub_dev.walk_components():
                    ancestors = (cls,) + walk.ancestors
                    dotted_name = ".".join((attr, walk.dotted_name))
                    yield ComponentWalk(
                        ancestors=ancestors, dotted_name=dotted_name, item=walk.item
                    )

    def walk_signals(self, *, include_lazy=False):
        """Walk all signals in the Device hierarchy

        EXPERIMENTAL: This method is experimental, and there are tentative
        plans to change its API in a way that may not be backward-compatible.

        Parameters
        ----------
        include_lazy : bool, optional
            Include not-yet-instantiated lazy signals

        Yields
        ------
        ComponentWalk
            Where ancestors is all ancestors of the signal, including the
            top-level device `walk_signals` was called on.
        """
        for attr, cpt in self._sig_attrs.items():
            # 2 scenarios:
            #  - Always include non-lazy components
            #  - Include a lazy if already instantiated OR requested with
            #    include_lazy
            lazy_ok = cpt.lazy and (include_lazy or attr in self._signals)
            should_walk = not cpt.lazy or lazy_ok

            if not should_walk:
                continue

            sig = getattr(self, attr)
            if isinstance(sig, Device):
                for walk in sig.walk_signals(include_lazy=include_lazy):
                    ancestors = (self,) + walk.ancestors
                    dotted_name = ".".join((attr, walk.dotted_name))
                    yield ComponentWalk(
                        ancestors=ancestors, dotted_name=dotted_name, item=walk.item
                    )
            else:
                yield ComponentWalk(ancestors=(self,), dotted_name=attr, item=sig)

    @classmethod
    def walk_subdevice_classes(cls):
        """Walk all sub-Devices classes in the Device hierarchy

        Yields
        ------
        (dotted_name, subdevice_class)
        """
        for attr in cls._sub_devices:
            cpt = getattr(cls, attr)
            if cpt is None:
                # Subclasses can override this, making this None...
                continue

            yield (attr, cpt.cls)
            for sub_attr, sub_cls in cpt.cls.walk_subdevice_classes():
                yield (".".join((attr, sub_attr)), sub_cls)

    def walk_subdevices(self, *, include_lazy=False):
        """Walk all sub-Devices in the hierarchy

        EXPERIMENTAL: This method is experimental, and there are tentative
        plans to change its API in a way that may not be backward-compatible.

        Yields
        ------
        (dotted_name, subdevice_instance)
        """
        # TODO: Devices can be lazy, outside of original design intent; should
        # discuss this at some point
        cls = type(self)
        for attr in cls._sub_devices:
            cpt = getattr(cls, attr)
            lazy_ok = cpt.lazy and (include_lazy or attr in self._signals)
            should_walk = not cpt.lazy or lazy_ok

            if should_walk:
                dev = getattr(self, attr)
                yield (attr, dev)
                for sub_attr, sub_dev in dev.walk_subdevices(include_lazy=include_lazy):
                    yield (".".join((attr, sub_attr)), sub_dev)

    def destroy(self):
        "Disconnect and destroy all signals on the Device"
        self._destroyed = True
        exceptions = []
        for walk in self.walk_signals(include_lazy=False):
            sig = walk.item
            try:
                sig.destroy()
            except Exception as ex:
                ex.signal = sig
                ex.attr = walk.dotted_name
                exceptions.append(ex)

        if exceptions:
            msg = ", ".join(
                "{} ({})".format(ex.attr, ex.__class__.__name__) for ex in exceptions
            )
            raise ExceptionBundle(
                "Failed to disconnect all signals ({})".format(msg),
                exceptions=exceptions,
            )
        super().destroy()

    def _get_kind(self, name):
        """Get a Kind for a given Component

        If the Component is instantiated, it will be retrieved directly from
        that object.

        If the Component is lazy and not yet instantiated, the default value as
        specified by the Component class will be used.  This is stashed away in
        `_component_kinds`.
        """
        return (
            self._signals[name].kind
            if name in self._signals
            else self._component_kinds[name]
        )

    def _set_kind(self, name, kind):
        """Set the Kind for a given Component"""
        if name in self._signals:
            self._signals[name].kind = kind
        else:
            self._component_kinds[name] = kind

    def _get_components_of_kind(self, kind):
        "Get names of components that match a specific kind"
        for component_name in self.component_names:
            # this might be lazy and get the Cpt
            component_kind = self._get_kind(component_name)
            if kind & component_kind:
                yield component_name, getattr(self, component_name)

    def _validate_kind(self, val):
        val = super()._validate_kind(val)
        if Kind.normal & val:
            val |= Kind.config
        return val

    @property
    def read_attrs(self):
        return self.OphydAttrList(self, Kind.normal, Kind.hinted, "read_attrs")

    @read_attrs.setter
    def read_attrs(self, val):
        self.__set_kinds_according_to_list(val, Kind.normal, Kind.hinted, "read_attrs")

    @property
    def configuration_attrs(self):
        return self.OphydAttrList(self, Kind.config, Kind.config, "configuration_attrs")

    @configuration_attrs.setter
    def configuration_attrs(self, val):
        self.__set_kinds_according_to_list(
            val, Kind.config, Kind.config, "configuration_attrs"
        )

    def __set_kinds_according_to_list(
        self, master_list, set_kind, unset_kind, recurse_name
    ):
        master_list = set(master_list)
        component_names = set(self.component_names)

        # For all children of this class, update their kinds
        for name in component_names:
            kind = self._get_kind(name)
            kind = kind | set_kind if name in master_list else kind & ~unset_kind
            self._set_kind(name, kind)

        # Now look at everything else, presumably things with dots
        extra = master_list - component_names
        fail = set(c for c in extra if "." not in c)

        if fail:
            raise ValueError(
                f"You asked to add the components {fail} to {recurse_name} "
                f"on {self.name!r}, but there is no such child in "
                f"{self.component_names}."
            )

        group = itertools.groupby(
            ((child, rest) for child, _, rest in (c.partition(".") for c in extra)),
            lambda x: x[0],
        )

        # we are into grand-children, can not be lazy!
        for child, cf_list in group:
            cpt = getattr(self, child)
            cpt.kind |= set_kind
            setattr(cpt, recurse_name, [c[1] for c in cf_list])

    @property
    def signal_names(self):
        warnings.warn(
            "'signal_names' has been renamed 'component_names' for "
            "clarity because it may include a mixture of Signals "
            "and Devices -- any Components. This alias may be "
            "removed in a future release of ophyd.",
            stacklevel=2,
        )
        return self.component_names

    def summary(self):
        print(self._summary())

    def _summary(self):
        "Return a string summarizing the structure of the Device."
        read_attrs = self.read_attrs
        config_attrs = self.configuration_attrs
        used_attrs = set(read_attrs + config_attrs)
        extra_attrs = [a for a in self.component_names if a not in used_attrs]
        hints = getattr(self, "hints", {}).get("fields", [])

        def format_leaf(attr):
            cpt = getattr(self, attr)
            return f"{attr:<20} {type(cpt).__name__:<20}({cpt.name!r})"

        def format_hint(key):
            return "".join(("*" if key in hints else " ", key))

        categories = [
            ("data keys (* hints)", sorted(self.describe()), format_hint),
            ("read attrs", read_attrs, format_leaf),
            ("config keys", sorted(self.describe_configuration()), str),
            ("configuration attrs", config_attrs, format_leaf),
            ("unused attrs", extra_attrs, format_leaf),
        ]

        out = []
        for title, items, formatter in categories:
            out.append(title)
            out.append("-" * len(title))
            out.extend([formatter(s) for s in items])
            out.append("")

        return "\n".join(out)

    def wait_for_connection(self, all_signals=False, timeout=2.0):
        """Wait for signals to connect

        Parameters
        ----------
        all_signals : bool, optional
            Wait for all signals to connect (including lazy ones)
        timeout : float or None
            Overall timeout
        """
        signals = [walk.item for walk in self.walk_signals(include_lazy=all_signals)]

        pending_funcs = {
            dev: getattr(dev, "_required_for_connection", {})
            for name, dev in self.walk_subdevices(include_lazy=all_signals)
        }
        pending_funcs[self] = self._required_for_connection

        t0 = ttime.time()
        while timeout is None or (ttime.time() - t0) < timeout:
            connected = all(sig.connected for sig in signals)
            if connected and not any(pending_funcs.values()):
                return
            ttime.sleep(min((0.05, timeout / 10.0)))

        def get_name(sig):
            sig_name = f"{self.name}.{sig.dotted_name}"
            return f"{sig_name} ({sig.pvname})" if hasattr(sig, "pvname") else sig_name

        reasons = []
        unconnected = ", ".join(get_name(sig) for sig in signals if not sig.connected)
        if unconnected:
            reasons.append(f"Failed to connect to all signals: {unconnected}")
        if any(pending_funcs.values()):
            pending = ", ".join(
                description.format(device=dev)
                for dev, funcs in pending_funcs.items()
                for obj, description in funcs.items()
            )
            reasons.append(f"Pending operations: {pending}")
        raise TimeoutError("; ".join(reasons))

    def get_instantiated_signals(self, *, attr_prefix=None):
        """Yields all of the instantiated signals in a device hierarchy

        Parameters
        ----------
        attr_prefix : string, optional
            The attribute prefix. If None, defaults to self.name

        Yields
        ------
            (fully_qualified_attribute_name, signal_instance)
        """
        if attr_prefix is None:
            attr_prefix = self.name

        for attr, sig in self._signals.items():
            # fully qualified attribute name from top-level device
            full_attr = "{}.{}".format(attr_prefix, attr)
            if isinstance(sig, Device):
                yield from sig.get_instantiated_signals(attr_prefix=full_attr)
            else:
                yield full_attr, sig

    @property
    def connected(self):
        signals_connected = all(
            walk.item.connected for walk in self.walk_signals(include_lazy=False)
        )
        pending_funcs = any(
            getattr(item, "_required_for_connection", None)
            for name, item in self.walk_subdevices()
        )

        pending_funcs = pending_funcs or self._required_for_connection
        return signals_connected and not pending_funcs

    def __getattr__(self, name):
        """Get a component from a fully-qualified name"""
        if "." in name:
            return operator.attrgetter(name)(self)

        # Components will be instantiated through the descriptor mechanism in
        # the Component class, so anything reaching this point is an error.
        raise AttributeError(name)

    def _instantiate_component(self, attr):
        "Create a Component specifically for this Device"
        if self._destroyed:
            raise RuntimeError("Cannot instantiate new signals on a destroyed Device")

        try:
            # Initial access of signal
            cpt = self._sig_attrs[attr]
        except KeyError:
            raise RuntimeError(
                f"The Component {attr!r} exists at the Python level and "
                "has triggered the `_instantiate_component` "
                "code path on Device, but has not been registered with "
                "the Component management machinery in Device.  This may be due to "
                "using multiple inheritance with a mix-in class that defines "
                "a Component but does not inherent from Device."
            ) from None

        try:
            self._signals[attr] = cpt.create_component(self)
            sig = self._signals[attr]
            for event_type, functions in cpt._subscriptions.items():
                for func in functions:
                    method = getattr(self, func.__name__)
                    sig.subscribe(method, event_type=event_type, run=sig.connected)
        except AttributeError as ex:
            # Raise a different Exception, as AttributeError will be shadowed
            # during initial access
            raise RuntimeError(
                f"AttributeError while instantiating " f"component: {attr}"
            ) from ex

        return sig

    @doc_annotation_forwarder(BlueskyInterface)
    def read(self):
        res = super().read()

        for _, component in self._get_components_of_kind(Kind.normal):
            res.update(component.read())
        return res

    def read_configuration(self) -> OrderedDictType[str, Dict[str, Any]]:
        """Dictionary mapping names to value dicts with keys: value, timestamp

        To control which fields are included, change the Component kinds on the
        device, or modify the ``configuration_attrs`` list.
        """
        res = OrderedDict()

        for _, component in self._get_components_of_kind(Kind.config):
            res.update(component.read_configuration())
        return res

    @doc_annotation_forwarder(BlueskyInterface)
    def describe(self):
        res = super().describe()
        for _, component in self._get_components_of_kind(Kind.normal):
            res.update(component.describe())
        return res

    def describe_configuration(self) -> OrderedDictType[str, Dict[str, Any]]:
        """Provide schema & meta-data for :meth:`~BlueskyInterface.read_configuration`

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
        res = OrderedDict()
        for _, component in self._get_components_of_kind(Kind.config):
            res.update(component.describe_configuration())
        return res

    @property
    def hints(self):
        fields = []
        for _, component in self._get_components_of_kind(Kind.normal):
            c_hints = component.hints
            fields.extend(c_hints.get("fields", []))
        return {"fields": fields}

    @property
    def trigger_signals(self):
        names = [
            attr
            for attr, cpt in self._sig_attrs.items()
            if cpt.trigger_value is not None
        ]

        return [getattr(self, name) for name in names]

    def _done_acquiring(self, **kwargs):
        """Call when acquisition has completed."""
        self._run_subs(sub_type=self.SUB_ACQ_DONE, success=True, **kwargs)
        self._reset_sub(self.SUB_ACQ_DONE)

    @doc_annotation_forwarder(BlueskyInterface)
    def trigger(self):
        """Start acquisition"""
        signals = self.trigger_signals
        if len(signals) > 1:
            raise NotImplementedError(
                "More than one trigger signal is not " "currently supported"
            )
        status = DeviceStatus(self)
        if not signals:
            status.set_finished()
            return status

        (acq_signal,) = signals

        self.subscribe(status._finished, event_type=self.SUB_ACQ_DONE, run=False)

        def done_acquisition(**ignored_kwargs):
            # Keyword arguments are ignored here from the EpicsSignal
            # subscription, as the important part is that the put completion
            # has finished
            self._done_acquiring()

        acq_signal.put(1, wait=False, callback=done_acquisition)
        return status

    def stop(self, *, success=False):
        """Stop the Device and all (instantiated) subdevices"""
        exc_list = []

        for attr, dev in getattrs(self, self._sub_devices):
            if not dev.connected:
                self.log.debug(
                    "stop: device %s (%s) is not connected; " "skipping", attr, dev
                )
                continue

            try:
                dev.stop(success=success)
            except ExceptionBundle as ex:
                exc_list.extend(
                    [
                        ("{}.{}".format(attr, sub_attr), ex)
                        for sub_attr, ex in ex.exceptions.items()
                    ]
                )
            except Exception as ex:
                exc_list.append((attr, ex))
                self.log.exception("Device %s (%s) stop failed", attr, dev)

        if exc_list:
            exc_info = "\n".join(
                "{} raised {!r}".format(attr, ex) for attr, ex in exc_list
            )
            raise ExceptionBundle(
                "{} exception(s) were raised during stop: \n"
                "{}".format(len(exc_list), exc_info),
                exceptions=dict(exc_list),
            )

    def get(self, **kwargs):
        """Get the value of all components in the device

        Keyword arguments are passed onto each signal.get(). Components
        beginning with an underscore will not be included.
        """
        values = {}
        for attr in self.component_names:
            if not attr.startswith("_"):
                signal = getattr(self, attr)
                values[attr] = signal.get(**kwargs)

        return self._device_tuple(**values)

    def put(self, dev_t, **kwargs):
        """Put a value to all components of the device

        Keyword arguments are passed onto each signal.put()

        Parameters
        ----------
        dev_t : DeviceTuple or tuple
            The device tuple with the value(s) to put (see get_device_tuple)
        """
        if not isinstance(dev_t, self._device_tuple):
            try:
                dev_t = self._device_tuple(*dev_t)
            except TypeError as ex:
                raise ValueError(
                    "{}\n\tDevice tuple fields: {}"
                    "".format(ex, self._device_tuple._fields)
                )

        for attr in self.component_names:
            value = getattr(dev_t, attr)
            signal = getattr(self, attr)
            signal.put(value, **kwargs)

    @classmethod
    def get_device_tuple(cls):
        """The device tuple type associated with an Device class

        This is a tuple representing the full state of all components and
        dynamic device sub-components.
        """
        return cls._device_tuple

    def configure(self, d: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Configure the device for something during a run

        This default implementation allows the user to change any of the
        `configuration_attrs`. Subclasses might override this to perform
        additional input validation, cleanup, etc.

        Parameters
        ----------
        d : dict
            The configuration dictionary. To specify the order that
            the changes should be made, use an OrderedDict.

        Returns
        -------
        (old, new) tuple of dictionaries
        Where old and new are pre- and post-configure configuration states.
        """
        old = self.read_configuration()
        for key, val in d.items():
            if key not in self.configuration_attrs:
                # a little extra checking for a more specific error msg
                if key not in self.component_names:
                    raise ValueError("There is no signal named %s" % key)
                else:
                    raise ValueError(
                        "%s is not one of the "
                        "configuration_fields, so it cannot be "
                        "changed using configure" % key
                    )
            getattr(self, key).set(val).wait()
        new = self.read_configuration()
        return old, new

    def _repr_info(self):
        yield ("prefix", self.prefix)
        yield from super()._repr_info()

        yield ("read_attrs", self.read_attrs)
        yield ("configuration_attrs", self.configuration_attrs)

    class OphydAttrList(MutableSequence):
        """list proxy to migrate away from Device.read_attrs and Device.config_attrs"""

        def __init__(self, device, kind, remove_kind, recurse_key):
            self._kind = kind
            self._remove_kind = remove_kind
            self._parent = device
            self._recurse_key = recurse_key

        def __internal_list(self):
            def per_component(name, component):
                yield name
                for v in getattr(component, self._recurse_key, []):
                    yield ".".join([name, v])

            out = (
                per_component(name, component)
                for name, component in self._parent._get_components_of_kind(self._kind)
            )

            return list(itertools.chain.from_iterable(out))

        def __getitem__(self, key):
            return self.__internal_list()[key]

        def __setitem__(self, key, val):
            raise NotImplementedError

        def __delitem__(self, key):
            to_delete = self.__internal_list()[key]
            if not isinstance(key, slice):
                to_delete = [to_delete]

            for attr in to_delete:
                item_kind = self._parent._get_kind(attr)
                item_kind &= ~self._remove_kind

        def __len__(self):
            return len(self.__internal_list())

        def insert(self, index, object):
            getattr(self._parent, object).kind |= self._kind

        def remove(self, value):
            kind = self._parent._get_kind(value)
            kind &= ~self._remove_kind

        def __contains__(self, value):
            return value in self.__internal_list()

        def __iter__(self):
            yield from self.__internal_list()

        def __eq__(self, other):
            return list(self) == other

        def __repr__(self):
            return repr(list(self))

        def __add__(self, other):
            return list(self) + list(other)

        def __radd__(self, other):
            return list(self) + list(other)


# Device can be used on its own in trivial cases; ensure that it is ready
# out-of-the-box for this scenario.
if not hasattr(Device, "_sig_attrs"):
    Device._initialize_device()


@contextlib.contextmanager
def kind_context(kind):
    yield functools.partial(Component, kind=kind)


def create_device_from_components(
    name,
    *,
    docstring=None,
    default_read_attrs=None,
    default_configuration_attrs=None,
    base_class=Device,
    class_kwargs=None,
    **components,
):
    """Factory function to make a Device from Components

    Parameters
    ----------
    name : str
        Class name to create
    docstring : str, optional
        Docstring to attach to the class
    default_read_attrs : list, optional
        Outside of Kind, control the default read_attrs list.
        Defaults to all `component_names'
    default_configuration_attrs : list, optional
        Outside of Kind, control the default configuration_attrs list.
        Defaults to []
    base_class : Device or sub-class, optional
        Class to inherit from, defaults to Device
    **components : dict
        Keyword arguments are used to map component attribute names to
        Components.

    Returns
    -------
    cls : Device
        Newly generated Device class
    """
    if docstring is None:
        docstring = f"{name} Device"

    if not isinstance(base_class, tuple):
        base_class = (base_class,)

    if class_kwargs is None:
        class_kwargs = {}

    clsdict = OrderedDict(
        __doc__=docstring,
        _default_read_attrs=default_read_attrs,
        _default_configuration_attrs=default_configuration_attrs,
    )

    for attr, component in components.items():
        if not isinstance(component, Component):
            raise ValueError(
                f"Attribute {attr} is not a Component. "
                f"It is of type {type(component).__name__}"
            )

        clsdict[attr] = component

    return type(name, base_class, clsdict, **class_kwargs)


def required_for_connection(func=None, *, description=None, device=None):
    """Require that a method be called prior to marking a Device as connected

    This is a decorator that wraps the given function.  When the function is
    called for the first time, the Device instance is informed that this
    operation is no longer pending.

    Parameters
    ----------
    func : callable, optional
        Function to wrap
    description : str, optional
        Optional string description to be shown when `wait_for_connection`
        fails.  Can include {device} which will be substituted when presented
        to the user.
    """

    if func is None:
        if description is None:
            raise ValueError("Either func or description must be specified")
        return functools.partial(required_for_connection, description=description)

    if description is None:
        if hasattr(func, "_subscriptions"):
            description = ", ".join(
                f"{{device}}.{func.__name__}[{event_type}] subscription"
                for cpt, event_type in func._subscriptions
            )
        else:
            description = f"{func.__name__} call"

    key = inspect.unwrap(func)

    if device is not None:
        # With the Device specified, this can only be done post-init, with the
        # required_for_connection flag set prior to returning.
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            try:
                ret = func(*args, **kwargs)
            finally:
                device._required_for_connection.pop(key, None)
            return ret

        # Add a specific requirement
        device._required_for_connection[func] = description
    else:
        # With the Device unspecified, this can only be used as a decorator on
        # unbound methods.
        @functools.wraps(func)
        def wrapped(self, *args, **kwargs):
            try:
                ret = func(self, *args, **kwargs)
            finally:
                self._required_for_connection.pop(key, None)
            return ret

    wrapped._required_for_connection = (key, description)
    return wrapped


def _wait_for_connection_context(value, doc):
    @contextlib.contextmanager
    def wrapped(dev):

        orig = dev.lazy_wait_for_connection
        dev.lazy_wait_for_connection = value
        try:
            yield
        finally:
            dev.lazy_wait_for_connection = orig

    wrapped.__doc__ = f"""Context manager which changes the wait behavior of lazy signal instantiation

By default, upon instantiation of a lazy signal, `wait_for_connection`
is called.  While a common source of confusion, this is done
intentionally and for good reason: without this functionality in place,
any new lazy signal will generally take a finite amount of time to
connect. This then requires that the user manually call
`wait_for_connection` each time before using the signal.

In certain cases, it can be desirable to override this behavior. For
instance, when instantiating multiple lazy signals or instantiating a
signal just so that a subscription can be added.

{doc}

Parameters
----------
dev : Device
    The device to temporarily change
"""
    return wrapped


wait_for_lazy_connection = _wait_for_connection_context(
    True, doc="Wait for lazy signals to connect post-instantiation."
)
do_not_wait_for_lazy_connection = _wait_for_connection_context(
    False, doc="Do not wait for lazy signals to connect post-instantiation."
)
