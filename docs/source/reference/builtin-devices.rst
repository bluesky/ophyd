Devices with Built-in Support
=============================

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

Creating 'bundles' of motors is very common so we also have a helper
class that tweaks the default behavior of :attr:`read_attrs`,
:attr:`configuration_attrs`, and :attr:`hints`

This must be sub-classed (like :class:`~ophyd.device.Device`) to be useful.

.. code-block:: python

   from ophyd import MotorBundle, EpicsMotor
   from ophyd import Component as Cpt

   class StageXY(MotorBundle):
       x = Cpt(EpicsMotor, ':X')
       y = Cpt(EpicsMotor, ':Y')

   stage = StageXY('STAGE_PV', name='stage')

.. autosummary::
   :toctree: ../generated

   ophyd.epics_motor.EpicsMotor
   ophyd.epics_motor.MotorBundle

EpicsScaler
-----------

Create an ``EpicsScaler`` to control an EPICS `scaler record
<http://www.aps.anl.gov/bcda/synApps/std/scalerRecord.html>`_:

.. code-block:: python

    from ophyd import EpicsScaler
    scaler = EpicsScaler('XF:28IDC-ES:1{Sclr:1}', name='tth')

.. autosummary::
   :toctree: ../generated

   ophyd.scaler.EpicsScaler


EpicsMCA and EpicsDXP
---------------------

`MCA records <http://cars9.uchicago.edu/software/epics/mcaRecord.html>`_ and
DXP-based devices are also supported, through the ``EpicsMCA`` and ``EpicsDXP``
devices.

.. autosummary::
   :toctree: ../generated

   ophyd.mca.EpicsMCARecord
   ophyd.mca.EpicsDXP