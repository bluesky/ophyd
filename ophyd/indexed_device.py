import collections
import copy
import itertools
import string

from .device import Device, Component, Kind, create_device_from_components
from .utils import underscores_to_camel_case


class _IndexedChildLevel(collections.abc.Mapping):
    'A mapping helper to allow access of IndexedDevice[idx][idx2...]'
    def __init__(self, device, mapping_dict):
        self._device = device
        self._d = mapping_dict

    def __getitem__(self, item):
        value = self._d[item]
        if isinstance(value, str):
            return getattr(self._device, value)
        return _IndexedChildLevel(device=self._device, mapping_dict=value)

    def __iter__(self):
        yield from self._d

    def __len__(self):
        return len(self._d)

    def __repr__(self):
        options = set(str(s) for s in self)
        return f'<{self.__class__.__name__} len={len(self)} options={options}>'


class IndexedDevice(Device, collections.abc.Mapping):
    '''
    A Device subclass which allows for indexing of components (e.g., channels)
    by using the getitem syntax (i.e., ``dev[idx]``)
    '''

    def __init__(self, prefix='', *, name, kind=None, read_attrs=None,
                 configuration_attrs=None, parent=None, **kwargs):
        self._root_index = _IndexedChildLevel(
            self, mapping_dict=self._mapping_dict)
        super().__init__(prefix=prefix, name=name, kind=kind,
                         read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs,
                         parent=parent, **kwargs)

    def _instantiate_component(self, attr):
        cpt = super()._instantiate_component(attr)
        # Patch in the index on the component for reverse lookups:
        cpt.index = self._attr_to_index[attr]
        return cpt

    def __getitem__(self, index):
        return self._root_index[index]

    def __iter__(self):
        yield from self._root_index

    def __len__(self):
        return len(self._root_index)


def _normalize_ranges(ranges):
    'Normalize a range/str to be used with _apply_range_to_value'
    if isinstance(ranges, (range, str)):
        return [list(ranges)]

    return [list(ri) for ri in ranges]


def _apply_range_to_value(ranges, value):
    'Get all values from a format string and the given range(s)'
    return [
        value.format(*item)
        for item in itertools.product(*ranges)
    ]


def _mapping_dict_from_ranges(ranges, attrs, *, tuple_access=True):
    'Create a dictionary to be used by _IndexedChildLevel'
    mapping_dict = {}

    for index, attr in zip(itertools.product(*ranges), attrs):
        d = mapping_dict
        for index_part in index[:-1]:
            if index_part not in d:
                d[index_part] = {}
            d = d[index_part]

        d[index[-1]] = attr

        if tuple_access:
            mapping_dict[index] = attr

    return mapping_dict


def _verify_with_formatter(formatter, format_str, num_args):
    'Verify a format string with the given formatter'
    parsed = list(formatter.parse(format_str))
    unnamed_fields = [
        field_name
        for literal_text, field_name, format_spec, conversion in parsed
        if field_name == ''
    ]
    if len(unnamed_fields) != num_args:
        raise ValueError(
            f'Expected a format string that would accept {num_args} args, but '
            f'got one that takes {len(unnamed_fields)} args in string: '
            f'{format_str!r}'
        )

    named_fields = [
        field_name
        for literal_text, field_name, format_spec, conversion in parsed
        if field_name
    ]
    if named_fields:
        named_fields = ', '.join(named_fields)
        raise ValueError(
            f'Expected a format string that would accept {num_args} args, but '
            f'got one that takes named fields {named_fields}: {format_str!r}'
        )


class IndexedComponent(Component):
    '''
    A Device component that dynamically creates a sub Device

    Parameters
    ----------
    attr : str
        The attribute format to use
    suffix:
        The suffix format to use
    ranges: str, range, or list of iterables
        A single range of numbers to expand attr and suffix. For example::

            ranges=range(10)

        Or, a list of ranges or iterables, from which individual indexed
        components will be created by taking the cartesian product of all
        items, for example::

            ranges=[range(2), 'AB']

        will be expanded to::

            [(0, 'A'), (0, 'B'), (1, 'A'), (1, 'B')]

        The definition of all attributes to be created is based on the above.
        Assuming component_class is Component, the following pseudo-code
        shows what would happen on the Device::

            for attr, suffix in expand_attr_and_suffix(ranges):
                attr = Component(SignalClass, _suffix, **keyword_arg_dict)

    allow_tuple_access : bool, optional
        Normally, accessing components with __getitem__ would be done on
        each level individually::

            dev[0]['A']

        Enabling this flag would allow for accessing the same component as
        follows::

            dev[(0, 'A')]

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
    '''

    # Allow for subclasses to override the formatting verifier:
    _formatter = string.Formatter()

    def __init__(self, cls, *, attr, suffix, ranges, clsname=None,
                 doc=None, kind=Kind.normal, default_read_attrs=None,
                 default_configuration_attrs=None, base_class=None,
                 component_class=Component, allow_tuple_access=False,
                 **kwargs):

        if isinstance(default_read_attrs, collections.abc.Iterable):
            default_read_attrs = tuple(default_read_attrs)

        if isinstance(default_configuration_attrs, collections.abc.Iterable):
            default_configuration_attrs = tuple(default_configuration_attrs)

        ranges = _normalize_ranges(ranges)

        _verify_with_formatter(self._formatter, suffix, num_args=len(ranges))
        suffixes = _apply_range_to_value(ranges, suffix)

        _verify_with_formatter(self._formatter, attr, num_args=len(ranges))
        attrs = _apply_range_to_value(ranges, attr)

        self.attr_to_suffix = dict(zip(attrs, suffixes))

        self.mapping_dict = _mapping_dict_from_ranges(
            ranges, attrs, tuple_access=allow_tuple_access)

        self.attr_to_index = dict(zip(attrs, itertools.product(*ranges)))

        self.allow_tuple_access = allow_tuple_access
        self.attr = attr
        self.base_class = base_class or IndexedDevice
        self.clsname = clsname
        self.component_class = component_class
        self.default_configuration_attrs = default_configuration_attrs
        self.default_read_attrs = default_read_attrs
        self.kwargs = kwargs
        self.ranges = ranges
        self.suffix = suffix

        self.components = {
            attr: component_class(cls, suffix_, **kwargs)
            for attr, suffix_ in self.attr_to_suffix.items()
        }

        # NOTE: cls is None here, as it gets created in __set_name__, below
        super().__init__(cls=None, suffix='', lazy=False, kind=kind)

        # Allow easy access to all generated components directly in the
        # IndexedComponent instance
        for attr, cpt in self.components.items():
            if not hasattr(self, attr):
                setattr(self, attr, cpt)

    def __getnewargs_ex__(self):
        'Get arguments needed to copy this class (used for pickle/copy)'
        kwargs = dict(
            attr=self.attr, suffix=self.suffix, ranges=self.ranges,
            allow_tuple_access=self.allow_tuple_access, clsname=self.clsname,
            doc=self.doc, kind=self.kind,
            default_read_attrs=self.default_read_attrs,
            default_configuration_attrs=self.default_configuration_attrs,
            component_class=self.component_class, base_class=self.base_class
        )
        return ((self.cls, ), kwargs)

    def __set_name__(self, owner, attr_name):
        if self.clsname is None:
            self.clsname = underscores_to_camel_case(attr_name)
        super().__set_name__(owner, attr_name)
        clsdict = dict(
            _mapping_dict=copy.deepcopy(self.mapping_dict),
            _attr_to_index=dict(self.attr_to_index),
        )
        self.cls = create_device_from_components(
            self.clsname, default_read_attrs=self.default_read_attrs,
            default_configuration_attrs=self.default_configuration_attrs,
            base_class=self.base_class, clsdict=clsdict,
            **self.components)

    def __repr__(self):
        return '\n'.join(f'{attr} = {cpt!r}'
                         for attr, cpt in self.components.items()
                         )

    def subscriptions(self, event_type):
        raise NotImplementedError('IndexedComponent does not yet '
                                  'support decorator subscriptions')
