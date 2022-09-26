.. note::

    Ophyd.v2 is included on a provisional basis until the v2.0 release and 
    may change API on minor release numbers before then

Using existing Devices
======================

To use an Ophyd Device that has already been written, you need to make a
RunEngine, then instantiate the Device in that process. This tutorial will take
you through this process. It assumes you have already run through the Bluesky
tutorial on `tutorial_run_engine_setup`.

Create Startup file
-------------------

For this tutorial we will use IPython. We will instantiate the RunEngine and
Devices in a startup file. This is just a regular Python file that IPython
will execute before giving us a prompt to execute scans. Copy the text
below and place it in an ``epics_demo.py`` file:

.. literalinclude:: ../examples/epics_demo.py
    :language: python

The top section of the file is explained in the Bluesky tutorial, but the bottom
section is Ophyd specific.

First of all we start up a specific EPICS IOC for the demo devices. This is only
used in this tutorial:

.. literalinclude:: ../examples/epics_demo.py
    :language: python
    :start-after: # Start IOC
    :end-before: # Create v1

Next we create an example v1 Device for comparison purposes. It is here to show
that you can mix v1 and v2 Devices in the same RunEngine:

.. literalinclude:: ../examples/epics_demo.py
    :language: python
    :start-after: # Create v1
    :end-before: # Create v2

Finally we create the v2 Devices imported from the `epicsdemo` module:

.. literalinclude:: ../examples/epics_demo.py
    :language: python
    :start-after: # Create v2

The first thing to note is `with`. This uses a `DeviceCollector` as a context
manager to collect up the top level `Device` instances created in the context,
and run the following:

- If ``set_name=True`` (the default), then call `Device.set_name` passing the
  name of the variable within the context. For example, here we call
  ``det.set_name("det")``
- If ``connect=True`` (the default), then call `Device.connect` in parallel for
  all top level Devices, waiting for up to ``timeout`` seconds. For example,
  here we call ``asyncio.wait([det.connect(), samp.connect()])``
- If ``sim=True`` is passed, then don't connect to PVs, but set Devices into
  simulation mode
- If ``prefix`` is passed, then use it as a prefix for all PV prefixes.

The Devices we create in this example are a "sample stage" with a couple of
"movers" called ``x`` and ``y`` and a "sensor" called ``det`` that gives a
different reading depending on the position of the "movers".

.. note::

    There are very few Devices included in ophyd.v2, see the ophyd-epics-devices
    and ophyd-tango-devices for some common ones associated with each control
    system

Run IPython
-----------

You can now run ipython with this startup file::

    $ ipython -i epics_demo.py
    IPython 8.5.0 -- An enhanced Interactive Python. Type '?' for help.

    In [1]:

.. ipython:: python
    :suppress:

    import sys
    from pathlib import Path
    sys.path.append(str(Path(".").absolute()/"docs/user_v2/examples"))
    from epics_demo import *
    # Turn off progressbar and table
    RE.waiting_hook = None
    bec.disable_table()

This is like a regular python console with the contents of that file executed.
IPython adds some extra features like tab completion and magics (shortcut
commands). Ophyd adds some magics of its own that we will explore now.

Try some magics
---------------

We can move the ``samp.x`` mover to 100mm using `bluesky.plan_stubs.mv`:

.. ipython::

    In [1]: mov samp.x 100

We can print the primary reading of ``samp.x``, in this case its readback value,
using `bluesky.plan_stubs.rd`:

.. ipython::

    In [1]: rd samp.x

We can do a relative move of ``samp.x`` by 10mm, using `bluesky.plan_stubs.mvr`:

.. ipython::

    In [1]: movr samp.x -10

Individual Devices will also expose some of the parameters of the underlying
hardware on itself. In the case of a `Mover`, we can set and get its
``velocity``:

.. ipython::

    In [1]: rd samp.x.velocity

Do a scan
---------

We can also use the `bluesky.run_engine.RunEngine` to run scans. For instance we
can do a `bluesky.plans.grid_scan` of ``x`` and ``y`` and plot ``det``:

.. ipython::

    @savefig grid_scan1.png width=4in
    In [1]: RE(bp.grid_scan([det], samp.x, 1, 2, 5, samp.y, 1, 2, 5))

There is also an "energy switch" that can be changed to modify the ``det`` output.

.. ipython::

    In [1]: rd det.energy

Although this is an :class:`~enum.Enum` and programmatic code should import and
use instances of :class:`~ophyd.v2.epicsdemo.Energy`, we can set it using a
string value on the commandline:

.. ipython::

    In [1]: mov det.energy "High"

The same scan will now give a slightly different output. If we include the v1
device we can see it gives the same result:

.. ipython::

    @savefig grid_scan2.png width=4in
    In [1]: RE(bp.grid_scan([det, det_old], samp.x, 1, 2, 5, samp.y, 1, 2, 5))

.. seealso::

    How-to `../how-to/make-a-device` to make your own Ophyd v2 Devices.