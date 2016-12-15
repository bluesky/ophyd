.. currentmodule:: ophyd

==============
 Architecture
==============

``Ophyd`` is hardware abstraction layer to provide a consistent
interface between the underlying control communication protocol and
`bluesky <https://nsls-ii.github.io/bluesky>`_.  This is done by
bundling sets of the underlying process variables in to hierarchical
devices and exposing a semantic API in terms of control system
primitives.  Thus we have two terms that will be used through out

Basic concepts
==============

Hardware abstraction
--------------------

  **Signal**
    Represents an atomic 'process variable'. This is nominally a
    'scalar' value and can not be decomposed any further by layers
    above :mod:`ohpyd`.

  **Device**
    Hierarchy composed of Signals and other Devices.  The components of
    a Device can be introspected by layers above :mod:`ophyd` and may be
    decomposed to, ultimately, the underlying Signals.


Put another way, if a hierarchical device is a tree, **Signals** are the leaves
and **Devices** are the nodes.


In EPICS, **Signal** maybe backed by a read-only PV, a single
read-write PV, or a pair of read and write PVs, grouped together.  In
any of those cases, a single value is exposed to `bluesky`_.  For more
complex hardware, for example a `motor record
<http://www.aps.anl.gov/bcda/synApps/motor/>`_, the relationships
between the individual process variables needs to be encoded in a
:class:`~device.Device` (a :class:`~epics_motor.EpicsMotor` class ships with ohpyd for this
case).  This includes both what **Signals** are grouped together, but
also how to manipulate them a coordinated fashion to achieve the
high-level action (moving a motor, changing a temperature, opening a
valve, or taking data).  More complex devices, like a diffractometer
or a Area Detector, can be assembled out of simpler component devices.

Asynchronous status
-------------------

Hardware control and data collection is an inherently asynchronous
activity.  The many devices on a beamline are (in general) uncoupled
and can move / read independently.  This is reflected in the callback
registry at the core of :obj:`~ophydobj.OphydObject` and most of the
object methods in :obj:`BlueskyInterface` returning `Status` objects.
These objects are one of the bridges between the asynchronous behavior
of the underlying control system and the asynchronous behavior of
:class:`~bluesky.run_engine.RunEngine`.

The core API of the status objects is a property and a private method:

.. autosummary::
   :nosignatures:

   status.StatusBase.finished_cb
   status.StatusBase._finished

The `bluesky`_ side assigns a callback to
:attr:`status.StatusBase.finished_cb` which is triggered when the
:meth:`status.StatusBase._finished` method is called.  The status object
conveys both that the action it 'done' and if the action was
successful or not.


Base Classes
============



The base class of almost all objects in ``ophyd`` is :obj:`~ophydobj.OphydObject`
which provides the core set of properties, reper/reporting

.. autosummary::
   :toctree: _as_gen
   :nosignatures:

   ophydobj.OphydObject
   ophydobj.OphydObject.connected
   ophydobj.OphydObject.parent
   ophydobj.OphydObject.root

and a callback registry

.. autosummary::
   :toctree: _as_gen
   :nosignatures:


   ophydobj.OphydObject.event_types
   ophydobj.OphydObject.subscribe
   ophydobj.OphydObject.clear_sub
   ophydobj.OphydObject._run_subs

This registry is used to connect to the underlying hardware events and propagate events
from the hardware up to bluesky, either via `~status.StatusBase` objects or via direct
subscription from the :class:`~bluesky.run_engine.RunEngine`.

Signals and Devices
===================



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
