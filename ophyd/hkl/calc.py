from .hkl import CalcRecip


class CalcE4CH(CalcRecip):
    def __init__(self, **kwargs):
        super().__init__('E4CH', **kwargs)


class CalcE4CV(CalcRecip):
    def __init__(self, **kwargs):
        super().__init__('E4CV', **kwargs)


class CalcE6C(CalcRecip):
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
