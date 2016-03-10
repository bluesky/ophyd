Ready-to-Use Devices
********************

These devices are have ready-made classes in Python. To configure them, the
user need only provide a PV prefix and a name.

EpicsMotor
----------

Create an ``EpicsMotor`` to communicate with a single `EPICS motor record
<http://www.aps.anl.gov/bcda/synApps/motor/>`_:

.. code-block:: python

    from ophyd import EpicsMotor

    # the two-theta motor
    tth = EpicsMotor('XF:28IDC-ES:1{Dif:1-Ax:2ThI}Mtr', name='tth')

.. autoclass:: ophyd.epics_motor.EpicsMotor


EpicsScaler
-----------

Create an ``EpicsScaler`` to control an EPICS `scaler record
<http://www.aps.anl.gov/bcda/synApps/std/scalerRecord.html>`_:

.. code-block:: python

    from ophyd import EpicsScaler
    scaler = EpicsScaler('XF:28IDC-ES:1{Sclr:1}', name='tth')

.. autoclass:: ophyd.scaler.EpicsScaler


EpicsMCA and EpicsDXP
---------------------

`MCA records <http://cars9.uchicago.edu/software/epics/mcaRecord.html>`_ and
DXP-based devices are also supported, through the ``EpicsMCA`` and ``EpicsDXP``
devices.

.. autoclass:: ophyd.mca.EpicsMCARecord
.. autoclass:: ophyd.mca.EpicsDXP
