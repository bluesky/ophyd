======================
 Device and Component
======================

.. automodule:: ophyd.device


Usage
=====

The core class of :mod:`ophyd` is :class:`Device` which encodes the
nodes of the hierarchical structure of the device and provides much of
core API.


.. autosummary::
   :toctree: generated

   Device

The base :class:`Device` is not particularly useful on it's own, it
must be sub-classed to provide it with components to do something
with.

Creating a custom device is as simple as

.. code-block:: python

   from ophyd import Device, EpicsMotor
   from ophyd import Component as Cpt

   class StageXY(Device):
       x = Cpt(EpicsMotor, ':X')
       y = Cpt(EpicsMotor, ':Y')

   stage = StageXY('STAGE_PV', name='stage')

You can then use ``stage`` as an input to any plan as a detector and
``stage.x`` and ``stage.y`` as independent motors.


A Robot
-------

A slightly more complex example is to control a simple sample loading
robot.

.. code-block:: python

    from ophyd import Device, EpicsSignal, EpicsSignalRO
    from ophyd import Component as Cpt
    from ophyd.utils import set_and_wait

    class Robot(Device):
        sample_number = Cpt(EpicsSignal, 'ID:Tgt-SP')
        load_cmd = Cpt(EpicsSignal, 'Cmd:Load-Cmd.PROC')
        unload_cmd = Cpt(EpicsSignal, 'Cmd:Unload-Cmd.PROC')
        execute_cmd = Cpt(EpicsSignal, 'Cmd:Exec-Cmd')

        status = Cpt(EpicsSignalRO, 'Sts-Sts')

    my_robot = Robot('PV_PREFIX:', name='my_robot',
                     read_attrs=['sample_number', 'status'])

Which creates an instance ``my_robot`` with 5 children

   ======================   ===============================    =====================
   python attribute         PV name                            in ``read()``
   ======================   ===============================    =====================
   my_robot.sample_number   'PV_PREFIX:ID:Tgt-SP'              Y
   my_robot.load_cmd        'PV_PREFIX:CMD:Load-Cmd.PROC'      N
   my_robot.unload_cmd      'PV_PREFIX:CMD:Unload-Cmd.PROC'    N
   my_robot.execute_cmd     'PV_PREFIX:CMD:Exec-Cmd'           N
   my_robot.status          'PV_PREFIX:Sts-Sts'                Y
   ======================   ===============================    =====================

only 2 of which will be included when reading from the robot.

You could now use this device in a scan like

.. code-block:: python

   import bluesky.plans as bp

   def load_sample(robot, sample):
       yield from bp.mv(robot.sample_number, sample)
       yield from bp.mv(robot.load_cmd, 1)
       yield from bp.mv(robot.execute_cmd, 1)

   def unload_sample(robot):
       yield from bp.mv(robot.unload_cmd, 1)
       yield from bp.mv(robot.execute_cmd, 1)

   def robot_plan(list_of_samples):
       for sample in list_of_samples:
           # load the sample
	   yield from load_sample(my_robot, sample)
	   # take a measurement
	   yield from bp.count([det], md={'sample': sample})
	   # unload the sample
	   yield from unload_sample(my_robot)

and from the command line ::

  RE(robot_plan([1, 2. 6]))


These classes were co-developed with :mod:`bluesky` and are the
reference implementation of a hardware abstraction layer for
:mod:`bluesky`.  However, these are closely tied to EPICS and make
some assumptions about the PV naming based on NSLS-II's naming scheme.
Despite attempting generality, it is likely that as :mod:`ophyd` and
:mod:`bluesky` are used at other facilities (and when :mod:`ophyd` is
adapted for a different control system) we will discover some latent
NSLS-II-isms that should be corrected (or at least acknowledged and
documented).


:class:`Device`
===============

:class:`Device` adds a number of additional attributes beyond the
required :mod:`bluesky` API and what is inherited from :class:`~ohpyd.ophydobj.OphydObj`
for run-time configuration

 ===========================  ========================================================
 Attribute                    Description
 ===========================  ========================================================
 :attr:`read_attrs`           Names of components for ``read()`` See :ref:`trd`
 ---------------------------  --------------------------------------------------------
 :attr:`configuration_attrs`  Names of components for ``read_configuration()``.
			      See :ref:`cfg_and_f`
 ---------------------------  --------------------------------------------------------
 :attr:`stage_sigs`           Signals to be set during `Stage and Unstage`_
 ===========================  ========================================================

and static information about the object

 ===========================  ========================================================
 Attribute                    Description
 ===========================  ========================================================
 :attr:`prefix`               'base' of PV name, used when building components
 ---------------------------  --------------------------------------------------------
 :attr:`component_names`      List of the names components on this device.
	                      Direct children only
 ---------------------------  --------------------------------------------------------
 :attr:`trigger_signals`      Signals for use in `Implicit Triggering`_
                              (provisional)
 ===========================  ========================================================

:class:`Device` also has two class-level attributes to control the default contents of
:attr:`read_attrs` and :attr:`configuration_attrs`.

 ====================================  ========================================================
 Attribute                             Description
 ====================================  ========================================================
 :attr:`_default_read_attrs`           The default contents of :attr:`read_attrs` if a subset
                                       of all available children.

			               An iterable or `None`.  If `None` defaults to
			               all children

				       A :class:`tuple` is recommended.

 ------------------------------------  --------------------------------------------------------
 :attr:`_default_configuration_attrs`  The default contents of :attr:`configuration_attrs`

			               An iterable or `None`.  If `None` defaults to ``[]``

				       A :class:`tuple` is recommended.

 ====================================  ========================================================


:class:`Component`
------------------

The :class:`Compent` class is a python descriptor_ which override the
behavior on attribute access.  This allows us to use a declarative
style to define the software representation of the hardware.  The best
way to understand ::

  class Foo(Device):
      bar = Cpt(EpicsSignal, ':bar', string=True)

is "When a ``Foo`` instance is created give it a ``bar`` attribute
which is an instance of :class:`EpicsSignal` and use the extra args
and kwargs when creating it".  It is a declaration of what you want
and it is the responsibility of :mod:`ophyd` to make it happen.

There are three classes

.. autosummary::
   :toctree: generated

   Component
   FormattedComponent
   DynamicDeviceComponent


.. _trd:

Trigger, Read and Describe
--------------------------

.. _cfg_and_f:


Configuration and Friends
-------------------------


Stage and Unstage
-----------------

When a Device ``d`` is used in scan, it is "staged" and "unstaged." Think of
this as "setup" and "cleanup". That is, before a device is triggered, read, or
moved, the scan is expected to call ``d.stage()``. And, at the end of scan,
``d.unstage()`` is called. (Whenever possible, unstaging is performed even if
the scan is aborted or fails due to an error.)

The staging process is a "hook" for preparing a device for use. To add
custom staging logic to a Device, subclass it and override ``stage`` and/or
``unstage`` like so.

.. code-block:: python

    class MyMotor(EpicsMotor):

        def stage(self):
            print('I am staging.')
            super().stage()

        def unstage(self):
            print('I am unstaging.')
            super().unstage()

It is crucial to call ``super()``, as above, so that any built-in staging
behavior is not overridden.

A common use for staging is to set certain signals to certain values for
a scan and then set them back at the end. For example, a detector device
might turn on "capture mode" at the beginning of the scan and then flip it
back off (or back to its original setting, whatever that was) at the end.
For this, ophyd provides a convenience, ``stage_sigs`` --- a dictionary
mapping signals to desired values. The device reads the initial values
of these signals, stashes them, changes them to the desired value, and then
restore the initial value when the device is unstaged. It is best to
customize ``stage_sigs`` in the device's ``__init__`` method, like so:

.. code-block:: python

    class MyMotor(EpicsMotor):
        def __init__(*args, **kwargs):
            super().__init__(*args, **kwargs)
            self.stage_sigs[self.user_offset] = 5

When a ``MyMotor`` device is staged, its ``user_offset`` value will be set
to 5. When it is unstaged, it will be set back to whatever value it had
right before it was staged.


Implicit Triggering
-------------------


Count Time
----------


Low level API
=============


.. autosummary::
   :toctree: generated
   :nosignatures:

   Device.connected
   Device.wait_for_connection
   Device.get_instantiated_signals
   Device.get
   Device.put
   Device.get_device_tuple

.. _descriptor: https://docs.python.org/3/reference/datamodel.html#implementing-descriptors


.. todo ['trigger_signals', ]
