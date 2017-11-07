Status Objects
==============

.. automodule:: ophyd.status

The core API of the status objects is a property and a private method:

.. autosummary::
   :toctree: generated
   :nosignatures:

   StatusBase
   StatusBase.finished_cb
   StatusBase._finished



In addition we provide two specialized sub-classes that know more about the object
they are tied to.

.. autosummary::
   :toctree: generated
   :nosignatures:


   DeviceStatus
   MoveStatus
   Status

The status objects also handle timeouts (if an action take too long)
and a settle time (to wait after the action has completed, but before triggering the callback
registered onto ``finished_cb``.


.. inheritance-diagram:: ophyd.status.StatusBase ophyd.status.MoveStatus ophyd.status.DeviceStatus ophyd.status.Status
    :parts: 2
