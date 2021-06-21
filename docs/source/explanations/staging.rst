Stage and Unstage
=================

When a Device ``d`` is used in scan, it is "staged" and "unstaged." Think of
this as "setup" and "cleanup". That is, before a device is triggered, read, or
moved, the scan is expected to call ``d.stage()``. And, at the end of scan,
``d.unstage()`` is called. (Whenever possible, unstaging is performed even if
the scan is aborted or fails due to an error.)

The staging process is a "hook" for preparing a device for use. To add
custom staging logic to a Device, subclass it and override ``stage`` and/or
``unstage`` like so.

.. code:: python

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

.. code:: python

    class MyMotor(EpicsMotor):
        def __init__(*args, **kwargs):
            super().__init__(*args, **kwargs)
            self.stage_sigs[self.user_offset] = 5

When a ``MyMotor`` device is staged, its ``user_offset`` value will be set
to 5. When it is unstaged, it will be set back to whatever value it had
right before it was staged.