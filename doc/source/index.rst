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


Contents:

.. toctree::
   :maxdepth: 1

   device-overview
   commands
   builtin-devices
   positioners
   custom-devices
   signals
   area-detector
   architecture
