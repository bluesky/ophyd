import time

from collections import OrderedDict

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

    def get_name(self, instance):
        '''Get a name for the device signal'''
        name = self.kwargs.get('name', self.attr)
        return '{}.{}'.format(instance.name, name)

    def create_component(self, instance):
        '''Create a component for the instance'''
        kwargs = self.kwargs.copy()
        kwargs['name'] = self.get_name(instance)

        for kw in self.add_prefix:
            # If any keyword arguments need a prefix, tack it on
            if kw in kwargs:
                suffix = self.get_pv_name(instance, kw, kwargs[kw])
                kwargs[kw] = suffix

        # Otherwise, we only have suffix to update
        pv_name = self.get_pv_name(instance, 'suffix', self.suffix)
        return self.cls(pv_name, **kwargs)

    def __get__(self, instance, owner):
        if instance is None:
            return self

        if self.attr not in instance._signals:
            instance._signals[self.attr] = self.create_component(instance)

        return instance._signals[self.attr]

    def __set__(self, instance, owner):
        raise RuntimeError('Use .put()')


class DynamicComponent:
    def __init__(self, sub_prefix, *defns, clsname=None, **kwargs):
        self.defns = defns
        self.clsname = clsname
        self.attr = None  # attr is set later by the device when known
        self.lazy = False
        self.kwargs = kwargs
        self.sub_prefix = sub_prefix

        # TODO: component compatibility
        self.trigger_value = None

    def get_name(self, instance):
        '''Get a name for the device signal'''
        name = self.kwargs.get('name', self.attr)
        return '{}.{}'.format(instance.name, name)

    def get_sub_prefix(self, instance):
        '''Get the sub prefix from an instance'''
        # Optionally use a separator from the instance
        sep = self.get_separator(instance)
        return sep.join((instance.prefix, self.sub_prefix))

    def get_separator(self, instance):
        if hasattr(instance, '_sep'):
            return instance._sep
        else:
            return ''

    def create_component(self, instance):
        '''Create a component for the instance'''
        kwargs = self.kwargs.copy()
        kwargs['name'] = self.get_name(instance)

        sub_prefix = self.get_sub_prefix(instance)

        clsname = self.clsname
        if clsname is None:
            clsname = ''.join((instance.__class__.__name__,
                               self.attr.capitalize()))

        clsdict = dict(_sep=self.get_separator(instance),
                       __doc__='{} sub-device'.format(clsname),
                       )

        for defn in self.defns:
            for attr, (cls, suffix, kwargs) in defn.items():
                clsdict[attr] = Component(cls, suffix, **kwargs)

        cls = type(clsname, (OphydDevice, ), clsdict)
        return cls(sub_prefix, **self.kwargs)

    def __get__(self, instance, owner):
        if instance is None:
            return self

        if self.attr not in instance._signals:
            instance._signals[self.attr] = self.create_component(instance)

        return instance._signals[self.attr]

    def __set__(self, instance, owner):
        raise RuntimeError('Use .put()')

    @staticmethod
    def make_def(cls, field_name, suffix, range_, format_key='index',
                 **kwargs):
        defn = OrderedDict()
        for i in range_:
            fmt_dict = {format_key: i}
            attr = field_name.format(**fmt_dict)
            defn[attr] = (cls, suffix.format(**fmt_dict), kwargs)

        return defn


class ComponentMeta(type):
    '''Creates attributes for Components by inspecting class definition'''

    def __new__(cls, name, bases, clsdict):
        clsobj = super().__new__(cls, name, bases, clsdict)

        # map component attribute names to Component classes
        sig_dict = {attr: value for attr, value in clsdict.items()
                    if isinstance(value, (Component, DynamicComponent))}

        # maps component to attribute names
        clsobj._sig_attrs = {cpt: name
                             for name, cpt in sig_dict.items()}

        for cpt, attr in clsobj._sig_attrs.items():
            cpt.attr = attr

        # List Signal attribute names.
        clsobj.signal_names = list(sig_dict.keys())

        # Store EpicsSignal objects (only created once they are accessed)
        clsobj._signals = {}
        return clsobj


class DeviceBase(metaclass=ComponentMeta):
    """Base class for device objects

    This class provides attribute access to one or more Signals, which can be
    a mixture of read-only and writable. All must share the same base_name.
    """
    def __init__(self, prefix, read_signals=None):
        self.prefix = prefix
        if self.signal_names and prefix is None:
            raise ValueError('Must specify prefix if device signals are being '
                             'used')

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

    def read(self):
        # map names ("data keys") to actual values
        values = {}
        for name in self.read_signals:
            signal = getattr(self, name)
            values.update(signal.read())

        return values

    def describe(self):
        desc = {}
        for name in self.read_signals:
            signal = getattr(self, name)
            desc.update(signal.describe())

        return desc

    def stop(self):
        "to be defined by subclass"
        pass

    def trigger(self):
        "to be defined by subclass"
        pass


class OphydDevice(DeviceBase, OphydObject):
    SUB_ACQ_DONE = 'acq_done'  # requested acquire

    def __init__(self, prefix=None, read_signals=None,
                 name=None, alias=None):
        if name is None:
            name = prefix

        OphydObject.__init__(self, name=name, alias=alias)
        DeviceBase.__init__(self, prefix, read_signals=read_signals)

        # set should work using signature-stuff

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
