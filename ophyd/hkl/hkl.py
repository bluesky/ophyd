# vi: ts=4 sw=4 sts=4 expandtab
'''
:mod:`ophyd.utils.hkl` - HKL calculation utilities
==================================================

.. module:: ophyd.utils.hkl
   :synopsis:

'''

from __future__ import print_function
import logging
from collections import OrderedDict

import numpy as np

from .util import hkl_module, GLib
from . import util

logger = logging.getLogger(__name__)


class HklSample(object):
    def __init__(self, calc, sample=None, units='user', **kwargs):
        if sample is None:
            sample = hkl_module.Sample.new('')

        self._calc = calc
        self._sample = sample
        self._sample_dict = calc._samples

        self._unit_name = units
        try:
            self._units = util.units[self._unit_name]
        except KeyError:
            raise ValueError('Invalid unit type')

        for name in ('lattice', 'name', 'U', 'UB', 'ux', 'uy', 'uz',
                     'reflections', ):
            value = kwargs.pop(name, None)
            if value:
                try:
                    setattr(self, name, value)
                except Exception as ex:
                    # These kwargs are funneled down to the gi wrapper
                    # and could raise just about anything. Tack on the
                    # kwarg to help debugging if necessary:
                    ex.message = '%s (attribute=%s)' % (ex, name)
                    raise

        if kwargs:
            raise ValueError('Unsupported kwargs for HklSample: %s' %
                             tuple(kwargs.keys()))

    @property
    def hkl_calc(self):
        '''
        The HklCalc instance associated with the sample
        '''
        return self._calc

    @property
    def hkl_sample(self):
        '''
        The HKL library sample object
        '''
        return self._sample

    @property
    def name(self):
        """
        The name of the currently selected sample
        """
        return self._sample.name_get()

    @name.setter
    def name(self, new_name):
        """Replace the current sample

        Parameters
        ----------
        new_name : str
        """
        if new_name in self._sample_dict:
            raise ValueError('Sample with that name already exists')
        sample = self._sample
        old_name = sample.name_get()

        sample.name_set(new_name)

        del self._sample_dict[old_name]
        self._sample_dict[new_name] = self

    @property
    def reciprocal(self):
        '''
        The reciprocal lattice
        '''
        lattice = self._sample.lattice_get()
        reciprocal = lattice.copy()
        lattice.reciprocal(reciprocal)
        return reciprocal.get(self._units)

    @property
    def lattice(self):
        '''
        The lattice
        '''
        lattice = self._sample.lattice_get()
        lattice = lattice.get(self._units)

        a, b, c, alpha, beta, gamma = lattice
        return a, b, c, alpha, beta, gamma

    def _set_lattice(self, sample, lattice):
        if not isinstance(lattice, hkl_module.Lattice):
            a, b, c, alpha, beta, gamma = lattice

            lattice = hkl_module.Lattice.new(a, b, c, alpha, beta, gamma,
                                             self._units)

        sample.lattice_set(lattice)

        # TODO: notes mention that lattice should not change, but is it alright
        #       if init() is called again? or should reflections be cleared,
        #       etc?

    @lattice.setter
    def lattice(self, lattice):
        self._set_lattice(self._sample, lattice)

    @property
    def U(self):
        '''
        The crystal orientation matrix, U
        '''
        return util.to_numpy(self._sample.U_get())

    @U.setter
    def U(self, new_u):
        self._sample.U_set(util.to_hkl(new_u))

    def _get_parameter(self, param):
        return Parameter(param, units=self._unit_name)

    @property
    def ux(self):
        '''
        ux part of the U matrix
        '''
        return self._get_parameter(self._sample.ux_get())

    @property
    def uy(self):
        '''
        uy part of the U matrix
        '''
        return self._get_parameter(self._sample.uy_get())

    @property
    def uz(self):
        '''
        uz part of the U matrix
        '''
        return self._get_parameter(self._sample.uz_get())

    @property
    def UB(self):
        '''
        The UB matrix, where U is the crystal orientation matrix and B is the
        transition matrix of a non-orthonormal (the reciprocal of the crystal)
        in an orthonormal system

        If written to, the B matrix will be kept constant:
            U * B = UB -> U = UB * B^-1
        '''
        return util.to_numpy(self._sample.UB_get())

    @UB.setter
    def UB(self, new_ub):
        self._sample.UB_set(util.to_hkl(new_ub))

    def _create_reflection(self, h, k, l, detector=None):
        '''
        Create a new reflection with the current geometry/detector
        '''
        if detector is None:
            detector = self._calc._detector

        return hkl_module.SampleReflection.new(self._calc._geometry, detector,
                                               h, k, l)

    # TODO: this appears to affect the internal state? it also does not return
    #       a matrix, only an integer
    def _compute_UB(self, r1, r2):
        '''
        Using the Busing and Levy method, compute the UB matrix for two
        sample reflections, r1 and r2

        '''
        if not isinstance(r1, hkl_module.SampleReflection):
            r1 = self._create_reflection(*r1)
        if not isinstance(r2, hkl_module.SampleReflection):
            r2 = self._create_reflection(*r2)

        # return hkl_matrix_to_numpy(self._sample.compute_UB_busing_levy(r1, r2))
        return self._sample.compute_UB_busing_levy(r1, r2)

    @property
    def reflections(self):
        '''
        All reflections for the current sample in the form:
            [(h, k, l), ...]
        '''
        return [refl.hkl_get() for refl in self._sample.reflections_get()]

    @reflections.setter
    def reflections(self, refls):
        self.clear_reflections()
        for refl in refls:
            self.add_reflection(*refl)

    def add_reflection(self, h, k, l, detector=None):
        '''
        Add a reflection, optionally specifying the detector to use
        '''
        if detector is None:
            detector = self._calc._detector

        return self._sample.add_reflection(self._calc._geometry, detector,
                                           h, k, l)

    def remove_reflection(self, refl):
        '''
        Remove a specific reflection
        '''
        if not isinstance(refl, hkl_module.SampleReflection):
            index = self.reflections.index(refl)
            refl = self._sample.reflections_get()[index]

        return self._sample.del_reflection(refl)

    def clear_reflections(self):
        '''
        Clear all reflections for the current sample
        '''
        reflections = self._sample.reflections_get()
        for refl in reflections:
            self._sample.del_reflection(refl)

    def _refl_matrix(self, fcn):
        '''
        Get a reflection angle matrix
        '''
        sample = self._sample
        refl = sample.reflections_get()
        refl_matrix = np.zeros((len(refl), len(refl)))

        for i, r1 in enumerate(refl):
            for j, r2 in enumerate(refl):
                if i != j:
                    refl_matrix[i, j] = fcn(r1, r2)

        return refl_matrix

    @property
    def reflection_measured_angles(self):
        # TODO: typo bug report (mesured)
        return self._refl_matrix(self._sample.get_reflection_measured_angle)

    @property
    def reflection_theoretical_angles(self):
        return self._refl_matrix(self._sample.get_reflection_theoretical_angle)

    def affine(self):
        '''
        Make the sample transform affine
        '''
        return self._sample.affine()

    def _repr_info(self):
        repr = ['name={!r}'.format(self.name),
                'lattice={!r}'.format(self.lattice),
                'ux={!r}'.format(self.ux),
                'uy={!r}'.format(self.uy),
                'uz={!r}'.format(self.uz),
                'U={!r}'.format(self.U),
                'UB={!r}'.format(self.UB),
                'reflections={!r}'.format(self.reflections),
                ]

        return repr

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__,
                               ', '.join(self._repr_info()))

    def __str__(self):
        info = self._repr_info()
        info.append('reflection_measured_angles={!r}'.format(self.reflection_measured_angles))
        info.append('reflection_theoretical_angles={!r}'.format(self.reflection_theoretical_angles))
        return '{}({})'.format(self.__class__.__name__,
                               ', '.join(info))


class Parameter(object):
    def __init__(self, param, units='user'):
        self._param = param
        # Sets unit_name and units through the setter:
        self.units = units

    @property
    def hkl_parameter(self):
        '''
        The HKL library parameter object
        '''
        return self._param

    @property
    def units(self):
        return self._unit_name

    @units.setter
    def units(self, unit_name):
        self._unit_name = unit_name
        self._units = util.units[unit_name]

    @property
    def name(self):
        return self._param.name_get()

    @property
    def value(self):
        return self._param.value_get(self._units)

    @property
    def user_units(self):
        '''
        A string representing the user unit type
        '''
        return self._param.user_unit_get()

    @property
    def default_units(self):
        '''
        A string representing the default unit type
        '''
        return self._param.default_unit_get()

    @value.setter
    def value(self, value):
        self._param.value_set(value, self._units)

    @property
    def fit(self):
        '''
        True if the parameter can be fit or not
        '''
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
        return self._geometry.axis_values_get(self.units)

    @property
    def units(self):
        return self._engine.units

    def select(self):
        self._engine._engine_list.select_solution(self._list_item)

    def _repr_info(self):
        repr = ['{!r}'.format(self.axis_values),
                'units={!r}'.format(self.units),
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
        '''
        HKL calculation mode (see also `HklCalc.modes`)
        '''
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
        '''
        Calculate the pseudo axis positions from the real axis positions
        '''
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
        return self._engine.pseudo_axis_values_get(self.units)

    @property
    def pseudo_axes(self):
        return OrderedDict(zip(self.pseudo_axis_names,
                               self.pseudo_axis_values))

    @pseudo_axis_values.setter
    def pseudo_axis_values(self, values):
        try:
            geometry_list = self._engine.pseudo_axis_values_set(values,
                                                                self.units)
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
        return self._calc._units

    @property
    def engine(self):
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
