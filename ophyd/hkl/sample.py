from __future__ import print_function
import logging

import numpy as np

from .engine import Parameter
from .util import hkl_module
from . import util


logger = logging.getLogger(__name__)


class HklSample(object):
    def __init__(self, calc, sample=None, units='user', **kwargs):
        '''Represents a sample in diffractometer calculations

        Parameters
        ----------
        calc : instance of CalcRecip
            Reciprocal space calculation class
        name : str
            A user-defined name used to refer to the sample
        sample : Hkl.Sample, optional
            A Sample instance from the wrapped Hkl library. Created
            automatically if not specified.
        units : {'user', 'default'}
            Units to use
        lattice : np.ndarray, optional
            The lattice
        U : np.ndarray, optional
            The crystal orientation matrix, U
        UB : np.ndarray, optional
            The UB matrix, where U is the crystal orientation matrix and B is
            the transition matrix of a non-orthonormal (the reciprocal of the
            crystal) in an orthonormal system
        ux : np.ndarray, optional
            ux part of the U matrix
        uy : np.ndarray, optional
            uy part of the U matrix
        uz : np.ndarray, optional
            uz part of the U matrix
        reflections :
            All reflections for the current sample in the form:
                [(h, k, l), ...]
            This assumes the hkl engine is used; generally, the ordered set of
            positions for the engine in-use should be specified.
        '''

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
            if value is not None:
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

    @lattice.setter
    def lattice(self, lattice):
        self._set_lattice(self._sample, lattice)
        if not isinstance(lattice, hkl_module.Lattice):
            a, b, c, alpha, beta, gamma = lattice

            lattice = hkl_module.Lattice.new(a, b, c, alpha, beta, gamma,
                                             self._units)

        self._sample.lattice_set(lattice)

        # TODO: notes mention that lattice should not change, but is it alright
        #       if init() is called again? or should reflections be cleared,
        #       etc?

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
