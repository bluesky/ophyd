import logging
from collections import (OrderedDict, namedtuple)

import numpy as np

from .engine import (Engine, Parameter)
from .sample import HklSample
from . import util
from .util import hkl_module

logger = logging.getLogger(__name__)

NM_KEV = 1.239842  # lambda = 1.24 / E (nm, keV or um, eV)


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
            if isinstance(sample, HklSample):
                if lattice is not None:
                    sample.lattice = lattice
                self.add_sample(sample)
            else:
                self.new_sample(sample, lattice=lattice)

        self.engine = engine

    @property
    def wavelength(self):
        '''The wavelength associated with the geometry, in nm'''
        # TODO hkl lib doesn't expose the getter, only the setter
        return self._geometry.wavelength_get(self._units)

    @wavelength.setter
    def wavelength(self, wavelength):
        self._geometry.wavelength_set(wavelength, self._units)

    @property
    def energy(self):
        '''The energy associated with the geometry, in keV'''
        return NM_KEV / self.wavelength

    @energy.setter
    def energy(self, energy):
        self.wavelength = NM_KEV / energy

    @property
    def engine_locked(self):
        '''If set, do not allow the engine to be changed post-initialization'''
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
        '''The name of the currently selected sample'''
        return self._sample.name

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

    def add_sample(self, sample, select=True):
        '''Add an HklSample

        Parameters
        ----------
        sample : HklSample instance
            The sample name, or optionally an already-created HklSample
            instance
        select : bool, optional
            Select the sample to focus calculations on
        '''
        if not isinstance(sample, (HklSample, hkl_module.Sample)):
            raise ValueError('Expected either an HklSample or a Sample '
                             'instance')

        if isinstance(sample, hkl_module.Sample):
            sample = HklSample(calc=self, sample=sample, units=self._unit_name)

        if sample.name in self._samples:
            raise ValueError('Sample of name "%s" already exists' % sample.name)

        self._samples[sample.name] = sample
        if select:
            self._sample = sample
            self._re_init()

        return sample

    def new_sample(self, name, select=True, **kwargs):
        '''Convenience function to add a sample by name

        Keyword arguments are passed to the new HklSample initializer.

        Parameters
        ----------
        name : str
            The sample name
        select : bool, optional
            Select the sample to focus calculations on
        '''
        units = kwargs.pop('units', self._unit_name)
        sample = HklSample(self, sample=hkl_module.Sample.new(name),
                           units=units,
                           **kwargs)

        return self.add_sample(sample, select=select)

    def _re_init(self):
        if self._engine is None:
            return

        if self._geometry is None or self._detector is None or self._sample is None:
            raise ValueError('Not all parameters set (geometry, detector, sample)')
            # pass
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
        '''Calculate the pseudo axis positions from the real axis positions'''
        return self._engine.update()

    def _get_parameter(self, param):
        return Parameter(param, units=self._unit_name)

    @property
    def units(self):
        '''The units used for calculations'''
        return self._unit_name

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


class CalcE4CH(CalcRecip):
    def __init__(self, **kwargs):
        super().__init__('E4CH', **kwargs)


class CalcE4CV(CalcRecip):
    def __init__(self, **kwargs):
        super().__init__('E4CV', **kwargs)


class CalcE6C(CalcRecip):
    RealPos = namedtuple('RealPos', 'mu omega chi phi gamma delta')

    def __init__(self, **kwargs):
        super().__init__('E6C', **kwargs)


class CalcK4CV(CalcRecip):
    def __init__(self, **kwargs):
        super().__init__('K4CV', **kwargs)


class CalcK6C(CalcRecip):
    def __init__(self, **kwargs):
        super().__init__('K6C', **kwargs)


class CalcPetra3_p09_eh2(CalcRecip):
    def __init__(self, **kwargs):
        super().__init__('PETRA3 P09 EH2', **kwargs)


class CalcSoleilMars(CalcRecip):
    def __init__(self, **kwargs):
        super().__init__('SOLEIL MARS', **kwargs)


class CalcSoleilSiriusKappa(CalcRecip):
    def __init__(self, **kwargs):
        super().__init__('SOLEIL SIRIUS KAPPA', **kwargs)


class CalcSoleilSiriusTurret(CalcRecip):
    def __init__(self, **kwargs):
        super().__init__('SOLEIL SIRIUS TURRET', **kwargs)


class CalcSoleilSixsMed1p2(CalcRecip):
    def __init__(self, **kwargs):
        super().__init__('SOLEIL SIXS MED1+2', **kwargs)


class CalcSoleilSixsMed2p2(CalcRecip):
    def __init__(self, **kwargs):
        super().__init__('SOLEIL SIXS MED2+2', **kwargs)


class CalcSoleilSixs(CalcRecip):
    def __init__(self, **kwargs):
        super().__init__('SOLEIL SIXS', **kwargs)


class CalcMed2p3(CalcRecip):
    def __init__(self, **kwargs):
        super().__init__('MED2+3', **kwargs)


class CalcTwoC(CalcRecip):
    def __init__(self, **kwargs):
        super().__init__('TwoC', **kwargs)


class CalcZaxis(CalcRecip):
    def __init__(self, **kwargs):
        super().__init__('ZAXIS', **kwargs)
