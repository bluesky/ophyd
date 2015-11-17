from .hkl import Diffractometer
from . import calc


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
