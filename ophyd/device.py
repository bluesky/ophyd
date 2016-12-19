import time as ttime
import logging
import textwrap
from enum import Enum
from collections import (OrderedDict, namedtuple)

from .ophydobj import OphydObject
from .status import DeviceStatus
from .utils import (ExceptionBundle, set_and_wait, RedundantStaging)

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
        The PV suffix, which gets appended onto the device prefix to
        generate the final PV that the instance component will bind to.

    lazy : bool, optional
        Lazily instantiate the signal. If False, the signal will be
        instantiated upon component instantiation
    trigger_value : any, optional
        Mark as a signal to be set on trigger. The value is sent to the signal
        at trigger time.
    add_prefix : sequence, optional
        Keys in the kwargs to prefix with the Device PV prefix during
        creation of the component instance.
        Defaults to ('suffix', 'write_pv', )
    doc : str, optional
        string to attach to component DvcClass.component.__doc__
    '''

    def __init__(self, cls, suffix=None, *, lazy=False, trigger_value=None,
                 add_prefix=None, doc=None, **kwargs):
        self.attr = None  # attr is set later by the device when known
        self.cls = cls
        self.kwargs = kwargs
        self.lazy = lazy
        self.suffix = suffix
        self.doc = doc
        self.trigger_value = trigger_value  # TODO discuss

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

        for kw, val in list(kwargs.items()):
            kwargs[kw] = self.maybe_add_prefix(instance, kw, val)

        if self.suffix is not None:
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

        return ('{self.__class__.__name__}({self.cls.__name__}{arg_str})'
                ''.format(self=self, arg_str=arg_str))

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
        The definition of all attributes to be created, in the form of:
            defn['attribute_name'] = (SignalClass, pv_suffix, keyword_arg_dict)
        This will create an attribute on the sub-device of type `SignalClass`,
        with a suffix of pv_suffix, which looks something like this:
            parent.attribute_name = SignalClass(pv_suffix, **keyword_arg_dict)
        Keep in mind that this is actually done in the metaclass creation, and
        not exactly as written above.
    clsname : str, optional
        The name of the class to be generated
        This defaults to {parent_name}{this_attribute_name.capitalize()}
    doc : str, optional
        The docstring to put on the dynamically generated class
    '''

    def __init__(self, defn, *, clsname=None, doc=None):
        self.defn = defn
        self.clsname = clsname
        self.attr = None  # attr is set later by the device when known
        self.lazy = False
        self.doc = doc

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

        clsdict = OrderedDict(__doc__=docstring)

        for attr in self.defn.keys():
            clsdict[attr] = self.create_attr(attr)

        attrs = set(self.defn.keys())
        inst_read = set(instance.read_attrs)
        if self.attr in inst_read:
            # if the sub-device is in the read list, then add all attrs
            read_attrs = attrs
        else:
            # otherwise, only add the attributes that exist in the sub-device
            # to the read_attrs list
            read_attrs = inst_read.intersection(attrs)

        cls = type(clsname, (Device, ), clsdict)
        return cls(instance.prefix, read_attrs=list(read_attrs),
                   name='{}_{}'.format(instance.name, self.attr),
                   parent=instance)

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
        INSTANCE_ATTRS = ['name', 'parent', 'signal_names', '_signals',
                          'read_attrs', 'configuration_attrs', '_sig_attrs',
                          '_sub_devices']
        # These attributes are part of the bluesky interface and cannot be
        # used as component names.
        RESERVED_ATTRS = ['read', 'describe', 'trigger',
                          'configure', 'read_configuration',
                          'describe_configuration', 'describe_collect',
                          'set', 'stage', 'unstage', 'pause', 'resume',
                          'kickoff', 'complete', 'collect', 'position', 'stop',
                          # from OphydObject
                          'subscribe', 'clear_sub', 'event_types', 'root']
        for attr in INSTANCE_ATTRS:
            if attr in clsdict:
                raise TypeError("The attribute name %r is reserved for "
                                "use by the Device class. Choose a different "
                                "name." % attr)

        clsobj._sig_attrs = OrderedDict()
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
        clsobj.signal_names = list(clsobj._sig_attrs.keys())

        # The namedtuple associated with the device
        clsobj._device_tuple = namedtuple(name + 'Tuple', clsobj.signal_names,
                                          rename=True)

        # Finally, create all the component docstrings
        for cpt in clsobj._sig_attrs.values():
            cpt.__doc__ = cpt.make_docstring(clsobj)

        # List the attributes that are Devices (not Signals).
        # This list is used by stage/unstage. Only Devices need to be staged.
        clsobj._sub_devices = []
        for attr, cpt in clsobj._sig_attrs.items():
            if isinstance(cpt, Component) and not issubclass(cpt.cls, Device):
                continue
            clsobj._sub_devices.append(attr)

        return clsobj


# These stub 'Interface' classes are the apex of the mro heirarchy for
# their respective methods. They make multiple interitance more
# forgiving, and let us define classes that customize these methods
# but are not full Devices.


class BlueskyInterface:
    """Classes that inherit from this can safely customize the
    these methods without breaking mro."""
    def __init__(self, *args, **kwargs):
        # Subclasses can populate this with (signal, value) pairs, to be
        # set by stage() and restored back by unstage().
        self.stage_sigs = OrderedDict()

        self._staged = Staged.no
        self._original_vals = OrderedDict()
        super().__init__(*args, **kwargs)

    def trigger(self):
        pass

    def read(self):
        return OrderedDict()

    def describe(self):
        return OrderedDict()

    def stage(self):
        """
        Prepare the device to be triggered.

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
        logger.debug("Staging %s", self.name)
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
        original_vals = {sig: sig.get() for sig, _ in stage_sigs.items()}

        # We will add signals and values from original_vals to
        # self._original_vals one at a time so that
        # we can undo our partial work in the event of an error.

        # Apply settings.
        devices_staged = []
        try:
            for sig, val in stage_sigs.items():
                logger.debug("Setting %s to %r (original value: %r)", self.name,
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
            logger.debug("An exception was raised while staging %s or "
                         "one of its children. Attempting to restore "
                         "original settings before re-raising the "
                         "exception.", self.name)
            self.unstage()
            raise
        else:
            self._staged = Staged.yes
        return devices_staged

    def unstage(self):
        """
        Restore the device to 'standby'.

        Multiple calls (without a new call to 'stage') have no effect.

        Returns
        -------
        devices : list
            list including self and all child devices unstaged
        """
        logger.debug("Unstaging %s", self.name)
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
            logger.debug("Setting %s back to its original value: %r)", self.name,
                         val)
            set_and_wait(sig, val)
            self._original_vals.pop(sig)
        devices_unstaged.append(self)

        self._staged = Staged.no
        return devices_unstaged

    def pause(self):
        pass

    def resume(self):
        pass


class GenerateDatumInterface:
    """Classes that inherit from this can safely customize the
    `generate_datum` method without breaking mro. If used along with the
    BlueskyInterface, inherit from this second."""
    def generate_datum(self, key, timestamp):
        pass


class Device(BlueskyInterface, OphydObject, metaclass=ComponentMeta):
    """Base class for device objects

    This class provides attribute access to one or more Signals, which can be
    a mixture of read-only and writable. All must share the same base_name.

    Parameters
    ----------
    prefix : str
        The PV prefix for all components of the device
    read_attrs : sequence of attribute names
        the components to include in a normal reading (i.e., in ``read()``)
    configuration_attrs : sequence of attribute names
        the components to be read less often (i.e., in
        ``read_configuration()``) and to adjust via ``configure()``
    name : str, optional
        The name of the device
    parent : instance or None
        The instance of the parent device, if applicable
    """

    SUB_ACQ_DONE = 'acq_done'  # requested acquire

    def __init__(self, prefix, *, read_attrs=None, configuration_attrs=None,
                 name=None, parent=None, **kwargs):
        # Store EpicsSignal objects (only created once they are accessed)
        self._signals = {}

        self.prefix = prefix
        if self.signal_names and prefix is None:
            raise ValueError('Must specify prefix if device signals are being '
                             'used')

        if name is None:
            name = prefix

        super().__init__(name=name, parent=parent, **kwargs)

        if read_attrs is None:
            read_attrs = self.signal_names

        if configuration_attrs is None:
            configuration_attrs = []

        self.read_attrs = list(read_attrs)
        self.configuration_attrs = list(configuration_attrs)

        # Instantiate non-lazy signals
        [getattr(self, attr) for attr, cpt in self._sig_attrs.items()
         if not cpt.lazy]

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

    def _read_attr_list(self, attr_list, *, config=False):
        '''Get a 'read' dictionary containing attributes in attr_list'''
        values = OrderedDict()
        for attr in attr_list:
            obj = getattr(self, attr)
            if config:
                values.update(obj.read_configuration())

            values.update(obj.read())

        return values

    def read(self):
        """returns dictionary mapping names to (value, timestamp) pairs

        To control which fields are included, adjust the ``read_attrs`` list.
        """
        res = super().read()
        res.update(self._read_attr_list(self.read_attrs))
        return res

    def read_configuration(self):
        """
        returns dictionary mapping names to (value, timestamp) pairs

        To control which fields are included, adjust the
        ``configuration_attrs`` list.
        """
        return self._read_attr_list(self.configuration_attrs, config=True)

    def _describe_attr_list(self, attr_list, *, config=False):
        '''Get a 'describe' dictionary containing attributes in attr_list'''
        desc = OrderedDict()
        for attr in attr_list:
            obj = getattr(self, attr)
            if config:
                desc.update(obj.describe_configuration())

            desc.update(obj.describe())

        return desc

    def describe(self):
        '''describe the read data keys' data types and other metadata'''
        res = super().describe()
        res.update(self._describe_attr_list(self.read_attrs))
        return res

    def describe_configuration(self):
        '''describe the configuration data keys' data types/other metadata'''
        return self._describe_attr_list(self.configuration_attrs, config=True)

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
                logger.debug('stop: device %s (%s) is not connected; '
                             'skipping', attr, dev)
                continue

            try:
                dev.stop(success=success)
            except ExceptionBundle as ex:
                exc_list.extend([('{}.{}'.format(attr, sub_attr), ex)
                                 for sub_attr, ex in ex.exceptions.items()])
            except Exception as ex:
                exc_list.append((attr, ex))
                logger.error('Device %s (%s) stop failed', attr, dev,
                             exc_info=ex)

        if exc_list:
            exc_info = '\n'.join('{} raised {!r}'.format(attr, ex)
                                 for attr, ex in exc_list)
            raise ExceptionBundle('{} exception(s) were raised during stop: \n'
                                  '{}'.format(len(exc_list), exc_info),
                                  exceptions=dict(exc_list))

    def get(self, **kwargs):
        '''Get the value of all components in the device

        Keyword arguments are passed onto each signal.get()
        '''
        values = {}
        for attr in self.signal_names:
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

        for attr in self.signal_names:
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

    def configure(self, d):
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
                if key not in self.signal_names:
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
