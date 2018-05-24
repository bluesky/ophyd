import collections
import contextlib
import functools
import time as ttime
import logging
import textwrap
from enum import Enum
from collections import (OrderedDict, namedtuple)
import warnings

from .ophydobj import OphydObject, Kind
from .status import DeviceStatus, StatusBase
from .utils import (ExceptionBundle, set_and_wait, RedundantStaging,
                    doc_annotation_forwarder)

from typing import Dict, List, Any, TypeVar, Tuple
from types import SimpleNamespace
from collections.abc import MutableSequence
from itertools import groupby

A, B = TypeVar('A'), TypeVar('B')
ALL_COMPONENTS = object()


class OrderedDictType(Dict[A, B]):
    ...


logger = logging.getLogger(__name__)


class Staged(Enum):
    """Three-state switch"""
    yes = 'yes'
    no = 'no'
    partially = 'partially'


class Component:
    '''A descriptor representing a device component (or signal)

    Unrecognized keyword arguments will be passed directly to the component
    class initializer.

    Parameters
    ----------
    cls : class
        Class of signal to create.  The required signature of
        `cls.__init__` is (if `suffix` is given)::

            def __init__(self, pv_name, parent=None, **kwargs):

        or (if suffix is None) ::

            def __init__(self, parent=None, **kwargs):

        The class may have a `wait_for_connection()` which is called
        during the component instance creation.

    suffix : str, optional
        The PV suffix, which gets appended onto ``parent.prefix`` to
        generate the final PV that the instance component will bind to.
        Also see ``add_prefix``

    lazy : bool, optional
        Lazily instantiate the signal. If ``False``, the signal will be
        instantiated upon component instantiation

    trigger_value : any, optional
        Mark as a signal to be set on trigger. The value is sent to the signal
        at trigger time.

    add_prefix : sequence, optional
        Keys in the kwargs to prefix with the Device PV prefix during
        creation of the component instance.
        Defaults to ``('suffix', 'write_pv', )``

    doc : str, optional
        string to attach to component DvcClass.component.__doc__
    '''

    def __init__(self, cls, suffix=None, *, lazy=False, trigger_value=None,
                 add_prefix=None, doc=None, kind=Kind.normal, **kwargs):
        self.attr = None  # attr is set later by the device when known
        self.cls = cls
        self.kwargs = kwargs
        self.lazy = lazy
        self.suffix = suffix
        self.doc = doc
        self.trigger_value = trigger_value  # TODO discuss
        self.kind = _ensure_kind(kind)
        if add_prefix is None:
            add_prefix = ('suffix', 'write_pv')
        self.add_prefix = tuple(add_prefix)

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
            return '{prefix}{suffix}'.format(prefix=instance.prefix,
                                             suffix=suffix)
        return suffix

    def create_component(self, instance):
        '''Create a component for the instance'''
        kwargs = self.kwargs.copy()
        kwargs['name'] = '{}_{}'.format(instance.name, self.attr)
        kwargs['kind'] = instance._initial_state[self.attr].kind

        for kw, val in list(kwargs.items()):
            kwargs[kw] = self.maybe_add_prefix(instance, kw, val)

        if (isinstance(self.cls, type) and  # is a class
                issubclass(self.cls, DynamicDeviceComponent)):
            cpt_inst = self.cls(self.suffix).create_component(self)

        elif self.suffix is not None:
            pv_name = self.maybe_add_prefix(instance, 'suffix', self.suffix)
            cpt_inst = self.cls(pv_name, parent=instance, **kwargs)
        else:
            cpt_inst = self.cls(parent=instance, **kwargs)

        if self.lazy and hasattr(self.cls, 'wait_for_connection'):
            cpt_inst.wait_for_connection()

        return cpt_inst

    def make_docstring(self, parent_class):
        if self.doc is not None:
            return self.doc

        doc = ['{} attribute'.format(self.__class__.__name__),
               '::',
               '',
               ]

        doc.append(textwrap.indent(repr(self), prefix=' ' * 4))
        doc.append('')
        return '\n'.join(doc)

    def __repr__(self):
        kw_str = ', '.join('{}={!r}'.format(k, v)
                           for k, v in self.kwargs.items())
        if self.suffix is not None:
            suffix_str = '{!r}'.format(self.suffix)
            if self.kwargs:
                suffix_str += ', '
        else:
            suffix_str = ''

        if suffix_str or kw_str:
            arg_str = ', {}{}'.format(suffix_str, kw_str)
        else:
            arg_str = ''
        arg_str += ', kind={}'.format(self.kind)

        return ('{self.__class__.__name__}({self.cls.__name__}{arg_str})'
                ''.format(self=self, arg_str=arg_str))

    __str__ = __repr__

    def __get__(self, instance, owner):
        if instance is None:
            return self

        if self.attr not in instance._signals:
            instance._signals[self.attr] = self.create_component(instance)

        return instance._signals[self.attr]

    def __set__(self, instance, owner):
        raise RuntimeError('Use .put()')


class FormattedComponent(Component):
    '''A Component which takes a dynamic format string

    This differs from Component in that the parent prefix is not automatically
    added onto the Component suffix. Additionally, `str.format()` style strings
    are accepted, allowing access to Device instance attributes:

    >>> from ophyd import (Component as C, FormattedComponent as FC)
    >>> class MyDevice(Device):
    ...     # A normal component, where 'suffix' is added to prefix verbatim
    ...     cpt = C(EpicsSignal, 'suffix')
    ...     # A formatted component, where 'self' refers to the Device instance
    ...     ch = FC(EpicsSignal, '{self.prefix}{self._ch_name}')
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
    '''

    def maybe_add_prefix(self, instance, kw, suffix):
        if kw not in self.add_prefix:
            return suffix

        return suffix.format(self=instance)


class DynamicDeviceComponent:
    '''An Device component that dynamically creates a OphyDevice

    Parameters
    ----------
    defn : OrderedDict
        The definition of all attributes to be created, in the form of::

            defn['attribute_name'] = (SignalClass, pv_suffix, keyword_arg_dict)

        This will create an attribute on the sub-device of type `SignalClass`,
        with a suffix of pv_suffix, which looks something like this::

            parent.attribute_name = SignalClass(pv_suffix, **keyword_arg_dict)

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
    '''

    def __init__(self, defn, *, clsname=None, doc=None, kind=Kind.normal,
                 default_read_attrs=None, default_configuration_attrs=None):
        self.defn = defn
        self.clsname = clsname
        self.attr = None  # attr is set later by the device when known
        self.lazy = False
        self.doc = doc
        if isinstance(default_read_attrs, collections.Iterable):
            default_read_attrs = tuple(default_read_attrs)
        if isinstance(default_configuration_attrs, collections.Iterable):
            default_configuration_attrs = tuple(default_configuration_attrs)
        self.default_read_attrs = default_read_attrs
        self.default_configuration_attrs = default_configuration_attrs
        self.kind = _ensure_kind(kind)

        # TODO: component compatibility
        self.trigger_value = None
        self.attrs = list(defn.keys())

    def make_docstring(self, parent_class):
        if self.doc is not None:
            return self.doc

        doc = ['{} comprised of'.format(self.__class__.__name__),
               '::',
               '',
               ]

        doc.append(textwrap.indent(repr(self), prefix=' ' * 4))
        doc.append('')
        return '\n'.join(doc)

    def __repr__(self):
        doc = []
        for attr, (cls, suffix, kwargs) in self.defn.items():
            kw_str = ', '.join('{}={!r}'.format(k, v)
                               for k, v in kwargs.items())
            if suffix is not None:
                suffix_str = '{!r}'.format(suffix)
                if kwargs:
                    suffix_str += ', '
            else:
                suffix_str = ''

            if suffix_str or kw_str:
                arg_str = ', {}{}'.format(suffix_str, kw_str)
            else:
                arg_str = ''

            doc.append('{attr} = Component({cls.__name__}{arg_str})'
                       ''.format(attr=attr, cls=cls, arg_str=arg_str))

        return '\n'.join(doc)

    def create_attr(self, attr_name):
        cls, suffix, kwargs = self.defn[attr_name]
        inst = Component(cls, suffix, **kwargs)
        inst.attr = attr_name
        return inst

    def create_component(self, instance):
        '''Create a component for the instance'''
        clsname = self.clsname
        if clsname is None:
            # make up a class name based on the instance's class name
            clsname = ''.join((instance.__class__.__name__,
                               self.attr.capitalize()))

            # TODO: and if the attribute has any underscores, convert that to
            #       camelcase

        docstring = self.doc
        if docstring is None:
            docstring = '{} sub-device'.format(clsname)

        clsdict = OrderedDict(
            __doc__=docstring,
            _default_read_attrs=self.default_read_attrs,
            _default_configuration_attrs=self.default_configuration_attrs
        )

        for attr in self.defn.keys():
            clsdict[attr] = self.create_attr(attr)

        cls = type(clsname, (Device, ), clsdict)
        return cls(instance.prefix,
                   name='{}_{}'.format(instance.name, self.attr),
                   parent=instance,
                   kind=instance._initial_state[self.attr].kind)

    def __get__(self, instance, owner):
        if instance is None:
            return self

        if self.attr not in instance._signals:
            instance._signals[self.attr] = self.create_component(instance)

        return instance._signals[self.attr]

    def __set__(self, instance, owner):
        raise RuntimeError('Use .put()')


class ComponentMeta(type):
    '''Creates attributes for Components by inspecting class definition'''

    @classmethod
    def __prepare__(self, name, bases):
        '''Prepare allows the class attribute dictionary to be ordered as
        defined by the user'''
        return OrderedDict()

    def __new__(cls, name, bases, clsdict):
        clsobj = super().__new__(cls, name, bases, clsdict)

        # This attrs are defined at instanitation time and must not
        # collide with class attributes.
        INSTANCE_ATTRS = ['name', 'parent', 'component_names', '_signals',
                          '_sig_attrs',
                          '_sub_devices']
        # These attributes are part of the bluesky interface and cannot be
        # used as component names.
        RESERVED_ATTRS = ['read', 'describe', 'trigger',
                          'configure', 'read_configuration',
                          'describe_configuration', 'describe_collect',
                          'set', 'stage', 'unstage', 'pause', 'resume',
                          'kickoff', 'complete', 'collect', 'position', 'stop',
                          # from OphydObject
                          'subscribe', 'clear_sub', 'event_types', 'root',
                          # for back-compat
                          'signal_names']
        for attr in INSTANCE_ATTRS:
            if attr in clsdict:
                raise TypeError("The attribute name %r is reserved for "
                                "use by the Device class. Choose a different "
                                "name." % attr)

        clsobj._sig_attrs = OrderedDict()
        # this is so that the _sig_attrs class attribute includes the
        # sigattrs from all of it's class-inheritance-parents so we do
        # not have to do this look up everytime we look at it.
        for base in reversed(bases):
            if not hasattr(base, '_sig_attrs'):
                continue

            for attr, cpt in base._sig_attrs.items():
                clsobj._sig_attrs[attr] = cpt

        # map component classes to their attribute names from this class
        for attr, value in clsdict.items():
            if isinstance(value, (Component, DynamicDeviceComponent)):
                if attr in RESERVED_ATTRS:
                    raise TypeError("The attribute name %r is part of the "
                                    "bluesky interface and cannot be used as "
                                    "the name of a component. Choose a "
                                    "different name." % attr)
                clsobj._sig_attrs[attr] = value

        for cpt_attr, cpt in clsobj._sig_attrs.items():
            # Notify the component of their attribute name
            cpt.attr = cpt_attr

        # List Signal attribute names.
        clsobj.component_names = list(clsobj._sig_attrs.keys())

        # The namedtuple associated with the device
        clsobj._device_tuple = namedtuple(
            name + 'Tuple',
            [comp for comp in clsobj.component_names
             if not comp.startswith('_')])
        # Finally, create all the component docstrings
        for cpt in clsobj._sig_attrs.values():
            cpt.__doc__ = cpt.make_docstring(clsobj)

        # List the attributes that are Devices (not Signals).
        # This list is used by stage/unstage. Only Devices need to be staged.
        clsobj._sub_devices = []
        for attr, cpt in clsobj._sig_attrs.items():
            if (isinstance(cpt, Component) and
                    (not isinstance(cpt.cls, type) or  # not a class
                     not issubclass(cpt.cls, Device))):  # not a Device
                continue
            clsobj._sub_devices.append(attr)

        return clsobj


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
        """Trigger the device and return status object

        This method is responsible for implementing 'trigger' or
        'acquire' functionality of this device.

        If there is an appreciable time between triggering the device
        and it being able to be read (via the
        :meth:`~BlueskyInterface.read` method) then this method is
        also responsible for arranging that the
        :obj:`~ophyd.status.StatusBase` object returned my this method
        is notified when the device is ready to be read.

        If there is no delay between triggering and being readable,
        then this method must return a :obj:`~ophyd.status.SatusBase`
        object which is already completed.

        Returns
        -------
        status : StatusBase
            :obj:`~ophyd.status.StatusBase` object which will be marked
            as complete when the device is ready to be read.

        """
        pass

    def read(self) -> OrderedDictType[str, Dict[str, Any]]:
        """Read data from the device

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
            raise RedundantStaging("Device {!r} is already staged. "
                                   "Unstage it first.".format(self))
        elif self._staged == Staged.partially:
            raise RedundantStaging("Device {!r} has been partially staged. "
                                   "Maybe the most recent unstaging "
                                   "encountered an error before finishing. "
                                   "Try unstaging again.".format(self))
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
                self.log.debug("Setting %s to %r (original value: %r)",
                               self.name,
                               val, original_vals[sig])
                set_and_wait(sig, val)
                # It worked -- now add it to this list of sigs to unstage.
                self._original_vals[sig] = original_vals[sig]
            devices_staged.append(self)

            # Call stage() on child devices.
            for attr in self._sub_devices:
                device = getattr(self, attr)
                if hasattr(device, 'stage'):
                    device.stage()
                    devices_staged.append(device)
        except Exception:
            self.log.debug("An exception was raised while staging %s or "
                           "one of its children. Attempting to restore "
                           "original settings before re-raising the "
                           "exception.", self.name)
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
            if hasattr(device, 'unstage'):
                device.unstage()
                devices_unstaged.append(device)

        # Restore original values.
        for sig, val in reversed(list(self._original_vals.items())):
            self.log.debug("Setting %s back to its original value: %r)",
                           self.name,
                           val)
            set_and_wait(sig, val)
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
        """Resume a device from a 'paused' state

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


class Device(BlueskyInterface, OphydObject, metaclass=ComponentMeta):
    """Base class for device objects

    This class provides attribute access to one or more Signals, which can be
    a mixture of read-only and writable. All must share the same base_name.

    Parameters
    ----------
    prefix : str, optional
        The PV prefix for all components of the device
    name : str, keyword only
        The name of the device
    kind : a member the Kind IntEnum (or equivalent integer), optional
        Default is Kind.normal. See Kind for options.
    read_attrs : sequence of attribute names
        DEPRECATED
        the components to include in a normal reading (i.e., in ``read()``)
    configuration_attrs : sequence of attribute names
        DEPRECATED
        the components to be read less often (i.e., in
        ``read_configuration()``) and to adjust via ``configure()``
    parent : instance or None, optional
        The instance of the parent device, if applicable
    """

    SUB_ACQ_DONE = 'acq_done'  # requested acquire

    # over ride in sub-classes to control the default
    # contents of read and configuration attrs lists

    # To use the new 'kind' parameter, set these equal to the sentinel
    # REPSECT_KIND, defined in this module.

    # If `None`, defaults to `self.component_names'
    _default_read_attrs = None
    # If `None`, defaults to `[]`
    _default_configuration_attrs = None

    def __init__(self, prefix='', *, name, kind=None,
                 read_attrs=None, configuration_attrs=None,
                 parent=None, **kwargs):
        # Store EpicsSignal objects (only created once they are accessed)
        self._signals = {}
        self._initial_state = {k: SimpleNamespace(kind=cpt.kind)
                               for k, cpt in self._sig_attrs.items()}
        self.prefix = prefix
        if self.component_names and prefix is None:
            raise ValueError('Must specify prefix if device signals are being '
                             'used')

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

        # Instantiate non-lazy signals
        [getattr(self, attr) for attr, cpt in self._sig_attrs.items()
         if not cpt.lazy]

    def _validate_kind(self, val):
        if isinstance(val, str):
            val = getattr(Kind, val.lower())
        if Kind.normal & val:
            val = val | Kind.config
        return super()._validate_kind(val)

    @property
    def read_attrs(self):
        return self.OphydAttrList(self, Kind.normal, Kind.hinted,
                                  'read_attrs')

    @read_attrs.setter
    def read_attrs(self, val):
        self.__attr_list_helper(val, Kind.normal, Kind.hinted, 'read_attrs')

    @property
    def configuration_attrs(self):
        return self.OphydAttrList(self, Kind.config, Kind.config,
                                  'configuration_attrs')

    @configuration_attrs.setter
    def configuration_attrs(self, val):
        self.__attr_list_helper(val, Kind.config, Kind.config,
                                'configuration_attrs')

    def __attr_list_helper(self, val, set_kind, unset_kind, recurse_name):
        val = set(val)
        cn = set(self.component_names)

        for c in cn:
            if c in val:
                _lazy_get(self, c).kind |= set_kind
            else:
                _lazy_get(self, c).kind &= ~unset_kind

        # now look at everything else, presumably things with dots
        extra = val - cn
        fail = set(c for c in extra if '.' not in c)
        if fail:

            raise ValueError("You asked to add the components {fail} "
                             "to {recurse_name} "
                             "on {self.name!r}, but there is no such child in "
                             "{self.component_names}."
                             .format(fail=fail, self=self,
                                     recurse_name=recurse_name))
        group = groupby(((child, rest)
                         for child, _, rest in (c.partition('.')
                                                for c in extra)),
                        lambda x: x[0])
        # we are into grand-children, can not be lazy!
        for child, cf_list in group:
            cpt = getattr(self, child)
            cpt.kind |= set_kind
            setattr(cpt,
                    recurse_name,
                    [c[1] for c in cf_list])

    @property
    def signal_names(self):
        warnings.warn("'signal_names' has been renamed 'component_names' for "
                      "clarity because it may include a mixture of Signals "
                      "and Devices -- any Components. This alias may be "
                      "removed in a future release of ophyd.", stacklevel=2)
        return self.component_names

    def summary(self):
        print(self._summary())

    def _summary(self):
        "Return a string summarizing the structure of the Device."
        desc = self.describe()
        config_desc = self.describe_configuration()
        read_attrs = self.read_attrs
        config_attrs = self.configuration_attrs
        used_attrs = set(read_attrs + config_attrs)
        extra_attrs = [a for a in self.component_names
                       if a not in used_attrs]
        hints = getattr(self, 'hints', {}).get('fields', [])

        def format_leaf(a):
            s = getattr(self, a)
            return '{:<20} {:<20}({!r})'.format(a, type(s).__name__,
                                                s.name)

        out = []
        out.append('data keys (* hints)')
        out.append('-------------------')
        for k in sorted(desc):
            out.append(('*' if k in hints else ' ') + k)
        out.append('')

        out.append('read attrs')
        out.append('----------')
        for a in read_attrs:
            out.append(format_leaf(a))

        out.append('')
        out.append('config keys')
        out.append('-----------')
        for k in sorted(config_desc):
            out.append(k)
        out.append('')

        out.append('configuration attrs')
        out.append('----------')
        for a in config_attrs:
            out.append(format_leaf(a))
        out.append('')

        out.append('Unused attrs')
        out.append('------------')
        for a in extra_attrs:
            out.append(format_leaf(a))
        return '\n'.join(out)

    def wait_for_connection(self, all_signals=False, timeout=2.0):
        '''Wait for signals to connect

        Parameters
        ----------
        all_signals : bool, optional
            Wait for all signals to connect (including lazy ones)
        timeout : float or None
            Overall timeout
        '''
        names = [attr for attr, cpt in self._sig_attrs.items()
                 if not cpt.lazy or all_signals]

        # Instantiate first to kickoff connection process
        signals = [getattr(self, name) for name in names]

        t0 = ttime.time()
        while timeout is None or (ttime.time() - t0) < timeout:
            connected = [sig.connected for sig in signals]
            if all(connected):
                return
            ttime.sleep(min((0.05, timeout / 10.0)))

        unconnected = ', '.join(self._get_unconnected())
        raise TimeoutError('Failed to connect to all signals: {}'
                           ''.format(unconnected))

    def _get_unconnected(self):
        '''Yields all of the signal pvnames or prefixes that are unconnected

        This recurses throughout the device hierarchy, only checking signals
        that have already been instantiated.
        '''
        for attr, sig in self.get_instantiated_signals():
            if sig.connected:
                continue

            if hasattr(sig, 'pvname'):
                prefix = sig.pvname
            else:
                prefix = sig.prefix

            yield '{} ({})'.format(attr, prefix)

    def get_instantiated_signals(self, *, attr_prefix=None):
        '''Yields all of the instantiated signals in a device hierarchy

        Parameters
        ----------
        attr_prefix : string, optional
            The attribute prefix. If None, defaults to self.name

        Yields
        ------
            (fully_qualified_attribute_name, signal_instance)
        '''
        if attr_prefix is None:
            attr_prefix = self.name

        for attr, sig in self._signals.items():
            # fully qualified attribute name from top-level device
            full_attr = '{}.{}'.format(attr_prefix, attr)
            if isinstance(sig, Device):
                yield from sig.get_instantiated_signals(attr_prefix=full_attr)
            else:
                yield full_attr, sig

    @property
    def connected(self):
        return all(signal.connected for name, signal in self._signals.items())

    def __getattr__(self, name):
        '''Get a component from a fully-qualified name

        As a reminder, __getattr__ is only called if a real attribute doesn't
        already exist, or a device component has yet to be instantiated.
        '''
        if '.' not in name:
            try:
                # Initial access of signal
                cpt = self._sig_attrs[name]
                return cpt.__get__(self, None)
            except KeyError:
                raise AttributeError(name)

        attr_names = name.split('.')
        try:
            attr = getattr(self, attr_names[0])
        except AttributeError:
            raise AttributeError('{} of {}'.format(attr_names[0], name))

        if len(attr_names) > 1:
            sub_attr_names = '.'.join(attr_names[1:])
            return getattr(attr, sub_attr_names)

        return attr

    @doc_annotation_forwarder(BlueskyInterface)
    def read(self):
        res = super().read()
        for component_name in self.component_names:
            # this might be lazy and get the Cpt
            component = _lazy_get(self, component_name)
            if component.kind & Kind.normal:
                # this forces us to get the real version
                component = getattr(self, component_name)
                res.update(component.read())
        return res

    def read_configuration(self) -> OrderedDictType[str, Dict[str, Any]]:
        """
        returns dictionary mapping names to (value, timestamp) pairs

        To control which fields are included, adjust the
        ``configuration_attrs`` list.
        """
        res = OrderedDict()
        for component_name in self.component_names:
            # this might be lazy and get the Cpt
            component = _lazy_get(self, component_name)
            if component.kind & Kind.config:
                # this forces us to get the real version
                component = getattr(self, component_name)
                res.update(component.read_configuration())
        return res

    @doc_annotation_forwarder(BlueskyInterface)
    def describe(self):
        res = super().describe()
        for component_name in self.component_names:
            component = _lazy_get(self, component_name)
            if component.kind & Kind.normal:
                component = getattr(self, component_name)
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
        for component_name in self.component_names:
            component = _lazy_get(self, component_name)
            if component.kind & Kind.config:
                component = getattr(self, component_name)
                res.update(component.describe_configuration())
        return res

    @property
    def hints(self):
        fields = []
        for component_name in self.component_names:
            # Pick off the component's kind without instantiating it.
            kind = _lazy_get(self, component_name).kind
            if Kind.normal & kind:
                # OK, we have to instantiate it.
                component = getattr(self, component_name)
                c_hints = component.hints
                fields.extend(c_hints.get('fields', []))
        return {'fields': fields}

    @property
    def trigger_signals(self):
        names = [attr for attr, cpt in self._sig_attrs.items()
                 if cpt.trigger_value is not None]

        return [getattr(self, name) for name in names]

    def _done_acquiring(self, **kwargs):
        '''Call when acquisition has completed.'''
        self._run_subs(sub_type=self.SUB_ACQ_DONE,
                       success=True, **kwargs)

        self._reset_sub(self.SUB_ACQ_DONE)

    @doc_annotation_forwarder(BlueskyInterface)
    def trigger(self):
        """Start acquisition"""
        signals = self.trigger_signals
        if len(signals) > 1:
            raise NotImplementedError('More than one trigger signal is not '
                                      'currently supported')
        status = DeviceStatus(self)
        if not signals:
            status._finished()
            return status

        acq_signal, = signals

        self.subscribe(status._finished,
                       event_type=self.SUB_ACQ_DONE, run=False)

        def done_acquisition(**ignored_kwargs):
            # Keyword arguments are ignored here from the EpicsSignal
            # subscription, as the important part is that the put completion
            # has finished
            self._done_acquiring()

        acq_signal.put(1, wait=False, callback=done_acquisition)
        return status

    def stop(self, *, success=False):
        '''Stop the Device and all (instantiated) subdevices'''
        exc_list = []

        for attr in self._sub_devices:
            dev = getattr(self, attr)

            if not dev.connected:
                self.log.debug('stop: device %s (%s) is not connected; '
                               'skipping', attr, dev)
                continue

            try:
                dev.stop(success=success)
            except ExceptionBundle as ex:
                exc_list.extend([('{}.{}'.format(attr, sub_attr), ex)
                                 for sub_attr, ex in ex.exceptions.items()])
            except Exception as ex:
                exc_list.append((attr, ex))
                self.log.exception('Device %s (%s) stop failed', attr, dev)

        if exc_list:
            exc_info = '\n'.join('{} raised {!r}'.format(attr, ex)
                                 for attr, ex in exc_list)
            raise ExceptionBundle('{} exception(s) were raised during stop: \n'
                                  '{}'.format(len(exc_list), exc_info),
                                  exceptions=dict(exc_list))

    def get(self, **kwargs):
        '''Get the value of all components in the device

        Keyword arguments are passed onto each signal.get(). Components
        beginning with an underscore will not be included.
        '''
        values = {}
        for attr in self.component_names:
            if not attr.startswith('_'):
                signal = getattr(self, attr)
                values[attr] = signal.get(**kwargs)

        return self._device_tuple(**values)

    def put(self, dev_t, **kwargs):
        '''Put a value to all components of the device

        Keyword arguments are passed onto each signal.put()

        Parameters
        ----------
        dev_t : DeviceTuple or tuple
            The device tuple with the value(s) to put (see get_device_tuple)
        '''
        if not isinstance(dev_t, self._device_tuple):
            try:
                dev_t = self._device_tuple(dev_t)
            except TypeError as ex:
                raise ValueError('{}\n\tDevice tuple fields: {}'
                                 ''.format(ex, self._device_tuple._fields))

        for attr in self.component_names:
            value = getattr(dev_t, attr)
            signal = getattr(self, attr)
            signal.put(value, **kwargs)

    @classmethod
    def get_device_tuple(cls):
        '''The device tuple type associated with an Device class

        This is a tuple representing the full state of all components and
        dynamic device sub-components.
        '''
        return cls._device_tuple

    def configure(self,
                  d: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        '''Configure the device for something during a run

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
        '''
        old = self.read_configuration()
        for key, val in d.items():
            if key not in self.configuration_attrs:
                # a little extra checking for a more specific error msg
                if key not in self.component_names:
                    raise ValueError("There is no signal named %s" % key)
                else:
                    raise ValueError("%s is not one of the "
                                     "configuration_fields, so it cannot be "
                                     "changed using configure" % key)
            set_and_wait(getattr(self, key), val)
        new = self.read_configuration()
        return old, new

    def _repr_info(self):
        yield ('prefix', self.prefix)
        yield from super()._repr_info()

        yield ('read_attrs', self.read_attrs)
        yield ('configuration_attrs', self.configuration_attrs)

    class OphydAttrList(MutableSequence):
        """list proxy to migrate away from Device.read_attrs and Device.config_attrs


        """
        def __init__(self, device, kind, remove_kind, recurse_key):
            self._kind = kind
            self._remove_kind = remove_kind
            self._parent = device
            self._recurse_key = recurse_key

        def __internal_list(self):

            children = [c for c in self._parent.component_names
                        if _lazy_get(self._parent, c).kind & self._kind]
            out = []
            for c in children:
                cmpt = getattr(self._parent, c)
                out.append(c)
                if hasattr(cmpt, self._recurse_key):
                    out.extend('.'.join([c, v]) for v in
                               getattr(cmpt, self._recurse_key, []))

            return out

        def __getitem__(self, key):
            return self.__internal_list()[key]

        def __setitem__(self, key, val):
            raise NotImplemented

        def __delitem__(self, key):
            o = self.__internal_list()[key]
            if not isinstance(key, slice):
                o = [o]
            for k in o:
                getattr(self._parent, k).kind &= ~self._remove_kind

        def __len__(self):
            return len(self.__internal_list())

        def insert(self, index, object):
            getattr(self._parent, object).kind |= self._kind

        def remove(self, value):
            getattr(self._parent, value).kind &= ~self._remove_kind

        def __contains__(self, value):
            return getattr(self._parent, value).kind & self._kind

        def __iter__(self):
            yield from self.__internal_list()

        def __eq__(self, other):
            return list(self) == other

        def __repr__(self):
            return repr(list(self))

        def __add__(self, other):
            return list(self) + list(other)


@contextlib.contextmanager
def kind_context(kind):
    yield functools.partial(Component, kind=kind)


def _lazy_get(parent, name):
    return parent._signals.get(name, parent._initial_state[name])


def _ensure_kind(k):
    return getattr(Kind, k.lower()) if isinstance(k, str) else k
