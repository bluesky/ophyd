# vi: ts=4 sw=4 sts=4 expandtab

from __future__ import print_function
import logging
from collections import OrderedDict

from .util import GLib
from . import util

logger = logging.getLogger(__name__)


class Parameter(object):
    def __init__(self, param, units='user'):
        self._param = param
        self._unit_name = units
        self._units = util.units[units]

    @property
    def hkl_parameter(self):
        '''The HKL library parameter object'''
        return self._param

    @property
    def units(self):
        return self._unit_name

    @property
    def name(self):
        return self._param.name_get()

    @property
    def value(self):
        return self._param.value_get(self._units)

    @property
    def user_units(self):
        '''A string representing the user unit type'''
        return self._param.user_unit_get()

    @property
    def default_units(self):
        '''A string representing the default unit type'''
        return self._param.default_unit_get()

    @value.setter
    def value(self, value):
        self._param.value_set(value, self._units)

    @property
    def fit(self):
        '''True if the parameter can be fit or not'''
        return bool(self._param.fit_get())

    @fit.setter
    def fit(self, fit):
        self._param.fit_set(int(fit))

    @property
    def limits(self):
        return self._param.min_max_get(self._units)

    @limits.setter
    def limits(self, lims):
        low, high = lims
        self._param.min_max_set(low, high, self._units)

    def _repr_info(self):
        repr = ['name={!r}'.format(self.name),
                'limits={!r}'.format(self.limits),
                'value={!r}'.format(self.value),
                'fit={!r}'.format(self.fit),
                ]

        if self._unit_name == 'user':
            repr.append('units={!r}'.format(self.user_units))
        else:
            repr.append('units={!r}'.format(self.default_units))

        return repr

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__,
                               ', '.join(self._repr_info()))

    def __str__(self):
        info = self._repr_info()
        # info.append(self.)
        return '{}({})'.format(self.__class__.__name__,
                               ', '.join(info))


class Solution(object):
    def __init__(self, engine, list_item):
        self._list_item = list_item.copy()
        self._geometry = list_item.geometry_get().copy()
        self._engine = engine

    def __getitem__(self, axis):
        return self._geometry.axis_get(axis)

    @property
    def axis_names(self):
        return self._geometry.axis_names_get()

    @property
    def axis_values(self):
        return self._geometry.axis_values_get(self._engine._units)

    @property
    def units(self):
        return self._engine.units

    def select(self):
        self._engine._engine_list.select_solution(self._list_item)

    def _repr_info(self):
        repr = ['{!r}'.format(self.axis_values),
                'units={!r}'.format(self._engine.units),
                ]

        return repr

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__,
                               ', '.join(self._repr_info()))


class Engine(object):
    def __init__(self, calc, engine, engine_list):
        self._calc = calc
        self._engine = engine
        self._engine_list = engine_list
        self._solutions = None

    @property
    def name(self):
        return self._engine.name_get()

    @property
    def mode(self):
        '''HKL calculation mode (see also `HklCalc.modes`)'''
        return self._engine.current_mode_get()

    @mode.setter
    def mode(self, mode):
        if mode not in self.modes:
            raise ValueError('Unrecognized mode %r; '
                             'choose from: %s' % (mode, ', '.join(self.modes))
                             )

        return self._engine.current_mode_set(mode)

    @property
    def modes(self):
        return self._engine.modes_names_get()

    @property
    def solutions(self):
        return tuple(self._solutions)

    def update(self):
        '''Calculate the pseudo axis positions from the real axis positions'''
        # TODO: though this works, maybe it could be named better on the hkl
        # side? either the 'get' function name or the fact that the EngineList
        # is more than just a list...

        self._engine_list.get()

    @property
    def parameters(self):
        # TODO using additional engine parameters easily
        return self._engine.parameters_names_get()

    @property
    def pseudo_axis_names(self):
        return self._engine.pseudo_axis_names_get()

    @property
    def pseudo_axis_values(self):
        return self._engine.pseudo_axis_values_get(self._units)

    @property
    def pseudo_axes(self):
        return OrderedDict(zip(self.pseudo_axis_names,
                               self.pseudo_axis_values))

    @pseudo_axis_values.setter
    def pseudo_axis_values(self, values):
        try:
            geometry_list = self._engine.pseudo_axis_values_set(values,
                                                                self._units)
        except GLib.GError as ex:
            raise ValueError('Calculation failed (%s)' % ex)

        self._solutions = [Solution(self, item)
                           for item in geometry_list.items()]

    def __getitem__(self, name):
        try:
            return self.pseudo_axes[name]
        except KeyError:
            raise ValueError('Unknown axis name: %s' % name)

    def __setitem__(self, name, value):
        values = self.pseudo_axis_values
        try:
            idx = self.pseudo_axis_names.index(name)
        except IndexError:
            raise ValueError('Unknown axis name: %s' % name)

        values[idx] = float(value)
        self.pseudo_axis_values = values

    @property
    def units(self):
        '''The units used for calculations'''
        return self._calc.units

    @property
    def _units(self):
        '''The (internal) units used for calculations'''
        return self._calc._units

    @property
    def engine(self):
        '''The calculation engine'''
        return self._engine

    def _repr_info(self):
        repr = ['parameters={!r}'.format(self.parameters),
                'pseudo_axes={!r}'.format(dict(self.pseudo_axes)),
                'mode={!r}'.format(self.mode),
                'modes={!r}'.format(self.modes),
                'units={!r}'.format(self.units),
                ]

        return repr

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__,
                               ', '.join(self._repr_info()))
