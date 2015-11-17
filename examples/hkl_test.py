from __future__ import print_function

import config

from ophyd.utils.hkl import (CalcRecip, CalcE4CH, CalcK6C,
                             DiffE4CH)
import ophyd.utils.hkl as hkl_module
from ophyd.controls.positioner import Positioner


class DumbPositioner(Positioner):
    def move(self, position, **kwargs):
        self._set_position(position)

        self._started_moving = True
        self._done_moving()

        Positioner.move(self, position, **kwargs)

    @property
    def moving(self):
        return False


def test():
    loggers = ('ophyd.utils.hkl',
               )

    config.setup_loggers(loggers)

    logger = config.logger

    logger.info('Diffractometer types: %s' % ', '.join(hkl_module.DIFF_TYPES))

    logger.info('')
    logger.info('---- calck6c ----')
    k6c = CalcK6C(engine='hkl')
    # or equivalently:
    # k6c = CalcRecip('K6C', engine='hkl')

    logger.info(k6c.engines)
    logger.info(k6c['mu'])
    logger.info(k6c[k6c.physical_axis_names[0]].limits)
    # geometry holds physical motor information
    logger.info('physical axes (depends on diffr. type): {}'.format(k6c.physical_axis_names))
    # engine holds pseudo motor information
    logger.info('pseudo axes (depends on engine): {}'.format(k6c.pseudo_axis_names))
    logger.info('engine parameters: {}'.format(k6c.parameters))
    logger.info('hkl 1, 1, 1 corresponds to real motor positions: {}'.format(list(k6c([1, 0.99, 1]))))

    logger.info('')
    logger.info('---- k6c.sample ----')
    sample = k6c.sample
    refl = sample.add_reflection(1, 1, 1)
    sample.remove_reflection(refl)
    sample.clear_reflections()

    lim = (0.0, 20.0)
    k6c['mu'].limits = lim
    logger.info('mu limits: {}'.format(k6c['mu'].limits))
    assert(k6c['mu'].limits == lim)

    k6c['h'] = 1.0
    k6c['mu'] = 0.55
    logger.info('pseudo={} physical={}'.format(dict(k6c.engine.pseudo_axes), dict(k6c.physical_axes)))

    sample.add_reflection(1, 1, 1)
    sample.add_reflection(1, 0, 1)
    sample.add_reflection(1, 0, 0)
    logger.info(sample.reflection_measured_angles)
    logger.info(sample.reflection_theoretical_angles)
    logger.info(sample.reflections)

    k6c.sample.name = 'main_sample'

    sample2 = k6c.add_sample('sample2')
    try:
        k6c.add_sample('sample2')
    except ValueError:
        pass
    else:
        sample2
        raise Exception

    k6c.sample = 'main_sample'

    logger.info('')
    logger.info('---- k6c matrix, lattice, engines ----')
    sample.U = [[1, 1, 1], [1, 0, 0], [1, 1, 0]]
    logger.info('U=%s' % sample.U)
    # sample.UB = [[1, 1, 1], [1, 0, 0], [1, 1, 0]]
    logger.info('UB=%s' % sample.UB)
    logger.info('ux, uy, uz=%s, %s, %s' % (sample.ux, sample.uy, sample.uz))
    logger.info('lattice=%s reciprocal=%s' % (sample.lattice, sample.reciprocal))
    logger.info('main_sample=%s' % sample)
    # logger.info(k6c)
    logger.info('')
    logger.info('current engine is: {}'.format(k6c.engine))
    logger.info('available engines:')

    for engine, info in k6c.engines.items():
        logger.info('-> {}: {}'.format(engine, info))

    # TODO compute_UB affects sample state?
    # logger.info('computed ub=%s' % sample.compute_UB([1, 1, 1], [1, 0, 1]))

    logger.info('wavelength is %s nm (energy=%s keV)' % (k6c.wavelength, k6c.energy))

    logger.info('hkl mode is %s (can be: %s)' % (k6c.engine.mode, k6c.engine.modes))
    logger.info('* single position')
    list(k6c([0, 1, 0]))

    logger.info('* 10 positions between two hkls')
    for solutions in k6c([0, 1, 0], [0, 1, 0.1], n=10):
        logger.info('choosing {} of {} solutions'.format(solutions[0], len(solutions)))
        solutions[0].select()

    logger.info('* 3 specific hkls')
    list(k6c([[0, 1, 0], [0, 1, 0.01], [0, 1, 0.02]]))

    q2_recip = CalcRecip('K6C', engine='q2')
    logger.info('q is {}'.format(q2_recip['q']))
    logger.info('alpha is {}'.format(q2_recip['alpha']))
    assert(len(list(q2_recip([[1, 2], ]))) == 1)
    assert(len(list(q2_recip([[1, 2], [3, 4]]))) == 2)
    assert(len(list(q2_recip([1, 2], [3, 4], n=20))) == 21)

    logger.info('')
    logger.info('---- calce4ch ----')

    e4ch = CalcE4CH()
    logger.info('e4ch axes: {} {}'.format(e4ch.pseudo_axis_names, e4ch.physical_axis_names))

    positioners = [DumbPositioner(name='%s' % name) for name in
                   e4ch.physical_axis_names]

    for i, pos in enumerate(positioners):
        pos._position = 0.1 * (i + 1)

    logger.info('')
    logger.info('---- diffractometer ----')
    diffr = DiffE4CH(positioners, name='my_diffractometer',
                     energy=8.0,
                     )

    calc = diffr.calc
    sample = calc.sample
    sample.add_reflection(1, 1, 1)

    pos0 = positioners[0]
    # this will run the callbacks to force a readback pseudo position calculation:
    # (not normally used, since they should be tied to real motors)
    pos0._set_position(pos0.position)

    def show_pos():
        _pseudos = [(pos.name, pos.position) for pos in diffr.pseudos.values()]
        _reals = [(pos.name, pos.position) for pos in diffr.reals.values()]

        logger.info('pseudo positioner is at {}'.format(_pseudos))
        logger.info('real positioners: {}'.format(_reals))

    show_pos()
    logger.info('')
    diffr.move((1, 0, 1), wait=True)
    diffr.energy = 10.0
    diffr.move((1, 0, 1), wait=True)
    logger.info('')
    show_pos()

    sample = diffr.calc.sample
    logger.info(diffr.calc)

    return k6c, diffr

if __name__ == '__main__':
    k6c, diffr = test()

    print('hkl module is: ', hkl_module.hkl_module)
