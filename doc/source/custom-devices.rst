Custom Devices
**************

A Device is made from Components, which encapsulate other Devices or Signals.
See examples.


.. code-block:: python

    from ophyd import Device, EpicsSignal, EpicsSignalRO
    from ophyd import Component as C
    from ophyd.utils import set_and_wait

    class Robot(Device):
        sample_number = C(EpicsSignal, 'ID:Tgt-SP')
        load_cmd = C(EpicsSignal, 'Cmd:Load-Cmd.PROC')
        unload_cmd = C(EpicsSignal, 'Cmd:Unload-Cmd.PROC')
        execute_cmd = C(EpicsSignal, 'Cmd:Exec-Cmd')
        status = C(EpicsSignal, 'Sts-Sts')
