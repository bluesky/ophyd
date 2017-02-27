.. ophyd documentation master file, created by
   sphinx-quickstart on Fri Nov  7 11:18:58 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Ophyd
=====

Ophyd represents hardware in Python and provides a consistent high-level interface
across a wide-range of devices which is used by ``bluesky``.  By presenting a
uniform interface experimental plans can be agnostic to the details of the underlying
hardware.  In addition to the high-level interface, `ophyd` provides low-level access
to the underlying controls system (in this ``EPICS`` via `pyepics`) for debugging
and development.

.. toctree::
   :maxdepth: 2
   :caption: Standard Devices

   builtin-devices


.. toctree::
   :maxdepth: 1
   :caption: Signals and Devices

   architecture
   device-overview
   positioners
   signals
   status
   area-detector


.. toctree::
   :maxdepth: 1
   :caption: CLI tools

   commands

.. toctree::
   :maxdepth: 1
   :caption: Developer notes

   release_notes
   OEP/index

.. toctree::
   :maxdepth: 1
   :caption: API

   api
