Single EPICS PVs
================

In this tutorial we will read, write, and monitor an EPICS PV in ophyd.

Set up for tutorial
-------------------

Before you begin, install ``ophyd``, ``pyepics``, ``bluesky``, and ``caproto``,
following the :doc:`install`.

We'll start this simulated hardware that implements a `random walk`_. It has
just two PVs. One is a tunable parameter, ``random_walk:dt``, the time between
steps. The other is ``random_walk:x``, the current position of the random
walker.

.. code:: bash

   python -m caproto.ioc_examples.random_walk --list-pvs

.. ipython:: python
   :suppress:

   processes = []
   def run_example(module_name):
       import sys
       import subprocess
       import time
       p = subprocess.Popen([sys.executable, '-m', module_name])
       processes.append(p)  # Clean this up at the end.
       time.sleep(1)  # Give it time to start up.
   run_example('caproto.ioc_examples.random_walk')

Start your favorite interactive Python environment, such as ``ipython`` or
``jupyter lab``.

Connect to a PV from Ophyd
--------------------------

Let's connect to the PV ``random_walk:dt`` from Ophyd. We need two pieces of
information:

* The PV name, ``random_walk:dt``.
* A human-friendly name. This name is used to label the readings and will be
  used in any downstream data analysis or file-writing code. We might choose,
  for example, ``time_delta``.

.. ipython:: python

   from ophyd.signal import EpicsSignal

   time_delta = EpicsSignal("random_walk:dt", name="time_delta")

.. note::

   It is *conventional* to name the Python variable on the left the same as the
   value of ``name``, but not required. That is, this is conventional...

   .. code:: python

      a = EpicsSignal("...", name="a")

   ...but all of these are also allowed.

   .. code:: python

      a = EpicsSignal("...", name="b")  # local variable different from name
      a = EpicsSignal("...", name="some name with spaces in it")
      a = b = EpicsSignal("...", name="b")  # two local variables

Next let's connect to ``random_walk:x``. It happens that this PV is not
writable---any writes would be rejected by EPICS---so we should use a read-only
EpicsSignal, :class:`~ophyd.signal.EPICSSignalRO`, to represent it in in ophyd. In
EPICS, you just have to "know" this about your hardware. Fortunately if, in our
ignorance,  we used writable :class:`~ophyd.signal.EpicsSignal` instead, we could
still use it to read the PV. It would just have a vestigial ``set()`` method
that wouldn't work.

.. ipython:: python

   from ophyd.signal import EpicsSignalRO

   x = EpicsSignalRO("random_walk:x", name="x")

Use it with the Bluesky RunEngine
---------------------------------

The signals can be used by the Bluesky RunEngine. Let's configure a RunEngine
to print a table.

.. ipython:: python
   :suppress:

   time_delta.wait_for_connection()
   x.wait_for_connection()

.. ipython:: python

   from bluesky import RunEngine
   from bluesky.callbacks import LiveTable
   RE = RunEngine()
   token = RE.subscribe(LiveTable(["time_delta", "x"]))

Because ``time_delta`` is writable, it can be scanned like a "motor". It can
also be read like a "detector". (In Bluesky, all things that are "motors" are
also "detectors".)

.. ipython:: python

   from bluesky.plans import count, list_scan

   RE(count([time_delta]))  # Use as a "detector".
   RE(list_scan([], time_delta, [0.1, 0.3, 1, 3]))  # Use as "motor".

For the following example, set ``time_delta`` to ``1``.

.. ipython:: python

   from bluesky.plan_stubs import mv

   RE(mv(time_delta, 1))

We know that ``x`` represents a time-dependent variable. We can "poll" it at
regular intervals

.. ipython:: python

   RE(count([x], num=5, delay=0.5))  # Read every 0.5 seconds.

but this required us to choose an update frequency (``0.5``). It's often better
to rely on the control system to *tell* us when a new value is available. In
this example, we accumulate updates for ``x`` whenever it changes.

.. ipython:: python

   from bluesky.plan_stubs import monitor, unmonitor, open_run, close_run, sleep

   def monitor_x_for(duration, md=None):
       yield from open_run(md)  # optional metadata
       yield from monitor(x, name="x_monitor")
       yield from sleep(duration)  # Wait for readings to accumulate.
       yield from unmonitor(x)
       yield from close_run()

.. ipython:: python

   RE.unsubscribe(token)  # Remove the old table.
   RE(monitor_x_for(3), LiveTable(["x"], stream_name="x_monitor"))

If you are a scientist aiming to use Ophyd with the Bluesky Run Engine, you may
stop at this point or read on to learn more about how the Run Engine interacts
with these signals. If you are a controls engineer, the details that follow are
likely important to you.

Use it directly
---------------

.. note::

   These methods should *not* be called inside a Bluesky plan.
   See [TODO link to explanation.]

Read
^^^^

The signal can be read. It return a dictionary with one item. The key is the
human-friendly ``name`` we specified. The value is another dictionary,
containing the ``value`` and the ``timestamp`` of the reading from the control
system (in this case, EPICS).

.. ipython:: python

   time_delta.read()

Describe
^^^^^^^^

Additional metadata is available. This always includes the data type, shape,
and source (e.g.  PV). It may also include units and other metadata.

.. ipython:: python

   time_delta.describe()

Set
^^^

This signal is writable, so it can also be set.

.. ipython:: python

   time_delta.set(10).wait()  # Set it to 10 and wait for it to get there.

Sometimes hardware gets stuck or does not do what it is told, and so it is good
practice to put a timeout on how long you are willing to wait until deciding
that there is an error that needs to be handled somehow.

.. ipython:: python

   time_delta.set(10).wait(timeout=1)  # Set it to 10 and wait up to 1 second.

If the signal fails to arrive, a ``TimeoutError`` will be raised.

Note that ``set(...)`` starts the motion but does *not* wait for it to
complete. It is a fast, "non-blocking" operation. This enables you to run
code between starting a motion and completing it.

.. ipython:: python

   status = time_delta.set(5)
   print("Moving to 5...")
   status.wait(timeout=1)
   print("Moved to 5.")

.. note::

   To move more than one signal in parallel, use the :func:`ophyd.status.wait`
   *function*.

   .. code:: python

      from ophyd.status import wait

      # Given signals a and b, set both in motion.
      status1 = a.set(1)
      status2 = b.set(1)
      # Wait for both to complete.
      wait(status1, status2, timeout=1)

For more on what you can do with ``status``, see [...].

Subscribe
^^^^^^^^^

What's the best way to read a signal that changes over time, like our ``x``
signal?

First, set ``time_delta`` to a reasonable value like ``1``. This controls the
update rate of ``x`` in our random walk simulation.

.. ipython:: python

   time_delta.set(1).wait()

We could poll the signal in a loop and collect N readings spaced T seconds
apart.

.. code:: python

   # Don't do this.
   N = 5
   T = 0.5
   readings = []
   for _ in range(N):
       time.sleep(T)
       reading = x.read()
       readings.append(reading)

There are two problems with this counterexample.

1. We might not know how often we need to check for updates.
2. We often want to watch *multiple* signals with different update rates, and
   this pattern would quickly become messy.

Alternatively, we can use *subscription*.

.. ipython:: python

   from collections import deque

   def accumulate(value, old_value, timestamp, **kwargs):
       readings.append({"x": {"value": value, "timestamp": timestamp}})
   readings = deque(maxlen=5)
   x.subscribe(accumulate)

When the control system has a new ``reading`` for us, it calls
``readings.append(reading)`` from a background thread. If we do other work or
sleep for awhile and then check back on ``readings`` we'll see that it has some
items in it.

.. ipython:: python
   :suppress:

   import time; time.sleep(3)

.. ipython:: python

   readings

It will keep the last ``5``. We used a :class:`~collections.deque` instead of a
plain `list` here because a `list` would grow without bound and, if left to
run long enough, consume all available memory, crashing the program.

.. ipython:: python
   :suppress:

   # Clean up IOC processes.
   for p in processes:
       p.terminate()
   for p in processes:
       p.wait()

.. _random walk: https://en.wikipedia.org/wiki/Random_walk
