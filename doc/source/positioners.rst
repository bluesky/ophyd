.. _positioners:

Positioners
***********

Positioners other than ``EpicsMotor`` and ``SoftPositioner`` are not
"ready-to-use". They require some customization.

PVPositioner
------------

For example, this code defines a CS700 temperature controller. A temperature
controller is a kind of positioner, from ophyd's point of view, where the
"position" is the temperature.

.. code-block:: python

    from ophyd import PVPositioner, EpicsSignal, EpicsSignalRO
    from ophyd import Component as Cpt

    # Define a new kind of device.

    class CS700TemperatureController(PVPositioner):
        setpoint = Cpt(EpicsSignal, 'T-SP')
        readback = Cpt(EpicsSignalRO, 'T-I')
        done = Cpt(EpicsSignalRO, 'Cmd-Busy')
        stop_signal = Cpt(EpicsSignal, 'Cmd-Cmd')

    # Create an instance of this new kind of device.

    prefix = 'XF:28IDC-ES:1{Env:01}'
    cs700 = CS700TemperatureController(prefix, name='cs700')

    # When the cs700 has reached the set-point temperature, the 'done' signal
    # flips to 0.
    cs700.done_value = 0


.. autoclass:: ophyd.pv_positioner.PVPositioner

PseudoPositioner
----------------

An ophyd ``PseudoPositioner`` relates one or more pseudo (virtual) axes to one
or more real (physical) axes via forward and inverse calculations. To define
such a PseudoPositioner, one must subclass from PseudoPositioner:

.. code-block:: python

    from ophyd import (PseudoPositioner, PseudoSingle, EpicsMotor)
    from ophyd import (Component as Cpt)
    from ophyd.pseudopos import (pseudo_position_argument,
                                 real_position_argument)


    class Pseudo3x3(PseudoPositioner):
        # The pseudo positioner axes:
        px = Cpt(PseudoSingle, limits=(-10, 10))
        py = Cpt(PseudoSingle, limits=(-10, 10))
        pz = Cpt(PseudoSingle)

        # The real (or physical) positioners:
        rx = Cpt(EpicsMotor, 'XF:31IDA-OP{Tbl-Ax:X1}Mtr')
        ry = Cpt(EpicsMotor, 'XF:31IDA-OP{Tbl-Ax:X2}Mtr')
        rz = Cpt(EpicsMotor, 'XF:31IDA-OP{Tbl-Ax:X3}Mtr')

        @pseudo_position_argument
        def forward(self, pseudo_pos):
            '''Run a forward (pseudo -> real) calculation'''
            return self.RealPosition(rx=-pseudo_pos.px,
                                     ry=-pseudo_pos.py,
                                     rz=-pseudo_pos.pz)

        @real_position_argument
        def inverse(self, real_pos):
            '''Run an inverse (real -> pseudo) calculation'''
            return self.PseudoPosition(px=-real_pos.rx,
                                       py=-real_pos.ry,
                                       pz=-real_pos.rz)

``Pseudo3x3`` above is a pseudo positioner with 3 pseudo axes and 3 real axes.
The pseudo axes are defined in order as (px, py, pz). Similarly, the real
positioners are (rx, ry, rz).

There is no restriction that the real axes must be tied to physical hardware.
A physical axis could just as well be a ``SoftPositioner``, or any subclass of
``PositionerBase`` (with the sole exception of ``PseudoSingle``).

The forward calculation says that, for any given pseudo position, the real
motors should move to the opposite position. For example, for a pseudo position
of (px=1, py=2, pz=3), the corresponding real position would be (rx=-1, ry=-2,
rz=-3). The inverse calculation is similar, in going from a real position to a
pseudo position.

The two decorators ``@real_position_argument`` and
``@pseudo_position_argument`` are used here for convenience so that one can
call these functions in a variety of ways, all of which generate a correct
PseudoPosition tuple as the first argument to your calculation method.
Positions can be specified in the following ways:

* As positional arguments:

.. code-block:: python

    pseudo.forward(px, py, pz)


* As a sequence or PseudoPosition/RealPosition:

.. code-block:: python

    pseudo.forward((px, py, pz))
    pseudo.forward(pseudo.PseudoPosition(px, py, pz))


* As kwargs:

.. code-block:: python

    pseudo.forward(px=1, py=2, pz=3)


``move`` is decorated like this on PseudoPositioner, meaning you can also call
it with this syntax.

.. autoclass:: ophyd.pseudopos.PseudoSingle
.. autoclass:: ophyd.pseudopos.PseudoPositioner


SoftPositioner
--------------

A ``SoftPositioner`` is a positioner which has no corresponding physical motor.
On its own, it is most useful for debugging scanning logic when moving physical
motors is either undesirable or not possible.

Used as-is, a ``SoftPositioner`` will "move" to the requested position
immediately.

``PseudoSingle`` and ``PseudoPositioner``, for example, are implemented as
heavily customized ``SoftPositioner`` subclasses.

.. autoclass:: ophyd.positioner.PositionerBase
.. autoclass:: ophyd.positioner.SoftPositioner

.. code-block:: python

    from ophyd import SoftPositioner
    my_positioner = SoftPositioner(name='my_positioner')
