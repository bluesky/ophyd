Devices with Built-in Support
=============================

These devices have ready-made classes in Python. To configure them, the
user need only provide a PV prefix and a name.

EPICS motor
-----------

The EPICS `motor record <http://www.aps.anl.gov/bcda/synApps/motor/>`_
is supported by the :class:`~ophyd.epics_motor.EpicsMotor` Device in ``ophyd``:

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

.. _built_in.Epics.Scaler.record:

EPICS Scaler
------------

The EPICS ``scaler`` record ([#scaler]_) is supported by two alternative
``ophyd`` Devices.  (You need only choose one of these two.)  An important
difference between the :ref:`built_in.EpicsScaler` and the :ref:`built_in.ScalerCH`
Devices is in how each channel's name is represented, as summarized 
in the next table:

===========================  =======================================  ====================================================
class                        channel naming                           examples
===========================  =======================================  ====================================================
:ref:`built_in.EpicsScaler`  numbered                                 ``scaler_channels_chan2``, ``scaler_channels_chan3``
:ref:`built_in.ScalerCH`     EPICS scaler record channel name fields  ``I0``, ``diode``
===========================  =======================================  ====================================================

.. [#scaler] EPICS ``scaler`` documentation:
   https://htmlpreview.github.io/?https://github.com/epics-modules/scaler/blob/master/documentation/scalerRecord.html

.. _built_in.EpicsScaler:

EpicsScaler
+++++++++++

Create an :class:`~ophyd.scaler.EpicsScaler` object to control an EPICS ``scaler`` record ([#scaler]_).

.. code-block:: python

    from ophyd import EpicsScaler
    scaler = EpicsScaler('XF:28IDC-ES:1{Sclr:1}', name='scaler')

.. autosummary::
   :toctree: ../generated

   ophyd.scaler.EpicsScaler

.. _built_in.ScalerCH:

ScalerCH
++++++++

Create a :class:`~ophyd.scaler.ScalerCH` object to control an EPICS ``scaler`` record ([#scaler]_).

.. code-block:: python

    from ophyd.scaler import ScalerCH
    scaler = ScalerCH('XF:28IDC-ES:1{Sclr:1}', name='scaler')

.. autosummary::
   :toctree: ../generated

   ophyd.scaler.ScalerCH


EpicsMCA and EpicsDXP
---------------------

EPICS `MCA records <http://cars9.uchicago.edu/software/epics/mcaRecord.html>`_ and
DXP-based devices are also supported, through the ``EpicsMCA`` and ``EpicsDXP``
devices.

.. autosummary::
   :toctree: ../generated

   ophyd.mca.EpicsMCARecord
   ophyd.mca.EpicsDXP
