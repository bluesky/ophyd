.. ophyd documentation master file, created by
   sphinx-quickstart on Fri Nov  7 11:18:58 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Ophyd
=====

Ophyd represents hardware in Python as hierarchical objects grouping
together related values from the underlying control system.  This
structure allows :mod:`ophyd` to provide

* A consistent high-level interface across a wide-range of devices (
  which is used by :mod:`bluesky`).
* Direct low-level access to the underlying controls system for
  debugging and development.


By presenting a uniform interface experimental plans can be agnostic
to the details of the underlying hardware which simplifies writing
experimental plans.  For example, every device has a ``read`` method
which, somewhat tautologically, reads the device.  It is up to the
object to have an understanding of which of its signals are
interesting and should be included in the reading, to reach out and
fetch those values, and then to format them into a consistent format.
Similarly, if a device can be 'moved' (in the most general sense) then
it must provide a ``set`` method which is responsible for knowing how
to translate the user input into values that the control system
understands, setting those values, and then returning to the caller an
object which will signal when the requested move is complete.  This
provides a direct way to implement software pseudo motors.

:mod:`ophyd` contains a number of pre-built devices for common
hardware (and IOCs) as well as the tools to build custom devices.

Currently ophyd only support ``EPICS`` via :mod:`pyepics` (because it
is what we use at NSLS-II), however the library is designed to be
control-system agnostic and we are looking for a partner to port it to
other control systems.


.. toctree::
   :maxdepth: 1
   :caption: Ophyd's Core Functionality

   architecture
   device-overview
   signals
   status
   positioners
   debugging

.. toctree::
   :maxdepth: 2
   :caption: Built-in Device Support

   area-detector
   builtin-devices

.. toctree::
   :maxdepth: 1
   :caption: Developer notes

   api
   release_notes
   OEP/index
   docker
