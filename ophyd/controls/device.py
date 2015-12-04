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
        Class of signal to create
    suffix : str
        The PV suffix, which gets appended onto the device prefix
    add_prefix : sequence, optional
        Arguments to attach the device prefix to.
        Defaults to ('suffix', 'write_pv')
    lazy : bool, optional
        Lazily instantiate the signal. If False, the signal will be instantiated
        upon object instantiation
    trigger_value : any, optional
        Mark as a signal to be set on trigger. The value is sent to the signal
        at trigger time.
    '''

    def __init__(self, cls, suffix, lazy=False, trigger_value=None,
                 add_prefix=None, **kwargs):
        self.attr = None  # attr is set later by the device when known
        self.cls = cls
        self.kwargs = kwargs
        self.lazy = lazy
        self.suffix = suffix
        self.trigger_value = trigger_value  # TODO discuss

        if add_prefix is None:
            add_prefix = ('suffix', 'write_pv')

        self.add_prefix = tuple(add_prefix)

    def get_pv_name(self, instance, attr, suffix):
        '''Get pv name for a given suffix'''
        if attr in self.add_prefix:
            # Optionally use a separator from the instance
            if hasattr(instance, '_sep'):
                sep = instance._sep
            else:
                sep = ''

            return sep.join((instance.prefix, suffix))
        else:
            return suffix

    def create_component(self, instance):
        '''Create a component for the instance'''
        kwargs = self.kwargs.copy()
        kwargs['name'] = '{}.{}'.format(instance.name, self.attr)

        for kw in self.add_prefix:
            # If any keyword arguments need a prefix, tack it on
            if kw in kwargs:
                suffix = self.get_pv_name(instance, kw, kwargs[kw])
                kwargs[kw] = suffix

        # Otherwise, we only have suffix to update
        pv_name = self.get_pv_name(instance, 'suffix', self.suffix)

        cpt_inst = self.cls(pv_name, **kwargs)

        if self.lazy and hasattr(self.cls, 'wait_for_connection'):
            cpt_inst.wait_for_connection()

        return cpt_inst

    def make_docstring(self, parent_class):
        return '{} component with suffix {}'.format(self.attr, self.suffix)

    def __get__(self, instance, owner):
        if instance is None:
            return self

        if self.attr not in instance._signals:
            instance._signals[self.attr] = self.create_component(instance)

        return instance._signals[self.attr]

    def __set__(self, instance, owner):
        raise RuntimeError('Use .put()')


class DynamicComponent:
    def __init__(self, defn, clsname=None):
        self.defn = defn
        self.clsname = clsname
        self.attr = None  # attr is set later by the device when known
        self.lazy = False

        # TODO: component compatibility
        self.trigger_value = None
        self.attrs = list(defn.keys())

    def make_docstring(self, parent_class):
        return '{} dynamiccomponent containing {}'.format(self.attr,
                                                          self.attrs)

    def get_separator(self, instance):
        if hasattr(instance, '_sep'):
            return instance._sep
        else:
            return ''

    def create_attr(self, attr_name):
        cls, suffix, kwargs = self.defn[attr_name]
        inst = Component(cls, suffix, **kwargs)
        inst.attr = attr_name
        return inst

    def create_component(self, instance):
        '''Create a component for the instance'''
        clsname = self.clsname
        if clsname is None:
            clsname = ''.join((instance.__class__.__name__,
                               self.attr.capitalize()))

        clsdict = OrderedDict(_sep=self.get_separator(instance),
                              __doc__='{} sub-device'.format(clsname),
                              )

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
                   name='{}.{}'.format(instance.name, self.attr))

    def __get__(self, instance, owner):
        if instance is None:
            return self

        if self.attr not in instance._signals:
            instance._signals[self.attr] = self.create_component(instance)

        return instance._signals[self.attr]

    def __set__(self, instance, owner):
        raise RuntimeError('Use .put()')


def range_def(cls, field_name, suffix, range_, format_key='index',
              **kwargs):
    '''Create a DynamicComponent definition based on a range of indices'''
    defn = OrderedDict()
    for i in range_:
        fmt_dict = {format_key: i}
        attr = field_name.format(**fmt_dict)
        defn[attr] = (cls, suffix.format(**fmt_dict), kwargs)

    return defn


class ComponentMeta(type):
    '''Creates attributes for Components by inspecting class definition'''

    @classmethod
    def __prepare__(self, name, bases):
        '''Prepare allows the class attribute dictionary to be ordered as
        defined by the user'''
        return OrderedDict()

    def __new__(cls, name, bases, clsdict):
        clsobj = super().__new__(cls, name, bases, clsdict)

        # map component classes to their attribute names
        components = [(value, attr) for attr, value in clsdict.items()
                      if isinstance(value, (Component, DynamicComponent))]

        clsobj._sig_attrs = OrderedDict(components)

        # since we have a hierarchy of devices/sub-devices, note which
        # components belong to which device
        clsobj._sig_owner = OrderedDict()

        for cpt, cpt_attr in clsobj._sig_attrs.items():
            # Notify the component of their attribute name
            cpt.attr = cpt_attr

            if isinstance(cpt, DynamicComponent):
                # owner = None means the object itself
                clsobj._sig_owner[cpt_attr] = None
                for sub_attr in cpt.attrs:
                    # the dynamiccomponent attribute owns each of its
                    # sub-attributes
                    clsobj._sig_owner[sub_attr] = cpt_attr
            elif isinstance(cpt, Component):
                clsobj._sig_owner[cpt_attr] = None

        # List Signal attribute names.
        clsobj.signal_names = list(clsobj._sig_attrs.values())

        # The namedtuple associated with the device
        clsobj._device_tuple = namedtuple(name + 'Tuple', clsobj.signal_names,
                                          rename=True)

        # Store EpicsSignal objects (only created once they are accessed)
        clsobj._signals = {}

        # Finally, create all the component docstrings
        for cpt, cpt_attr in clsobj._sig_attrs.items():
            cpt.__doc__ = cpt.make_docstring(clsobj)

        return clsobj


class OphydDevice(OphydObject, metaclass=ComponentMeta):
    """Base class for device objects

    This class provides attribute access to one or more Signals, which can be
    a mixture of read-only and writable. All must share the same base_name.
    """

    SUB_ACQ_DONE = 'acq_done'  # requested acquire

    def __init__(self, prefix, read_signals=None, name=None):
        self.prefix = prefix
        if self.signal_names and prefix is None:
            raise ValueError('Must specify prefix if device signals are being '
                             'used')

        if name is None:
            name = prefix

        OphydObject.__init__(self, name=name)

        if read_signals is None:
            read_signals = self.signal_names

        self.read_signals = read_signals

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
        '''Gets a device attribute which may come from a sub-device'''
        try:
            owner_attr = self._sig_owner[name]
        except KeyError:
            raise ValueError('Unknown read signal: {}'.format(name))

        if owner_attr is None:
            # None means this instance owns it
            return getattr(self, name)
        else:
            # Otherwise, get the owner first
            owner = getattr(self, owner_attr)
            # Then the attribute
            return getattr(owner, name)

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

        def done_acquisition(**kwargs):
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
        values = {}
        for attr in self.signal_names:
            signal = getattr(self, attr)
            values[attr] = signal.get(**kwargs)

        return self._device_tuple(**values)

    def put(self, **kwargs):
        kw_set = set(kwargs.keys())
        sig_set = set(self.signal_names)
        if kw_set != sig_set:
            missing = sig_set - kw_set
            unknown = kw_set - sig_set
            msg = ['Required set of signals does not match. ']
            if missing:
                msg.append('\tMissing keys: {}'.format(', '.join(missing)))
            if unknown:
                msg.append('\tUnknown keys: {}'.format(', '.join(unknown)))
            raise ValueError('\n'.join(msg))

        for attr in self.signal_names:
            value = kwargs[attr]
            signal = getattr(self, attr)
            signal.put(value, **kwargs)

    @classmethod
    def get_device_tuple(cls):
        '''The device tuple associated with an OphydDevice class'''
        return cls._device_tuple
