.. _signal_indx:

Signals
*******

In EPICS, **Signal** maybe backed by a read-only PV, a single
read-write PV, or a pair of read and write PVs, grouped together.  In
any of those cases, a single value is exposed to `bluesky
<https://nsls-ii.github.io/bluesky>`_.  For more complex hardware, for
example a `motor record
<http://www.aps.anl.gov/bcda/synApps/motor/>`_, the relationships
between the individual process variables needs to be encoded in a
:class:`~device.Device` (a :class:`~epics_motor.EpicsMotor` class
ships with ophyd for this case).  This includes both what **Signals**
are grouped together, but also how to manipulate them a coordinated
fashion to achieve the high-level action (moving a motor, changing a
temperature, opening a valve, or taking data).  More complex devices,
like a diffractometer or a Area Detector, can be assembled out of
simpler component devices.


A ``Signal`` is much like a ``Device`` -- they share almost the same
interface -- but a ``Signal`` has no sub-components. In ophyd's hierarchical,
tree-like representation of a complex piece of hardware, the signals are
the leaves. Each one represents a single PV or a read--write pair of PVs.



.. automodule:: ophyd.signal
