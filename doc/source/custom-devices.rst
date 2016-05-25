Custom Devices
**************

A Device is made from Components, which encapsulate other Devices or Signals.
See examples.


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


Devices and bluesky count_time
==============================

When a ``Device`` is used as a bluesky detector in a scan, a ``count_time``
component will be checked for prior to staging.  For example:


.. code-block:: python

    from ophyd import (Device, Signal, Component as Cpt, EpicsSignal)

    class DetectorWithCountTime(Device):
        count_time = Cpt(Signal)
        exposure_time = Cpt(EpicsSignal, 'ExposureTime-SP')

        def stage(self):
            if self.count_time.get() is not None:
                actual_exposure_time = (self.count_time.get() - 0.1)
                self.stage_sigs[self.exposure_time] = actual_exposure_time
            super().stage()
   
    det = DetectorWithCountTime('prefix:', name='det')
    gs.DETS.append(det)
    RE(dscan(mtr, 0, 1, 5, time=5.0))
    # count_time would be set to 5.0 here, prior to the scan starting
    

Using the approach of a soft Signal on detectors allows ``stage`` to process
the value that comes directly from the user.  A slightly less flexible
alternative would be to define ``count_time`` just as the ``EpicsSignal``
``exposure_time`` below it, if those values should always be the same.
