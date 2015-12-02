from collections import OrderedDict


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
            return

        if self.attr not in instance._signals:
            instance._signals[self.attr] = self.create_component(instance)

        return instance._signals[self.attr]

    def __set__(self, instance, owner):
        raise RuntimeError('Use .put()')


# class DynamicComponent:
#     @staticmethod
#     def make_def(cls, field_name, suffix, range_, format_key='index'):
#         defn = OrderedDict()
#         for i in range_:
#             fmt_dict = dict(format_key=i)
#             _field = field_name.format(**fmt_dict)
#             _suffix = suffix.format(**fmt_dict)
#             defn[field_name] = (cls, _field, suffix)
