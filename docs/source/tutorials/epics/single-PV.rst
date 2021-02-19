A single EPICS PV
=================

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

   python -m caproto.ioc_examples_random_walk --list-pvs

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

Create an ophyd ``EpicsSignal``
-------------------------------

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

Use it with the Bluesky RunEngine
---------------------------------

The signal can be used by the Bluesky RunEngine. Let's set up a RunEngine to
print a table.

.. ipython:: python

   from bluesky import RunEngine
   from bluesky.callbacks import LiveTable
   RE = RunEngine()
   RE.subscribe(LiveTable(["time_delta"]))

Because the signal is writable, it can be scanned like a "motor". It can also
be read like a "detector". (In Bluesky, all things that are "motors" are also
"detectors".)

.. ipython:: python

   from bluesky.plans import count, list_scan

   RE(count([time_delta]))  # Use as a "detector".
   RE(list_scan([], time_delta, [0.1, 0.3, 1, 3]))  # Use as "motor'.

Use it directly
---------------

.. ipython:: python

   time_delta.read()

* EpicsSignal
* EpicsSignalRO
* Emphasize that if you want to use it with the RunEngine, you should stop here
  and let the RunEngine worry about read/write/subscribe.
* read
* write
* subscribe

.. ipython:: python
   :suppress:

   # Clean up IOC processes.
   for p in processes:
       p.terminate()
   for p in processes:
       p.wait()

.. _random walk: https://en.wikipedia.org/wiki/Random_walk
