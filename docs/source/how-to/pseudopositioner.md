# Pseudopositioner

A pseudopositioner is a positioner that presents two interfaces to the hardware:
a direct "real" interface and an indirect "pseudo" interface that enables the
hardware to be read and moved in coordinate system different from the literal
one exposed by the hardware. One important use case is HKL scanning.

```py

from ophyd.psuedopos import (
    PseudoPositioner,
    PseudoSingle,
    pseudo_position_argument,
    real_position_argument
)
from ophyd import Component, SoftPositioner


class SPseudo3x3(PseudoPositioner):
    """
    Interface to three positioners in a coordinate system that flips the sign.
    """
    pseudo1 = Component(PseudoSingle, limits=(-10, 10), egu='a')
    pseudo2 = Component(PseudoSingle, limits=(-10, 10), egu='b')
    pseudo3 = Component(PseudoSingle, limits=None, egu='c')
    
    real1 = Component(SoftPositioner, init_pos=0.)
    real2 = Component(SoftPositioner, init_pos=0.)
    real3 = Component(SoftPositioner, init_pos=0.)

    @pseudo_position_argument
    def forward(self, pseudo_pos):
        "Given a position in the psuedo coordinate system, transform to the real coordinate system."
        return self.RealPosition(
            real1=-pseudo_pos.pseudo1,
            real2=-pseudo_pos.pseudo2,
            real3=-pseudo_pos.pseudo3
        )

    @real_position_argument
    def inverse(self, real_pos):
        "Given a position in the real coordinate system, transform to the pseudo coordinate system."
        return self.PseudoPosition(
            pseudo1=-real_pos.real1,
            pseudo2=-real_pos.real2,
            pseudo3=-real_pos.real3
        )

p3 = Pseudo3x3(name='p3')
```

## Use with Bluesky

```py
from ophyd.sim import det

RE(scan([det, p3], p3.pseudo2, -1, 1, 5))
```