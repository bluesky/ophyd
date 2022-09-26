import functools
import time
import weakref
from enum import IntFlag
from itertools import count
from logging import LoggerAdapter, getLogger
from typing import ClassVar, FrozenSet

from .log import control_layer_logger


def select_version(cls, version):
    """Select closest compatible version to requested version

    Compatible is defined as ``class_version <= requested_version``
    as defined by the types used to denote the versions.

    Parameters
    ----------
    cls : type
        The base class to find a version of

    version : any
        Must be the same type as used to define the class versions.

    """
    all_versions = cls._class_info_["versions"]
    matched_version = max(ver for ver in all_versions if ver <= version)
    return all_versions[matched_version]


try:
    from enum import KEEP

    class IFBase(IntFlag, boundary=KEEP):
        ...

except ImportError:

    IFBase = IntFlag


class Kind(IFBase):
    """
    This is used in the .kind attribute of all OphydObj (Signals, Devices).

    A Device examines its components' .kind atttribute to decide whether to
    traverse it in read(), read_configuration(), or neither. Additionally, if
    decides whether to include its name in `hints['fields']`.
    """

    omitted = 0b000
    normal = 0b001
    config = 0b010
    hinted = 0b101  # Notice that bool(hinted & normal) is True.


class UnknownSubscription(KeyError):
    "Subclass of KeyError.  Raised for unknown event type"
    ...


def register_instances_keyed_on_name(fail_if_late=False):
    """Register OphydObj instances in a WeakValueDictionary keyed on name.

    Be advised that ophyd does not require 'name' to be unique and is
    configurable by the user at run-time so this should
    not be relied on unless name uniqueness is enforced by other means.

    Parameters
    ----------
    fail_if_late : boolean
        If True, verify that OphydObj has not yet been instantiated and raise
        ``RuntimeError`` if it has, as a way of verify that no instances will
        be "missed" by this registry. False by default.

    Returns
    -------
    WeakValueDictionary
    """
    weak_dict = weakref.WeakValueDictionary()

    def register(instance):
        weak_dict[instance.name] = instance

    OphydObject.add_instantiation_callback(register, fail_if_late)
    return weak_dict


def register_instances_in_weakset(fail_if_late=False):
    """Register OphydObj instances in a WeakSet.

    Be advised that OphydObj may not always be hashable.

    Parameters
    ----------
    fail_if_late : boolean
        If True, verify that OphydObj has not yet been instantiated and raise
        ``RuntimeError`` if it has, as a way of verify that no instances will
        be "missed" by this registry. False by default.

    Returns
    -------
    WeakSet
    """
    weak_set = weakref.WeakSet()

    def register(instance):
        weak_set.add(instance)

    OphydObject.add_instantiation_callback(register, fail_if_late)
    return weak_set


class OphydObject:
    """The base class for all objects in Ophyd

    Handles:

      * Subscription/callback mechanism

    Parameters
    ----------
    name : str, optional
        The name of the object.
    attr_name : str, optional
        The attr name on it's parent (if it has one)
        ex ``getattr(self.parent, self.attr_name) is self``
    parent : parent, optional
        The object's parent, if it exists in a hierarchy
    kind : a member of the :class:`~ophydobj.Kind` :class:`~enum.IntEnum`
        (or equivalent integer), optional
        Default is ``Kind.normal``. See :class:`~ophydobj.Kind` for options.

    Attributes
    ----------
    name
    """

    # Any callables appended to this mutable class variable will be notified
    # one time when a new instance of OphydObj is instantiated. See
    # OphydObject.add_instantiation_callback().
    __instantiation_callbacks = []
    _default_sub = None
    # This is set to True when the first OphydObj is instantiated. This may be
    # of interest to code that adds something to instantiation_callbacks, which
    # may want to know whether it has already "missed" any instances.
    __any_instantiated = False
    subscriptions: ClassVar[FrozenSet[str]] = frozenset()

    def __init__(self, *, name=None, attr_name="", parent=None, labels=None, kind=None):
        if labels is None:
            labels = set()
        self._ophyd_labels_ = set(labels)
        if kind is None:
            kind = Kind.normal
        self.kind = kind

        super().__init__()

        # base name and ref to parent, these go with properties
        if name is None:
            name = ""
        self._attr_name = attr_name
        if not isinstance(name, str):
            raise ValueError("name must be a string.")
        self._name = name
        self._parent = parent

        # dictionary of wrapped callbacks
        self._callbacks = {k: {} for k in self.subscriptions}
        # this is to maintain api on clear_sub
        self._unwrapped_callbacks = {k: {} for k in self.subscriptions}
        # map cid -> back to which event it is in
        self._cid_to_event_mapping = dict()
        # cache of last inputs to _run_subs, the semi-private way
        # to trigger the callbacks for a given subscription to be run
        self._args_cache = {k: None for k in self.subscriptions}
        # count of subscriptions we have handed out, used to give unique ids
        self._cb_count = count()
        self.log = LoggerAdapter(
            getLogger("ophyd.objects"), {"ophyd_object_name": name}
        )
        self.control_layer_log = LoggerAdapter(
            control_layer_logger, {"ophyd_object_name": name}
        )

        if not self.__any_instantiated:
            self.log.debug("first instance of OphydObject: id=%s", id(self))
            OphydObject._mark_as_instantiated()
        self.__register_instance(self)

    @classmethod
    def _mark_as_instantiated(cls):
        cls.__any_instantiated = True

    @classmethod
    def add_instantiation_callback(cls, callback, fail_if_late=False):
        """
        Register a callback which will receive each OphydObject instance.

        Parameters
        ----------
        callback : callable
            Expected signature: ``f(ophydobj_instance)``
        fail_if_late : boolean
            If True, verify that OphydObj has not yet been instantiated and raise
            ``RuntimeError`` if it has, as a way of verify that no instances will
            be "missed" by this registry. False by default.
        """
        if fail_if_late and OphydObject.__any_instantiated:
            raise RuntimeError(
                "OphydObject has already been instantiated at least once, and "
                "this callback will not be notified of those instances that "
                "have already been created. If that is acceptable for this "
                "application, set fail_if_false=False."
            )
        # This is a class variable.
        cls.__instantiation_callbacks.append(callback)

    @classmethod
    def __register_instance(cls, instance):
        """
        Notify the callbacks in OphydObject.instantiation_callbacks of an instance.
        """
        for callback in cls.__instantiation_callbacks:
            callback(instance)

    def __init_subclass__(
        cls, version=None, version_of=None, version_type=None, **kwargs
    ):
        "This is called automatically in Python for all subclasses of OphydObject"
        super().__init_subclass__(**kwargs)

        cls.subscriptions = frozenset(
            {
                getattr(cls, key)
                for key in dir(cls)
                if key.startswith("SUB") or key.startswith("_SUB")
            }
        )

        if version is None:
            if version_of is not None:
                raise RuntimeError(
                    "Must specify a version if `version_of` " "is specified"
                )
            if version_type is None:
                return
            # Allow specification of version_type without specifying a version,
            # for use in a base class

            cls._class_info_ = dict(
                versions={},
                version=None,
                version_type=version_type,
                version_of=version_of,
            )
            return

        if version_of is None:
            versions = {}
            version_of = cls
        else:
            versions = version_of._class_info_["versions"]
            if version_type is None:
                version_type = version_of._class_info_["version_type"]

            elif version_type != version_of._class_info_["version_type"]:
                raise RuntimeError(
                    "version_type with in a family must be consistent, "
                    f"you passed in {version_type}, to {cls.__name__} "
                    f"but {version_of.__name__} has version_type "
                    f"{version_of._class_info_['version_type']}"
                )

            if not issubclass(cls, version_of):
                raise RuntimeError(
                    f"Versions are only valid for classes in the same "
                    f"hierarchy. {cls.__name__} is not a subclass of "
                    f"{version_of.__name__}."
                )

        if versions is not None and version in versions:
            getLogger("ophyd.object").warning(
                "Redefining %r version %s: old=%r new=%r",
                version_of,
                version,
                versions[version],
                cls,
            )

        versions[version] = cls

        cls._class_info_ = dict(
            versions=versions,
            version=version,
            version_type=version_type,
            version_of=version_of,
        )

    def _validate_kind(self, val):
        if isinstance(val, str):
            return Kind[val.lower()]
        return Kind(val)

    @property
    def kind(self):
        return self._kind

    @kind.setter
    def kind(self, val):
        self._kind = self._validate_kind(val)

    @property
    def dotted_name(self) -> str:
        """Return the dotted name"""
        names = []
        obj = self
        while obj.parent is not None:
            names.append(obj.attr_name)
            obj = obj.parent
        return ".".join(names[::-1])

    @property
    def name(self):
        """name of the device"""
        return self._name

    @name.setter
    def name(self, name):
        self._name = name

    @property
    def attr_name(self):
        return self._attr_name

    @property
    def connected(self):
        """If the device is connected.

        Subclasses should override this"""
        return True

    def destroy(self):
        """Disconnect the object from the underlying control layer"""
        self.unsubscribe_all()

    @property
    def parent(self):
        """The parent of the ophyd object.

        If at the top of its hierarchy, `parent` will be None
        """
        return self._parent

    @property
    def root(self):
        "Walk parents to find ultimate ancestor (parent's parent...)."
        root = self
        while True:
            if root.parent is None:
                return root
            root = root.parent

    @property
    def report(self):
        """A report on the object."""
        return {}

    @property
    def event_types(self):
        """Events that can be subscribed to via ``obj.subscribe``"""
        return tuple(self.subscriptions)

    def _run_subs(self, *args, sub_type, **kwargs):
        """Run a set of subscription callbacks

        Only the kwarg ``sub_type`` is required, indicating
        the type of callback to perform. All other positional arguments
        and kwargs are passed directly to the callback function.

        The host object will be injected into kwargs as 'obj' unless that key
        already exists.

        If the ``timestamp`` is None, then it will be replaced by the current
        time.

        No exceptions are raised if the callback functions fail.
        """
        if sub_type not in self.subscriptions:
            raise UnknownSubscription(
                "Unknown subscription {!r}, must be one of {!r}".format(
                    sub_type, self.subscriptions
                )
            )

        kwargs["sub_type"] = sub_type
        # Guarantee that the object will be in the kwargs
        kwargs.setdefault("obj", self)

        # And if a timestamp key exists, but isn't filled -- supply it with
        # a new timestamp
        if "timestamp" in kwargs and kwargs["timestamp"] is None:
            kwargs["timestamp"] = time.time()

        # Shallow-copy the callback arguments for replaying the
        # callback at a later time (e.g., when a new subscription is made)
        self._args_cache[sub_type] = (tuple(args), dict(kwargs))

        for cb in list(self._callbacks[sub_type].values()):
            cb(*args, **kwargs)

    def subscribe(self, callback, event_type=None, run=True):
        """Subscribe to events this event_type generates.

        The callback will be called as ``cb(*args, **kwargs)`` with
        the values passed to `_run_subs` with the following additional keys:

           sub_type : the string value of the event_type
           obj : the host object, added if 'obj' not already in kwargs

        if the key 'timestamp' is in kwargs _and_ is None, then it will
        be replaced with the current time before running the callback.

        The ``*args``, ``**kwargs`` passed to _run_subs will be cached as
        shallow copies, be aware of passing in mutable data.

        .. warning::

           If the callback raises any exceptions when run they will be
           silently ignored.

        Parameters
        ----------
        callback : callable
            A callable function (that takes kwargs) to be run when the event is
            generated.  The expected signature is ::

              def cb(*args, obj: OphydObject, sub_type: str, **kwargs) -> None:

            The exact args/kwargs passed are whatever are passed to
            ``_run_subs``
        event_type : str, optional
            The name of the event to subscribe to (if None, defaults to
            the default sub for the instance - obj._default_sub)

            This maps to the ``sub_type`` kwargs in `_run_subs`
        run : bool, optional
            Run the callback now

        See Also
        --------
        clear_sub, _run_subs

        Returns
        -------
        cid : int
            id of callback, can be passed to `unsubscribe` to remove the
            callback

        """
        if not callable(callback):
            raise ValueError("callback must be callable")
        # do default event type
        if event_type is None:
            # warnings.warn("Please specify which call back you wish to "
            #               "attach to defaulting to {}"
            #               .format(self._default_sub), stacklevel=2)
            event_type = self._default_sub

        if event_type is None:
            raise ValueError(
                "Subscription type not set and object {} of class"
                " {} has no default subscription set"
                "".format(self.name, self.__class__.__name__)
            )

        # check that this is a valid event type
        if event_type not in self.subscriptions:
            raise UnknownSubscription(
                "Unknown subscription {!r}, must be one of {!r}".format(
                    event_type, self.subscriptions
                )
            )

        # wrapper for callback to snarf exceptions
        def wrap_cb(cb):
            @functools.wraps(cb)
            def inner(*args, **kwargs):
                try:
                    cb(*args, **kwargs)
                except Exception:
                    sub_type = kwargs["sub_type"]
                    self.log.exception(
                        "Subscription %s callback exception (%s)", sub_type, self
                    )

            return inner

        # get next cid
        cid = next(self._cb_count)
        wrapped = wrap_cb(callback)
        self._unwrapped_callbacks[event_type][cid] = callback
        self._callbacks[event_type][cid] = wrapped
        self._cid_to_event_mapping[cid] = event_type

        if run:
            cached = self._args_cache[event_type]
            if cached is not None:
                args, kwargs = cached
                wrapped(*args, **kwargs)

        return cid

    def _reset_sub(self, event_type):
        """Remove all subscriptions in an event type"""
        self._callbacks[event_type].clear()
        self._unwrapped_callbacks[event_type].clear()

    def clear_sub(self, cb, event_type=None):
        """Remove a subscription, given the original callback function

        See also :meth:`subscribe`, :meth:`unsubscribe`

        Parameters
        ----------
        cb : callable
            The callback
        event_type : str, optional
            The event to unsubscribe from (if None, removes it from all event
            types)
        """
        if event_type is None:
            event_types = self.event_types
        else:
            event_types = [event_type]
        cid_list = []
        for et in event_types:
            for cid, target in self._unwrapped_callbacks[et].items():
                if cb == target:
                    cid_list.append(cid)
        for cid in cid_list:
            self.unsubscribe(cid)

    def unsubscribe(self, cid):
        """Remove a subscription

        See also :meth:`subscribe`, :meth:`clear_sub`

        Parameters
        ----------
        cid : int
           token return by :meth:`subscribe`
        """
        ev_type = self._cid_to_event_mapping.pop(cid, None)
        if ev_type is None:
            return
        del self._unwrapped_callbacks[ev_type][cid]
        del self._callbacks[ev_type][cid]

    def unsubscribe_all(self):
        for ev_type in self._callbacks:
            self._reset_sub(ev_type)

    def check_value(self, value, **kwargs):
        """Check if the value is valid for this object

        This function does no normalization, but may raise if the
        value is invalid.

        Raises
        ------
        ValueError
        """
        pass

    def __repr__(self):
        info = self._repr_info()
        info = ", ".join("{}={!r}".format(key, value) for key, value in info)
        return "{}({})".format(self.__class__.__name__, info)

    def _repr_info(self):
        "Yields pairs of (key, value) to generate the object repr"
        if self.name is not None:
            yield ("name", self.name)

        if self._parent is not None:
            yield ("parent", self.parent.name)

    def __copy__(self):
        """Copy the ophyd object

        Shallow copying ophyd objects uses the repr information from the
        _repr_info method to create a new object.
        """
        kwargs = dict(self._repr_info())
        return self.__class__(**kwargs)

    def __getnewargs_ex__(self):
        """Used by pickle to serialize an ophyd object

        Returns
        -------
        (args, kwargs)
            Arguments to be passed to __init__, necessary to recreate this
            object
        """
        kwargs = dict(self._repr_info())
        return ((), kwargs)
