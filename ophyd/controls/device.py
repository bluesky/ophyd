import time

from collections import (OrderedDict, namedtuple)

from .ophydobj import (OphydObject, DeviceStatus)
from ..utils import TimeoutError


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

    def __init__(self, cls, suffix, lazy=False, trigger_value=None,
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
    '''An OphydDevice component that dynamically creates a OphyDevice

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

    def __init__(self, defn, clsname=None, doc=None):
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
        inst_read = set(instance.read_signals)
        if self.attr in inst_read:
            # if the sub-device is in the read list, then add all attrs
            read_signals = attrs
        else:
            # otherwise, only add the attributes that exist in the sub-device
            # to the read_signals list
            read_signals = inst_read.intersection(attrs)

        cls = type(clsname, (OphydDevice, ), clsdict)
        return cls(instance.prefix, read_signals=list(read_signals),
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
        # *TODO* this has to use bases!

        # map component classes to their attribute names
        components = [(value, attr) for attr, value in clsdict.items()
                      if isinstance(value, (Component,
                                            DynamicDeviceComponent))]

        clsobj._sig_attrs = OrderedDict(components)

        for cpt, cpt_attr in clsobj._sig_attrs.items():
            # Notify the component of their attribute name
            cpt.attr = cpt_attr

        # List Signal attribute names.
        clsobj.signal_names = list(clsobj._sig_attrs.values())

        # The namedtuple associated with the device
        clsobj._device_tuple = namedtuple(name + 'Tuple', clsobj.signal_names,
                                          rename=True)

        # Finally, create all the component docstrings
        for cpt, cpt_attr in clsobj._sig_attrs.items():
            cpt.__doc__ = cpt.make_docstring(clsobj)

        return clsobj


class OphydDevice(OphydObject, metaclass=ComponentMeta):
    """Base class for device objects

    This class provides attribute access to one or more Signals, which can be
    a mixture of read-only and writable. All must share the same base_name.

    Parameters
    ----------
    prefix : str
        The PV prefix for all components of the device
    read_signals : sequence of attribute names
        The signals to be read during data acquisition (i.e., in read() and
        describe() calls)
    name : str, optional
        The name of the device
    parent : instance or None
        The instance of the parent device, if applicable
    """

    SUB_ACQ_DONE = 'acq_done'  # requested acquire

    def __init__(self, prefix, read_signals=None, name=None, parent=None,
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

        if read_signals is None:
            read_signals = self.signal_names

        self.read_signals = list(read_signals)

        # Instantiate non-lazy signals
        [getattr(self, attr) for cpt, attr in self._sig_attrs.items()
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
        names = [attr for cpt, attr in self._sig_attrs.items()
                 if not cpt.lazy or all_signals]

        # Instantiate first to kickoff connection process
        signals = [getattr(self, name) for name in names]

        t0 = time.time()
        while timeout is None or (time.time() - t0) < timeout:
            connected = [sig.connected for sig in signals]
            if all(connected):
                return
            time.sleep(min((0.05, timeout / 10.0)))

        unconnected = [sig.name for sig in signals
                       if not sig.connected]

        raise TimeoutError('Failed to connect to all signals: {}'
                           ''.format(', '.join(unconnected)))

    @property
    def connected(self):
        return all(signal.connected for name, signal in self._signals.items())

    def _get_devattr(self, name):
        '''Gets a component from a fully-qualified python name'''
        attrs = name.split('.', 1)

        sub_attr = '.'.join(attrs[1:])
        try:
            attr = getattr(self, attrs[0])
        except AttributeError:
            raise AttributeError('{} {} has no attribute {}'
                                 ''.format(self.__class__.__name__, self.name,
                                           attrs[0]))

        if sub_attr:
            # TODO is it a bad idea to promote this to __getattr__?
            if hasattr(attr, '_get_devattr'):
                return attr._get_devattr(sub_attr)
            else:
                return getattr(attr, sub_attr)

        return attr


    def read(self):
        # map names ("data keys") to actual values
        values = OrderedDict()
        for name in self.read_signals:
            signal = self._get_devattr(name)
            values.update(signal.read())

        return values

    def describe(self):
        desc = OrderedDict()
        for name in self.read_signals:
            signal = self._get_devattr(name)
            desc.update(signal.describe())

        return desc

    @property
    def trigger_signals(self):
        names = [attr for cpt, attr in self._sig_attrs.items()
                 if cpt.trigger_value is not None]

        return [getattr(self, name) for name in names]

    def trigger(self, **kwargs):
        """Start acquisition"""
        # TODO mass confusion here
        signals = self.trigger_signals
        if len(signals) > 1:
            raise NotImplementedError('TODO more than one trigger')
        elif len(signals) == 0:
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

    def _done_acquiring(self, **kwargs):
        '''Call when acquisition has completed.'''
        self._run_subs(sub_type=self.SUB_ACQ_DONE,
                       success=True, **kwargs)

        self._reset_sub(self.SUB_ACQ_DONE)

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
        '''The device tuple type associated with an OphydDevice class

        This is a tuple representing the full state of all components and
        dynamic device sub-components.
        '''
        return cls._device_tuple

    @property
    def report(self):
        # TODO
        return {}

    @property
    def state(self):
        return {}

    def configure(self, state=None):
        # does nothing; subclasses can override if configuration is possible
        return self.state, self.state

    def deconfigure(self):
        return self.state
