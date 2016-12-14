.. ophyd documentation master file, created by
   sphinx-quickstart on Fri Nov  7 11:18:58 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Ophyd
=====

Ophyd represents hardware in Python, providing a consistent interface for
reading values from and sending values to any device.

To represent a complex device with many components, it employs a hierarchical
structure wherein a device is a composition of subdevices, all sharing the
common interface.

Why not just use pyepics?
-------------------------

Ophyd builds on pyepics, Python bindings to EPICS. It provides full access to
the underlying pyepics PV objects, but it also provides some higher-level
abstractions.

The purpose of these abstractions is make all hardware look the same as much as
possible, enabling the same experimental control logic to apply to different
hardware. For example, from this point of view performing a temperature sweep
is no different that scanning a motor. The abstractions in ophyd present a
standard interface for maximum generality. But they do not preclude direct
access to the individual PVs, which can be important for debugging or
interactive exploration.

* A **Signal** represents a single value. In EPICS, it corresponds to either
  a single read-only PV or a pair of read and write PVs, grouped together. It
  assigns a human-readable name (e.g., 'temperature') which is more natural in
  the analysis phase than the raw PV names.
* A **Device** is composed of Signals or of other Devices. Devices can be
  nested. Some devices map to single pieces of hardware (like a motor).
  Others group together many different pieces of hardware (like a
  diffractometer). In one process, the same PVs might appear in multiple
  different Devices, so organized for different uses.

Signals and devices have:

* a ``connected`` attribute, to quickly check whether *all* the involved PVs
  are responding
* a ``name`` attribute, assigning a human-friendly alias (e.g., "temperature")
  which is often more natural than the raw PV name in the analysis phase
* a means of designating signals that should included in a typical reading
  (``read_attrs`` for "read attriubtes"), signals that change rarely
  (``configuration_attrs`` for "configuration attributes") and should be read
  only when known to change, and signals that should be not read at all (a
  common example: the hundreds of rarely-touched PVs in the area detector
  plugin).
* a single ``read`` method which reads the values of all a device's designated
  components and collates them into a single, labeled result
* a single ``describe`` method which extrats the metadata (PV, units,
  precision, data type, etc.) of all a device's designated components


.. toctree::
   :maxdepth: 1
   :caption: Contents

   device-overview
   commands
   builtin-devices
   positioners
   custom-devices
   signals
   area-detector
   architecture
   OEP/index
   release_notes
