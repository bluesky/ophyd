.. note::

    Ophyd.v2 is included on a provisional basis until the v2.0 release and 
    may change API on minor release numbers before then

Make a Device
=============

.. currentmodule:: ophyd.v2.core

To make a Device using Ophyd.v2, you need to subclass from the `Device`
class, create some `Signal` instances, implement :meth:`~Device.connect()` and
implement some other suitable Bluesky `hardware_interface`.

The rest of this guide will show examples from ``ophyd/v2/epicsdemo/__init__.py``

Readable
--------

For a simple `bluesky.protocols.Readable` object like a `Sensor`, you could just
implement these methods directly:

.. literalinclude:: ../../../ophyd/v2/epicsdemo/__init__.py
   :pyobject: Sensor

The PV prefix is passed to the constructor and stored, then Signals constructed
and stored on the Device. Each one is passed its Python type, which could be a
primitive (`str`, `int`, `float`), an array (`numpy.typing.NDArray`), or an enum
(`enum.Enum`). It is also passed the PV suffix. Finally ``set_name()`` is called
which will give a name to the Device and all its child Devices.

The ``connect()`` method takes an additional prefix (in case this Device is nested
in another) and passes them to the `connect_children()` function that will
connect all the Signals in parallel.

All the other methods directly implement the Bluesky protocols by calling
down to a single relevant Signal. This means that only ``energy`` will be
reported as configuration, and only ``value`` will be reported in read.

Movable
-------

For a more complicated `bluesky.protocols.Readable` device like a `Mover`, you
can use the `HasReadableSignals` mix-in class:

.. literalinclude:: ../../../ophyd/v2/epicsdemo/__init__.py
   :pyobject: Mover

This will add the ``read()``, ``describe()``, ``read_configuration()`` and
``describe_configuration()`` methods, and add ``stage()`` and ``unstage()``
methods to cache PV values during a scan. You call ``set_readable_signals()`` to
show the:

- Optional ``primary`` signal: a Signal that should be renamed to take the name
  of the Device and output at ``read()``
- ``read`` signals: Signals that should be output to ``read()`` without renaming
- ``config`` signals: Signals that should be output to ``read_configuration()``
  without renaming

The ``connect()`` method is again the same as `Sensor`.

Finally we create a ``set()`` method to implement `bluesky.protocols.Movable`.
This creates a `coroutine` ``do_set()`` which gets the old position, units and
precision in parallel, sets the setpoint, then observes the readback value,
informing watchers of the progress. When it gets to the requested value it
completes. This co-routine is wrapped in a timeout handler, and passed to an
`AsyncStatus` which will start executing it as soon as the Run Engine adds a
callback to it. The ``stop()`` method then pokes a PV if the move needs to be
interrupted. 

Assembly
--------

Compound assemblies can be used to group Devices into larger logical Devices:

.. literalinclude:: ../../../ophyd/v2/epicsdemo/__init__.py
   :pyobject: SampleStage

.. note::

    This does not inherit from `HasReadableSignals` or implement the ``read()``
    method. This means you can ``rd sample_stage.x``, but not ``rd sample_stage``.
    You can implement your own ``read()`` method by using `merge_gathered_dicts`
    on child Devices if you want this functionality.
