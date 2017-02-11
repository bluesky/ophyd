========
 Device
========

.. automodule:: ophyd.device


The core class of :mod:`ophyd` is :class:`Device` which encodes
the structure of the device and provides much of core API.


.. autosummary::
   :toctree: _as_gen

   Device

The base :class:`Device` is not particularly useful on it's own,
it must be sub-classed to provide it with


Constructing `Device`
=====================

Under the hood, `Device` uses a metaclass to allow for

.. code-block:: python

    from ophyd import Device, EpicsSignal, EpicsSignalRO
    from ophyd import Component as Cpt
    from ophyd.utils import set_and_wait

    class Robot(Device):
        sample_number = Cpt(EpicsSignal, 'ID:Tgt-SP')
        load_cmd = Cpt(EpicsSignal, 'Cmd:Load-Cmd.PROC')
        unload_cmd = Cpt(EpicsSignal, 'Cmd:Unload-Cmd.PROC')
        execute_cmd = Cpt(EpicsSignal, 'Cmd:Exec-Cmd')
        status = Cpt(EpicsSignal, 'Sts-Sts')

    my_robot = Robot('pv_prefix:', name='my_robot')


In this case, ``my_robot.load_cmd`` would be an ``EpicsSignal`` that points to
the PV ``pv_prefix:Cmd:Load-Cmd.PROC``.  Each of the components can be used as
``stage_sigs``, added to the list of ``read_attrs`` or ``configuration_attrs``,
or simply as ``EpicsSignals`` on their own.



Components
----------




Trigger, Read and Describe
--------------------------


configure, read_configuration, describe_configuration
-----------------------------------------------------


Stage and unstage
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


Implicit triggering
-------------------


Count Time
----------


Low level API
=============


.. autosummary::
   :toctree: _as_gen
   :nosignatures:

   Device.connected
   Device.wait_for_connection
   Device.get
   Device.put
   Device.get_device_tuple
