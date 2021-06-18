Core
====

Status objects (Futures)
------------------------

In addition to :class:`ophyd.status.StatusBase` ophyd provides specialized
subclasses that know more about the object they are tied to.

.. inheritance-diagram:: ophyd.status.StatusBase ophyd.status.MoveStatus ophyd.status.DeviceStatus ophyd.status.Status ophyd.status.SubscriptionStatus
   :parts: 2

.. autosummary::
   :toctree: generated

   ophyd.status.StatusBase
   ophyd.status.Status
   ophyd.status.DeviceStatus
   ophyd.status.MoveStatus
   ophyd.status.SubscriptionStatus
   ophyd.areadetector.trigger_mixins.ADTriggerStatus
   ophyd.status.wait