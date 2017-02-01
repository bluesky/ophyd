.. currentmodule:: ophyd

==============
 Architecture
==============

``Ophyd`` is hardware abstraction layer to provide a consistent
interface between the underlying control communication protocol and
`bluesky <https://nsls-ii.github.io/bluesky>`_.  This is done by
bundling sets of the underlying process variables into hierarchical
devices and exposing a semantic API in terms of control system
primitives.  Thus we have two terms that will be used through out

Hardware abstraction
====================

  **Signal**
    Represents an atomic 'process variable'. This is nominally a
    'scalar' value and can not be decomposed any further by layers
    above :mod:`ophyd`.

  **Device**
    Hierarchy composed of Signals and other Devices.  The components of
    a Device can be introspected by layers above :mod:`ophyd` and may be
    decomposed to, ultimately, the underlying Signals.


Put another way, if a hierarchical device is a tree, **Signals** are the leaves
and **Devices** are the nodes.



Asynchronous status
===================

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


Callbacks
=========

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

This registry is used to connect to the underlying hardware events and
propagate events from the hardware up to bluesky, either via
`~status.StatusBase` objects or via direct subscription from the
:class:`~bluesky.run_engine.RunEngine`.
