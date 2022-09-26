Core
====

Status objects (Futures)
------------------------

In addition to :class:`ophyd.status.StatusBase` ophyd provides specialized
subclasses that know more about the object they are tied to.

.. inheritance-diagram:: ophyd.status.StatusBase ophyd.status.MoveStatus ophyd.status.DeviceStatus ophyd.status.Status ophyd.status.SubscriptionStatus
   :parts: 2

.. autosummary::
   :toctree: ../generated

   ophyd.status.StatusBase
   ophyd.status.Status
   ophyd.status.DeviceStatus
   ophyd.status.MoveStatus
   ophyd.status.SubscriptionStatus
   ophyd.areadetector.trigger_mixins.ADTriggerStatus
   ophyd.status.wait

Callbacks
---------

The base class of Device and Signal objects in Ophyd is :obj:`~ophydobj.OphydObject`,
a callback registry.

.. currentmodule:: ophyd.ophydobj

.. autosummary::
   :toctree: ../generated
   :nosignatures:

   OphydObject
   OphydObject.event_types
   OphydObject.subscribe
   OphydObject.unsubscribe
   OphydObject.clear_sub
   OphydObject._run_subs
   OphydObject._reset_sub

This registry is used to connect to the underlying events from the
control system and propagate them up to bluesky, either via
:class:`~status.StatusBase` objects or via direct subscription from the
:class:`~bluesky.run_engine.RunEngine`.