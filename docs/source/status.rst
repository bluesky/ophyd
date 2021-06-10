Status objects (Futures)
========================

Ophyd Status objects signal when some potentially-lengthy action is complete.
The action may be moving a motor, acquiring an image, or waiting for a
temperature controller to reach a setpoint. From a general software engineering
point of view, they are like :obj:`concurrent.futures.Future` objects in the
Python standard library but with some semantics specific to controlling
physical hardware.

The lifecycle of a Status object is:

#. A Status object is created with an associated timeout. The timeout clock
   starts.
#. The recipient of the Status object may add callbacks that will be notified
   when the Status object completes.
#. The Status object is marked as completed successfully, or marked as
   completed with an error, or the timeout is reached, whichever happens first.
   The callbacks are called in any case.

Creation and Marking Completion
-------------------------------

A *timeout*, given in seconds, is optional but strongly recommended. (The
default, ``None`` means it will wait forever to be marked completed.)

.. code:: python

   from ophyd import Status

   status = Status(timeout=60)

Additionally, it accepts a *settle_time*, an extra delay which will be added
between the control system reporting successful completion and the Status being
marked as finished. This is also given in seconds. It is ``0`` by default.

.. code:: python

   status = Status(timeout=60, settle_time=10)

The status should be notified by the control system, typically from another
thread or task, when some action is complete. To mark success, call
:obj:`~ophyd.StatusBase.set_finished`. To mark failure, call
:obj:`~ophyd.StatusBase.set_exception`, passing it an Exception giving
information about the cause of failure.

As a toy example, we could hook it up to a :obj:`threading.Timer` that marks it
as succeeded or failed based on a coin flip.

.. code:: python

   import random
   import threading

   def mark_done():
       if random.random() > 0.5:  # coin flip
           status.set_finished()  # success
       else:
           error = Exception("Bad luck")
           status.set_exception(error)  # failure

   # Run mark_done 5 seconds from now in a thread.
   threading.Timer(5, mark_done).start()

See the tutorials for more realistic examples involving integration with an
actual control system.

.. versionchanged:: v1.5.0

   In previous versions of ophyd, the Status objects were marked as completed
   by calling ``status._finished(success=True)`` or
   ``status._finished(success=False)``. This is still supported but the new
   methods ``status.set_finished()`` and ``status.set_exception(...)`` are
   recommended because they can provide more information about the *cause* of
   failure, and they match the Python standard library's
   :obj:`concurrent.futures.Future` interface.

Notification of Completion
--------------------------

The recipient of the Status object can request synchronous or asynchronous
notification of completion. To wait synchronously, the :obj:`~ophyd.StatusBase.wait`
will block until the Status is marked as complete or a timeout has expired.

.. code:: python

   status.wait()  # Wait forever for the Status to finish or time out.
   status.wait(10)  # Wait for at most 10 seconds.

If and when the Status completes successfully, this will return ``None``. If
the Status is marked as failed, the exception (e.g. ``Exception("Bad luck")``
in our example above) will be raised. If the Status' own timeout has expired,
:obj:`~ophyd.utils.StatusTimeoutError` will be raised. If a timeout given to
:obj:`~ophyd.StatusBase.wait` expires before any of these things happen,
:obj:`~ophyd.utils.WaitTimeoutError` will be raised.

The method :obj:`~ophyd.StatusBase.exception` behaves similarly to
:obj:`~ophyd.StatusBase.wait`; the only difference is that if the Status is marked as
failed or the Status' own timeout expires it *returns* the exception rather
than *raising* it. Both return ``None`` if the Status finishes successfully,
and both raise :obj:`~ophyd.utils.WaitTimeoutError` if the given timeout expires
before the Status completes or times out.

Alternatively, the recipient of the Status object can ask to be notified of
completion asynchronously by adding a callback. The callback will be called
when the Status is marked as complete or its timeout has expired. (If no
timeout was given, the callback might never be called. This is why providing a
timeout is strongly recommended.)

.. code:: python

   def callback(status):
       print(f"{status} is done")

   status.add_callback(callback)

Callbacks may be added at any time. Until the Status completes, it holds a hard
reference to each callback in a list, ``status.callbacks``. The list is cleared
when the callback completes. Any callbacks added to a Status object *after*
completion will be called immediately, and no reference will be held.

Each callback is passed to the Status object as an argument, and it can use
this to distinguish success from failure.

.. code:: python

   def callback(status):
       error = status.exception()
       if error is None:
           print(f"{status} has completed successfully.")
       else:
           print(f"{status} has failed with error {error}.")

SubscriptionStatus
------------------

The :class:`~ophyd.status.SubscriptionStatus` is a special Status object that
correctly and succinctly handles a common use case, wherein the Status object
is marked finished based on some ophyd event. It reduces this:

.. code:: python

   from ophyd import Device, Component, DeviceStatus

   class MyToyDetector(Device):
       ...
       # When set to 1, acquires, and then goes back to 0.
       acquire = Component(...)

       def trigger(self):
           def check_value(*, old_value, value, **kwargs):
               "Mark status as finished when the acquisition is complete."
               if old_value == 1 and value == 0:
                   status.set_finished()
                   # Clear the subscription.
                   sself.acquire.clear_sub(check_value)

           status = DeviceStatus(self.acquire)
           self.acquire.subscribe(check_value)
           self.acquire.set(1)
           return status

to this:

.. code:: python

   from ophyd import Device, Component, SubscriptionStatus

   class MyToyDetector(Device):
       ...
       # When set to 1, acquires, and then goes back to 0.
       acquire = Component(...)

       def trigger(self):
           def check_value(*, old_value, value, **kwargs):
               "Return True when the acquisition is complete, False otherwise."
               return (old_value == 1 and value == 0)

           status = SubscriptionStatus(self.acquire, check_value)
           self.acquire.set(1)
           return status

Note that ``set_finished``, ``subscribe`` and ``clear_sub`` are gone; they are
handled automatically, internally. See
:class:`~ophyd.status.SubscriptionStatus` for additional options.

Partial Progress Updates
------------------------

Some Status objects provide an additional method named ``watch``, as in
:meth:`~ophyd.status.MoveStatus.watch`, which can be used to subscribe to
*incremental* progress updates suitable for building progress bars. See
:doc:`bluesky:progress-bar` for one application of this feature.

The ``watch`` method accepts a callback which must accept the following
parameters as optional keyword arguments:

* ``name``
* ``current``
* ``initial``
* ``target``
* ``unit``
* ``precision``
* ``fraction``
* ``time_elapsed``
* ``time_remaining``

The callback may receive a subset of these depending on how much we can know
about the progress of a particular action. In the case of
:obj:`ophyd.status.MoveStatus` and
:obj:`ophyd.areadetector.trigger_mixins.ADTriggerStatus`, we know a lot, from
which one can build a frequently-updating progress bar with a realistic
estimated time of completion. In the case of a generic
:obj:`ophyd.status.DeviceStatus`, we only know the name of the assocated
Device, when the action starts, and when the action ends.

Status API details
------------------

.. autoclass:: ophyd.status.StatusBase
   :members:

In addition we provide specialized subclasses that know more about the object
they are tied to.

.. inheritance-diagram:: ophyd.status.StatusBase ophyd.status.MoveStatus ophyd.status.DeviceStatus ophyd.status.Status ophyd.status.SubscriptionStatus
   :parts: 2

.. autoclass:: ophyd.status.Status
   :members:

.. autoclass:: ophyd.status.DeviceStatus
   :members:

.. autoclass:: ophyd.status.MoveStatus
   :members:

.. autoclass:: ophyd.areadetector.trigger_mixins.ADTriggerStatus
   :members:

.. autoclass:: ophyd.status.SubscriptionStatus
   :members:

.. autofunction:: ophyd.status.wait
