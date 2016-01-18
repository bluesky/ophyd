Ready-to-Use Devices
*********************

These devices are have ready-made classes in Python. To configure them, the
user need only provide a PV prefix and a name. Example:

.. code-block:: python

    from ophyd import EpicsMotor

    # the two-theta motor
    tth = EpicsMotor('XF:28IDC-ES:1{Dif:1-Ax:2ThI}Mtr', name='tth')

.. autoclass:: ophyd.epics_motor.EpicsMotor

.. autoclass:: ophyd.scaler.EpicsScaler

.. autoclass:: ophyd.mca.EpicsMCA
.. autoclass:: ophyd.mca.EpicsDXP
