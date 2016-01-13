import logging
from . import calc
from .. import (Signal, PseudoPositioner)


logger = logging.getLogger(__name__)


class Diffractometer(PseudoPositioner):
    calc_class = None

    def __init__(self, prefix, calc_kw=None, decision_fcn=None,
                 energy_signal=None, energy=8.0, calc_inst=None,
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

        super().__init__(prefix, **kwargs)

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

    def forward(self, pseudo):
        solutions = self._calc.forward(pseudo)
        logger.debug('pseudo to real: {}'.format(solutions))

        if self._decision_fcn is not None:
            return self._decision_fcn(position, solutions)
        else:
            solutions[0].select()
            return solutions[0].positions

    def inverse(self, real):
        pseudo = self._calc.inverse(real)
        return self.PseudoPosition(*pseudo)


class E4CH(Diffractometer):
    calc_class = calc.CalcE4CH


class E4CV(Diffractometer):
    calc_class = calc.CalcE4CV


class E6C(Diffractometer):
    calc_class = calc.CalcE6C


class K4CV(Diffractometer):
    calc_class = calc.CalcK4CV


class K6C(Diffractometer):
    calc_class = calc.CalcK6C


class Petra3_p09_eh2(Diffractometer):
    calc_class = calc.CalcPetra3_p09_eh2


class SoleilMars(Diffractometer):
    calc_class = calc.CalcSoleilMars


class SoleilSiriusKappa(Diffractometer):
    calc_class = calc.CalcSoleilSiriusKappa


class SoleilSiriusTurret(Diffractometer):
    calc_class = calc.CalcSoleilSiriusTurret


class SoleilSixsMed1p2(Diffractometer):
    calc_class = calc.CalcSoleilSixsMed1p2


class SoleilSixsMed2p2(Diffractometer):
    calc_class = calc.CalcSoleilSixsMed2p2


class SoleilSixs(Diffractometer):
    calc_class = calc.CalcSoleilSixs


class Med2p3(Diffractometer):
    calc_class = calc.CalcMed2p3


class TwoC(Diffractometer):
    calc_class = calc.CalcTwoC


class Zaxis(Diffractometer):
    calc_class = calc.CalcZaxis
