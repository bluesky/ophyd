Project Architecture
********************

This is the class inheritance diagram for the key pieces of ophyd. This is
a selection meant to give a readable and representative picture of the
package's organization.

.. inheritance-diagram:: ophyd.Device ophyd.Component ophyd.EpicsSignal ophyd.EpicsSignalRO ophyd.Signal ophyd.EpicsMotor ophyd.EpicsScaler ophyd.EpicsMCA ophyd.AreaDetector ophyd.HDF5Plugin ophyd.DynamicDeviceComponent ophyd.PVPositioner ophyd.SingleTrigger
    :parts: 2

Device classes use metaclass magic to inspect and lazily instantiate their
Components. The examples illustrate how easy it is to define new kinds of
devices, and this is largely because the "dirty work" of handling connections
is hidden in the ``Component`` and ``ComponentMeta``. To understand further,
read the source code of ``device.py`` or contact the developers.
