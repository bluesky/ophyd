import time as ttime
import logging

from collections import (OrderedDict, namedtuple)

from .ophydobj import (OphydObject, DeviceStatus)
from .utils import TimeoutError, set_and_wait

logger = logging.getLogger(__name__)


class Component:
    '''A descriptor representing a device component (or signal)

    Unrecognized keyword arguments will be passed directly to the component
    class initializer.

    Parameters
    ----------
    cls : class
        Class of signal to create.  The required signature of
        `cls.__init__` is ::

            def __init__(self, pv_name, parent=None, **kwargs):

        The class may have a `wait_for_connection()` which is called
        during the component instance creation.

    suffix : str
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

    def __init__(self, cls, suffix, *, lazy=False, trigger_value=None,
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

    def get_pv_name(self, instance, attr, suffix):
        '''Get pv name for a given suffix'''
        if attr in self.add_prefix:
            return '{prefix}{suffix}'.format(prefix=instance.prefix,
                                             suffix=suffix)
        else:
            return suffix

    def create_component(self, instance):
        '''Create a component for the instance'''
        kwargs = self.kwargs.copy()
        kwargs['name'] = '{}_{}'.format(instance.name, self.attr)

        for kw in self.add_prefix:
            # If any keyword arguments need a prefix, tack it on
            if kw in kwargs:
                suffix = self.get_pv_name(instance, kw, kwargs[kw])
                kwargs[kw] = suffix

        # Otherwise, we only have suffix to update
        pv_name = self.get_pv_name(instance, 'suffix', self.suffix)

        cpt_inst = self.cls(pv_name, parent=instance, **kwargs)

        if self.lazy and hasattr(self.cls, 'wait_for_connection'):
            cpt_inst.wait_for_connection()

        return cpt_inst

    def make_docstring(self, parent_class):
        if self.doc is not None:
            return self.doc

        return '{} component with suffix {}'.format(self.attr, self.suffix)

    def __get__(self, instance, owner):
        if instance is None:
            return self

        if self.attr not in instance._signals:
            instance._signals[self.attr] = self.create_component(instance)

        return instance._signals[self.attr]

    def __set__(self, instance, owner):
        raise RuntimeError('Use .put()')


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

        return '{} dynamicdevice containing {}'.format(self.attr,
                                                       self.attrs)

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
        clsobj._sig_attrs = OrderedDict()

        # map component classes to their attribute names from this class
        for attr, value in clsdict.items():
            if isinstance(value, (Component, DynamicDeviceComponent)):
                if attr in clsobj._sig_attrs:
                    print('overriding', attr)
                clsobj._sig_attrs[attr] = value

        for cpt_attr, cpt in clsobj._sig_attrs.items():
            # Notify the component of their attribute name
            cpt.attr = cpt_attr

        # List Signal attribute names.
        clsobj.signal_names = list(clsobj._sig_attrs.keys())
        for b in bases:
            try:
                clsobj.signal_names.extend(b.signal_names)
            except AttributeError:
                pass
        # The namedtuple associated with the device
        clsobj._device_tuple = namedtuple(name + 'Tuple', clsobj.signal_names,
                                          rename=True)

        # Finally, create all the component docstrings
        for cpt in clsobj._sig_attrs.values():
            cpt.__doc__ = cpt.make_docstring(clsobj)

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
        self.stage_sigs = list()
        self._staged = False
        super().__init__(*args, **kwargs)

    def trigger(self):
        pass

    def read(self):
        return {}

    def describe(self):
        return {}

    def stage(self):
        "Prepare the device to be triggered."
        if self._staged:
            raise RuntimeError("Device is already stage. Unstage it first.")

        # Read and stage current values, to be restored by unstage()
        self._original_vals = [(sig, sig.get())
                               for sig, _ in self.stage_sigs]

        # Apply settings.
        self._staged = True
        for sig, val in self.stage_sigs:
            set_and_wait(sig, val)

        # Call stage() on child devices (including, notably, plugins).
        for signal_name in self.signal_names:
            signal = getattr(self, signal_name)
            if hasattr(signal, 'stage'):
                signal.stage()

    def unstage(self):
        """
        Restore the device to 'standby'.

        Multiple calls (without a new call to 'stage') have no effect.
        """
        if not self._staged:
            # Unlike staging, there is no harm in making unstage
            # 'indepotent'.
            logger.debug("Cannot unstage %r; it is not staged. Passing.",
                         self)
            return

        # Restore original values.
        for sig, val in reversed(self._original_vals):
            set_and_wait(sig, val)

        # Call unstage() on child devices (including, notably, plugins).
        for signal_name in self.signal_names:
            signal = getattr(self, signal_name)
            if hasattr(signal, 'unstage'):
                signal.unstage()

        self._staged = False


class GenerateDatumInterface:
    """Classes that inherit from this can safely customize the
    `generate_datum` method without breaking mro. If used along with the
    BlueskyInterface, inherit from this second."""
    def generate_datum(self, key):
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
        The signals to be read during data acquisition (i.e., in read() and
        describe() calls)
    name : str, optional
        The name of the device
    parent : instance or None
        The instance of the parent device, if applicable
    """

    SUB_ACQ_DONE = 'acq_done'  # requested acquire

    def __init__(self, prefix, *, read_attrs=None, configuration_attrs=None,
                 monitor_attrs=None, name=None, parent=None,
                 **kwargs):
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

        if monitor_attrs is None:
            monitor_attrs = []

        self.read_attrs = list(read_attrs)
        self.configuration_attrs = list(configuration_attrs)
        self.monitor_attrs = list(monitor_attrs)

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

        unconnected = [sig.name for sig in signals
                       if not sig.connected]

        raise TimeoutError('Failed to connect to all signals: {}'
                           ''.format(', '.join(unconnected)))

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

    def _read_attr_list(self, attr_list):
        '''Get a 'read' dictionary containing attributes in attr_list'''
        values = OrderedDict()
        for name in attr_list:
            signal = getattr(self, name)
            values.update(signal.read())

        return values

    def read(self):
        '''map names ("data keys") to actual values'''
        res = super().read()
        res.update(self._read_attr_list(self.read_attrs))
        return res

    def read_configuration(self):
        return self._read_attr_list(self.configuration_attrs)

    def _describe_attr_list(self, attr_list):
        '''Get a 'describe' dictionary containing attributes in attr_list'''
        desc = OrderedDict()
        for name in attr_list:
            signal = getattr(self, name)
            desc.update(signal.describe())

        return desc

    def describe(self):
        '''describe the read data keys' data types and other metadata'''
        res = super().describe()
        res.update(self._describe_attr_list(self.read_attrs))
        return res

    def describe_configuration(self):
        '''describe the configuration data keys' data types/other metadata'''
        return self._describe_attr_list(self.configuration_attrs)

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
        elif not signals:
            raise RuntimeError('Device has no trigger signal(s)')

        acq_signal = signals[0]
        status = DeviceStatus(self)
        self.subscribe(status._finished,
                       event_type=self.SUB_ACQ_DONE, run=False)

        def done_acquisition(**ignored_kwargs):
            # Keyword arguments are ignored here from the EpicsSignal
            # subscription, as the important part is that the put completion
            # has finished
            self._done_acquiring()

        acq_signal.put(1, wait=False, callback=done_acquisition)
        return status

    def stop(self):
        '''to be defined by subclass'''
        pass

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

    @property
    def report(self):
        # TODO
        return {}

    def configure(self, d=None):
        '''Configure the device for something during a run

        This default implementation allows the user to change any of the
        `configuration_attrs`. Subclasses might override this to perform
        additional input validation, cleanup, etc.

        Parameters
        ----------
        d : dict
            The configuration dictionary

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
                    raise ValueError("there is no signal named %s", key)
                else:
                    raise ValueError("%s is not one of the "
                                     "configuration_fields, so it cannot be "
                                     "changed using configure", key)
            getattr(self, key).put(val)
        new = self.read_configuration()
        return old, new

    def _repr_info(self):
        yield ('prefix', self.prefix)
        yield from super()._repr_info()

        yield ('read_attrs', self.read_attrs)
        yield ('configuration_attrs', self.configuration_attrs)
        yield ('monitor_attrs', self.monitor_attrs)
