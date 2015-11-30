# from ..utils.epics_pvs import raise_if_disconnected
# from ..utils.errors import DisconnectedError
from .signal import (EpicsSignal, SignalGroup)
# from .signal import EpicsSignalRO


class DevSignal:
    '''A descriptor representing a device signal

    Parameters
    ----------
    suffix : str
        The PV suffix, which gets appended onto the device prefix
    write_suffix : str, optional
        If specified, a separate setpoint signal is created with this suffix
    lazy : bool, optional
        Lazily instantiate the signal. If False, the signal will be instantiated
        upon object instantiation
    trigger_value : any, optional
        Mark as a signal to be set on trigger. The value is sent to the signal
        at trigger time.
    '''
    # TODO: lazy/essential/what?
    writable = True
    cls = EpicsSignal

    def __init__(self, suffix, write_suffix=None, lazy=False,
                 trigger_value=None, attr=None, format_kw=None, **kwargs):
        self.suffix = suffix
        self.write_suffix = write_suffix
        self.kwargs = kwargs
        self.lazy = lazy
        self.trigger_value = trigger_value

        # attr is set later when known
        self.attr = attr

        if format_kw is None:
            format_kw = {}

        self.format_kw = format_kw

    def get_pv_name(self, instance, suffix):
        '''Get pv name for a given suffix'''
        return ''.join((instance.prefix,
                        suffix.format(**self.format_kw)))

    def get_name(self, instance):
        '''Get a name for the device signal'''
        try:
            return self.kwargs['name']
        except KeyError:
            return self.get_pv_name(instance, self.suffix)

    def get_alias(self, instance):
        '''Get an alias for the device signal'''
        alias = self.kwargs.get('alias', self.attr)
        return '{}.{}'.format(instance.alias, alias)

    def create_signal(self, instance):
        '''Create a signal for the instance'''
        kwargs = self.kwargs.copy()
        kwargs.update(dict(name=self.get_name(instance),
                           alias=self.get_alias(instance)))

        read_pv = self.get_pv_name(instance, self.suffix)
        write_pv = None
        if self.write_suffix is not None:
            write_pv = self.get_pv_name(instance, self.write_suffix)
        return self.cls(read_pv=read_pv, write_pv=write_pv, **kwargs)

    def __get__(self, instance, owner):
        if instance is None:
            return

        if self.attr not in instance._signals:
            instance._signals[self.attr] = self.create_signal(instance)

        return instance._signals[self.attr]

    def __set__(self, instance, owner):
        raise RuntimeError('Use signal.put()')


class DevSignalRO(DevSignal):
    '''Read-only device signal'''
    writable = False

    def __init__(self, read_suffix, **kwargs):
        super().__init__(read_suffix, write_suffix=None, rw=False,
                         **kwargs)


class AdDevSignal(DevSignal):
    def __init__(self, suffix, **kwargs):
        super().__init__(suffix + '_RBV', write_suffix=suffix, lazy=True,
                         **kwargs)


class AdDevSignalRO(DevSignalRO):
    def __init__(self, read_suffix, **kwargs):
        super().__init__(read_suffix, **kwargs)


class DevSignalArray:
    cls = EpicsSignal
    group_cls = SignalGroup

    def __init__(self, cls, suffix, **kwargs):
        self.kwargs = kwargs
        # self.cls = cls
        self.lazy = True
        self.suffix = suffix
        self.trigger_value = None

    def get_name(self, instance, format_kw):
        '''Get a name for the device signal'''
        try:
            return self.kwargs['name']
        except KeyError:
            return self.get_pv_name(instance, self.suffix)

    def get_alias(self, instance):
        '''Get an alias for the device signal'''
        alias = self.kwargs.get('alias', self.attr)
        return '{}.{}'.format(instance.alias, alias)

    def create_signal(self, instance, format_kw, kwargs):
        '''Create a signal on the instance, with specific kwargs

        Parameters
        ----------
        format_kw : dict
            Used to format the pv_name (pv_name.format(**format_kw))
        kwargs : dict
            Keyword arguments for the signal initializer
        '''
        pv_name = ''.join((instance.prefix,
                           self.suffix.format(**format_kw)))

        kwargs = kwargs.copy()
        name = kwargs.pop('name', pv_name)
        alias = kwargs.pop('alias', '{}_{}'.format(self.attr,
                                                   format_kw['index']))

        signal = self.cls(pv_name, name=name, alias=alias, **kwargs)
        return format_kw['index'], signal

    def __get__(self, instance, owner):
        if instance is None:
            return

        # get should return an indexable list
        if self.attr not in instance._signals:
            # instance._signals[self.attr] = DevList(self)
            instance._signals[self.attr] = group = self.group_cls()
            for format_kw, obj_kw in self.get_kwlist(instance):
                index, sig = self.create_signal(instance, format_kw,
                                                self.kwargs)
                group.add_signal(sig, index=index)

        return instance._signals[self.attr]

    def __set__(self, instance, owner):
        raise RuntimeError('Use signals[index].put()')

    def get_kwlist(self, instance):
        '''Get the formatting keyword list

        For each dictionary returned here, a signal will be created

        Yields a list of (format_kwarg, class_kwargs) pairs
        '''
        raise NotImplementedError()


class DevSignalRange(DevSignalArray):
    def __init__(self, cls, *args, **kwargs):
        self.range_ = kwargs.pop('range_', None)
        super().__init__(cls, *args, **kwargs)

    def get_kwlist(self, instance):
        '''Get the formatting keyword list

        Yields a list of (format_kwarg, class_kwargs) pairs
        '''

        range_ = self.range_
        # if callable(range) calculate on access/instantiation
        if callable(range_):
            range_ = range_(instance, self)

        for index in range_:
            yield dict(index=index), self.kwargs
