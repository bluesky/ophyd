Positioners
***********

The Positioners are not "ready-to-use" like ``EpicsMotor``. They require
some customization.

For example, this code defines a CS700 temperature controller. A temperature
controller is a kind of positioner, from ophyd's point of view, where the
"position" is the temperature.

.. code-block:: python

    from ophyd import PVPositioner, EpicsSignal, EpicsSignalRO
    from ophyd import Component as C

    # Define a new kind of device.

    class CS700TemperatureController(PVPositioner):
        setpoint = C(EpicsSignal, 'T-SP')
        readback = C(EpicsSignalRO, 'T-I')
        done = C(EpicsSignalRO, 'Cmd-Busy')
        stop_signal = C(EpicsSignal, 'Cmd-Cmd')

    # Create an instance of this new kind of device.

    prefix = 'XF:28IDC-ES:1{Env:01}'
    cs700 = CS700TemperatureController(prefix, name='cs700')

    # When the cs700 has reached the set-point temperature, the 'done' signal
    # flips to 0.
    cs700.done_value = 0

    # The 'settle_time' adds an extra delay between when the cs700 reaches
    # its set point and when it signals that is is ready.
    cs700.settle_time = 10


The "pseudo-positioner" functionality is still under active development.

.. autoclass:: ophyd.pv_positioner.PVPositioner

.. autoclass:: ophyd.positioner.Positioner

.. autoclass:: ophyd.pseudopos.PseudoSingle
.. autoclass:: ophyd.pseudopos.PseudoPositioner
