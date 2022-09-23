Group Signals into Devices
==========================

In this tutorial we will group multiple Signals into a simple custom Device,
which enables us to conveniently connect to them and read them in batch.

Set up for tutorial
-------------------

Before you begin, install ``ophyd``, ``pyepics``, ``bluesky``, and ``caproto``,
following the :doc:`install`.

We'll start two simulated devices that implement a `random walk`_.

.. code:: bash

   python -m caproto.ioc_examples.random_walk --prefix="random-walk:horiz:" --list-pvs
   python -m caproto.ioc_examples.random_walk --prefix="random-walk:vert:" --list-pvs

.. ipython:: python
   :suppress:

   processes = []
   def run_example(module_name, args):
       import sys
       import subprocess
       import time
       p = subprocess.Popen([sys.executable, '-m', module_name, *args])
       processes.append(p)  # Clean this up at the end.
       time.sleep(1)  # Give it time to start up.
   run_example('caproto.ioc_examples.random_walk', ['--prefix', 'random-walk:horiz:'])
   run_example('caproto.ioc_examples.random_walk', ['--prefix', 'random-walk:vert:'])

Start your favorite interactive Python environment, such as ``ipython`` or
``jupyter lab``.

Define a Custom Device
----------------------

It's common to have more than one instance of a given piece of hardware and to
present each instance in EPICS with different "prefixes" as in:

.. code:: none

   # Device 1:
   random-walk:horiz:dt
   random-walk:horiz:x

   # Device 2:
   random-walk:vert:dt
   random-walk:vert:x

Ophyd makes it easy to take advantage of the nested structure of PV string,
where applicable. Define a subclass of :class:`ophyd.Device`.

.. ipython:: python

   from ophyd import Component, Device, EpicsSignal, EpicsSignalRO

   class RandomWalk(Device):
       x = Component(EpicsSignalRO, 'x')
       dt = Component(EpicsSignal, 'dt')

Up to this point we haven't actually created any signals yet or connected
to any hardware.  We have only *defined the structure* of this device and
provided the suffixes (``'x'``, ``'dt'``) of the relevant PVs.

Now, we create an instance of the device, providing the PV prefix that
identifies one of our IOCs.

.. ipython:: python

   random_walk_horiz = RandomWalk('random-walk:horiz:', name='random_walk_horiz')
   random_walk_horiz.wait_for_connection()
   random_walk_horiz

.. note:: 

   It is *conventional* to name the Python variable on the left the same as the
   value of ``name``, but not required. That is, this is conventional...
   
   .. code:: python

      a = RandomWalk("...", name="a")

   ...but all of these are also allowed.

   .. code:: python

      a = RandomWalk("...", name="b")  # local variable different from name
      a = RandomWalk("...", name="some name with spaces in it")
      a = b = RandomWalk("...", name="b")  # two local variables

In the same way we can connect to the other IOC. We create a second instance of
the same class.

.. ipython:: python

   random_walk_vert = RandomWalk('random-walk:vert:', name='random_walk_vert')
   random_walk_vert.wait_for_connection()
   random_walk_vert

Use it with the Bluesky RunEngine
---------------------------------

The signals can be used by the Bluesky RunEngine. Let's configure a RunEngine
to print a table.

.. ipython:: python

   from bluesky import RunEngine
   from bluesky.callbacks import LiveTable
   RE = RunEngine()
   token = RE.subscribe(LiveTable(["random_walk_horiz_x", "random_walk_horiz_dt"]))

We can access the components of ``random_walk_horiz`` like ``random_walk_horiz.x``
and use this to read them individually.

.. ipython:: python

   from bluesky.plans import count

   RE(count([random_walk_horiz.x], num=3, delay=1))

We can also read ``random_walk_horiz`` in its entirety as a unit, treating it as
a composite "detector".

.. ipython:: python

   RE(count([random_walk_horiz], num=3, delay=1))

Assign a "Kind" to Components
-----------------------------

In the example just above, notice that we are recording ``random_walk_horiz_dt``
in every row (i.e. every Event) because it is returned alongside
``random_walk_horiz_x`` in the reading.

.. ipython:: python

   random_walk_horiz.read()

This is probably not necessary. Unless we have some reason to expect that it
could be changed, it would be more useful to record ``random_walk_horiz_dt``
once per Run as part of the device's *configuration*.

Ophyd enables us to do this like so:

.. ipython:: python

   from ophyd import Kind

   random_walk_horiz.dt.kind = Kind.config

As a shorthand, a string alias is also accepted and normalized to enum member of
that name.

.. ipython:: python

   random_walk_horiz.dt.kind = "config"
   random_walk_horiz.dt.kind

Equivalently, we could have set the ``kind`` when we first defined the device, like so:

.. code:: python

   class RandomWalk(Device):
       x = Component(EpicsSignalRO, 'x')
       dt = Component(EpicsSignal, 'dt', kind="config")

Again, either enum ``Kind.config`` or string ``"config"`` are accepted.

The result is that ``random_walk_horiz_dt`` is moved from ``read()`` to
``read_configuration()``.

.. ipython:: python

   random_walk_horiz.read()
   random_walk_horiz.read_configuration()

.. note::

   In Bluesky's Document Model, the result of ``device.read()`` is placed in an
   Event Document, and the result of ``device.read_configuration()`` is placed in
   an Event Descriptor document. The Bluesky RunEngine always calls
   ``device.read_configuration()`` and captures that information the first time
   a given ``device`` is read.

For a larger example of Kind being used on a real device,
see `the source code for EpicsMotor`_.

.. ipython:: python
   :suppress:

   # Clean up IOC processes.
   for p in processes:
       p.terminate()
   for p in processes:
       p.wait()

.. _random walk: https://en.wikipedia.org/wiki/Random_walk

.. _the source code for EpicsMotor: https://github.com/bluesky/ophyd/blob/master/ophyd/epics_motor.py