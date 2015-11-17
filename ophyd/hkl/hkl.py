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

from ..controls import (Signal, PseudoPositioner)
from .util import hkl_module, GLib
from . import util

logger = logging.getLogger(__name__)
NM_KEV = 1.239842  # lambda = 1.24 / E (nm, keV or um, eV)


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


class CalcRecip(object):
    def __init__(self, dtype, engine='hkl',
                 sample='main', lattice=None,
                 degrees=True, units='user',
                 lock_engine=False):

        self._engine = None  # set below with property
        self._detector = util.new_detector()
        self._degrees = bool(degrees)
        self._sample = None
        self._samples = {}
        self._unit_name = units
        self._units = util.units[self._unit_name]
        self._lock_engine = bool(lock_engine)

        try:
            self._factory = hkl_module.factories()[dtype]
        except KeyError:
            types = ', '.join(util.diffractometer_types)
            raise ValueError('Invalid diffractometer type {!r}; choose from: {}'
                             ''.format(dtype, types))

        self._geometry = self._factory.create_new_geometry()
        self._engine_list = self._factory.create_new_engine_list()

        if sample is not None:
            self.add_sample(sample, lattice=lattice)

        self.engine = engine

    @property
    def wavelength(self):
        '''
        The wavelength associated with the geometry, in nm
        '''
        # TODO hkl lib doesn't expose the getter, only the setter
        return self._geometry.wavelength_get(self._units)

    @wavelength.setter
    def wavelength(self, wavelength):
        self._geometry.wavelength_set(wavelength, self._units)

    @property
    def energy(self):
        '''
        The energy associated with the geometry, in keV
        '''
        return NM_KEV / self.wavelength

    @energy.setter
    def energy(self, energy):
        self.wavelength = NM_KEV / energy

    @property
    def engine_locked(self):
        '''
        If set, do not allow the engine to be changed post-initialization
        '''
        return self._lock_engine

    @property
    def engine(self):
        return self._engine

    @engine.setter
    def engine(self, engine):
        if engine is self._engine:
            return

        if self._lock_engine and self._engine is not None:
            raise ValueError('Engine is locked on this %s instance' %
                             self.__class__.__name__)

        if isinstance(engine, hkl_module.Engine):
            self._engine = engine
        else:
            engines = self.engines
            try:
                self._engine = engines[engine]
            except KeyError:
                raise ValueError('Unknown engine name or type')

        self._re_init()

    def _get_sample(self, name):
        if isinstance(name, hkl_module.Sample):
            return name

        return self._samples[name]

    @property
    def sample_name(self):
        '''
        The name of the currently selected sample
        '''
        return self._sample.name_get()

    @sample_name.setter
    def sample_name(self, new_name):
        sample = self._sample
        sample.name = new_name

    @property
    def sample(self):
        return self._sample

    @sample.setter
    def sample(self, sample):
        if sample is self._sample:
            return
        elif sample == self._sample.name:
            return

        if isinstance(sample, HklSample):
            if sample not in self._samples.values():
                self.add_sample(sample, select=False)
        elif sample in self._samples:
            name = sample
            sample = self._samples[name]
        else:
            raise ValueError('Unknown sample type (expected HklSample)')

        self._sample = sample
        self._re_init()

    def add_sample(self, name, select=True,
                   **kwargs):
        if isinstance(name, hkl_module.Sample):
            sample = HklSample(self, name, units=self._unit_name,
                               **kwargs)
        elif isinstance(name, HklSample):
            sample = name
        else:
            sample = HklSample(self, sample=hkl_module.Sample.new(name),
                               units=self._unit_name,
                               **kwargs)

        if sample.name in self._samples:
            raise ValueError('Sample of name "%s" already exists' % name)

        self._samples[sample.name] = sample
        if select:
            self._sample = sample
            self._re_init()

        return sample

    def _re_init(self):
        if self._engine is None:
            return

        if self._geometry is None or self._detector is None or self._sample is None:
            # raise ValueError('Not all parameters set (geometry, detector, sample)')
            pass
        else:
            self._engine_list.init(self._geometry, self._detector,
                                   self._sample.hkl_sample)

    @property
    def engines(self):
        return dict((engine.name_get(), Engine(self, engine, self._engine_list))
                    for engine in self._engine_list.engines_get())

    @property
    def parameters(self):
        return self._engine.parameters

    @property
    def physical_axis_names(self):
        return self._geometry.axis_names_get()

    @property
    def physical_axis_values(self):
        return self._geometry.axis_values_get(self._units)

    @physical_axis_values.setter
    def physical_axis_values(self, positions):
        return self._geometry.axis_values_set(positions, self._units)

    @property
    def physical_axes(self):
        keys = self.physical_axis_names
        values = self.physical_axis_values
        return OrderedDict(zip(keys, values))

    @property
    def pseudo_axis_names(self):
        '''Pseudo axis names from the current engine'''
        return self._engine.pseudo_axis_names

    @property
    def pseudo_axis_values(self):
        '''Pseudo axis positions/values from the current engine'''
        return self._engine.pseudo_axis_values

    @property
    def pseudo_axes(self):
        '''Dictionary of axis name to position'''
        return self._engine.pseudo_axes

    def update(self):
        '''
        Calculate the pseudo axis positions from the real axis positions
        '''
        return self._engine.update()

    def _get_parameter(self, param):
        return Parameter(param, units=self._unit_name)

    def __getitem__(self, axis):
        if axis in self.physical_axis_names:
            return self._get_parameter(self._geometry.axis_get(axis))
        elif axis in self.pseudo_axis_names:
            return self._engine[axis]

    def __setitem__(self, axis, value):
        if axis in self.physical_axis_names:
            param = self[axis]
            param.value = value
        elif axis in self.pseudo_axis_names:
            self._engine[axis] = value

    def calc(self, position, engine=None,
             use_first=False):
        # TODO default should probably not be `use_first` (or remove
        # completely?)
        with self.using_engine(engine):
            if self.engine is None:
                raise ValueError('Engine unset')

            engine = self.engine
            self.engine.pseudo_axis_values = position

            solutions = self.engine.solutions

            if use_first:
                # just use the first solution
                solutions[0].select()

            return solutions

    def using_engine(self, engine):
        return util.UsingEngine(self, engine)

    def calc_linear_path(self, start, end, n, num_params=0, **kwargs):
        # start = [h1, k1, l1]
        # end   = [h2, k2, l2]

        # from start to end, in a linear path
        singles = [np.linspace(start[i], end[i], n + 1)
                   for i in range(num_params)]

        return list(zip(*singles))

    def _get_path_fcn(self, path_type):
        try:
            return getattr(self, 'calc_%s_path' % (path_type))
        except AttributeError:
            raise ValueError('Invalid path type specified (%s)' % path_type)

    def get_path(self, start, end=None, n=100,
                 path_type='linear', **kwargs):
        num_params = len(self.pseudo_axis_names)

        start = np.array(start)

        path_fcn = self._get_path_fcn(path_type)

        if end is not None:
            end = np.array(end)
            if start.size == end.size == num_params:
                return path_fcn(start, end, n, num_params=num_params,
                                **kwargs)

        else:
            positions = np.array(start)
            if positions.ndim == 1 and positions.size == num_params:
                # single position
                return [list(positions)]
            elif positions.ndim == 2:
                if positions.shape[0] == 1 and positions.size == num_params:
                    # [[h, k, l], ]
                    return [positions[0]]
                elif positions.shape[0] == num_params:
                    # [[h, k, l], [h, k, l], ...]
                    return [positions[i, :] for i in range(num_params)]

        raise ValueError('Invalid set of %s positions' %
                         ', '.join(self.pseudo_axis_names))

    def __call__(self, start, end=None, n=100, engine=None,
                 path_type='linear', **kwargs):

        with self.using_engine(engine):
            for pos in self.get_path(start, end=end, n=n,
                                     path_type=path_type, **kwargs):
                yield self.calc(pos, engine=None,
                                **kwargs)

    def _repr_info(self):
        repr = ['engine={!r}'.format(self.engine.name),
                'detector={!r}'.format(self._detector),
                'sample={!r}'.format(self._sample),
                'samples={!r}'.format(self._samples),
                ]

        return repr

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__,
                               ', '.join(self._repr_info()))

    def __str__(self):
        info = self._repr_info()
        return '{}({})'.format(self.__class__.__name__,
                               ', '.join(info))


class Diffractometer(PseudoPositioner):
    calc_class = None

    def __init__(self, name, real_positioners, calc_kw=None,
                 decision_fcn=None, energy_signal=None, energy=8.0,
                 calc_inst=None,
                 **kwargs):

        if calc_inst is not None:
            if not isinstance(calc_inst, self.calc_class):
                raise ValueError('Calculation instance must be derived from '
                                 'the class {}'.format(self.calc_class))
            self._calc = calc_inst

        else:
            if calc_kw is None:
                calc_kw = {}

            calc_kw = dict(calc_kw)
            self._calc = self.calc_class(lock_engine=True, **calc_kw)

        if not self._calc.engine_locked:
            # Reason for this is that the engine determines the pseudomotor
            # names, so if the engine is switched from underneath, the
            # pseudomotor will no longer function properly
            raise ValueError('Calculation engine must be locked'
                             ' (CalcDiff.lock_engine set)')

        pseudo_axes = self._calc.pseudo_axes
        pseudo_names = list(pseudo_axes.keys())

        self._decision_fcn = decision_fcn

        super().__init__(name, real_positioners,
                         forward=self.pseudo_to_real,
                         reverse=self.real_to_pseudo, pseudo=pseudo_names,
                         **kwargs)

        if energy_signal is None:
            energy_signal = Signal(name='%s.energy' % self.name)
        else:
            # For pre-existing signals, don't update the energy upon
            # initialization
            energy = None

        self._energy_sig = energy_signal

        self._energy_sig.subscribe(self._energy_changed,
                                   event_type=Signal.SUB_VALUE)

        if energy is not None:
            self._energy_sig.put(float(energy))

    @property
    def energy(self):
        '''
        Energy in keV
        '''
        return self._energy_sig.value

    @energy.setter
    def energy(self, energy):
        self._energy_sig.put(float(energy))

    def _energy_changed(self, value=None, **kwargs):
        '''
        Callback indicating that the energy signal was updated
        '''
        energy = value

        logger.debug('{.name} energy changed: {}'.format(self, value))
        self._calc.energy = energy
        self._update_position()

    @property
    def calc(self):
        return self._calc

    @property
    def engine(self):
        return self._calc.engine

    # TODO so these calculations change the internal state of the hkl
    # calculation class, which is probably not a good thing -- it becomes a
    # problem when someone uses these functions outside of move()

    def pseudo_to_real(self, **pseudo):
        position = [pseudo[name] for name in self._pseudo_names]
        solutions = self._calc.calc(position)

        logger.debug('pseudo to real: {}'.format(solutions))

        if self._decision_fcn is not None:
            return self._decision_fcn(position, solutions)
        else:
            solutions[0].select()
            return solutions[0].axis_values

    def real_to_pseudo(self, **real):
        calc = self._calc
        for name, pos in real.items():
            calc[name] = pos

        calc.update()

        logger.debug('real to pseudo: {}'.format(calc.pseudo_axis_values))
        return calc.pseudo_axis_values

        # finally:
        #     # Restore the old state
        #     for name, pos in old_positions.items():
        #         calc[name] = pos
