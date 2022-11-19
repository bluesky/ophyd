*****
Ophyd
*****

|build_status| |coverage| |pypi_version| |license|

Ophyd is Python library for interfacing with hardware. It provides an
abstraction layer than enables experiment orchestration and data acquisition
code to operate above the specifics of particular devices and control systems.

Ophyd is typically used with the `Bluesky Run Engine`_ for experiment
orchestration and data acquisition. It is also sometimes used in a stand-alone
fashion.

Many facilities use ophyd to integrate with control systems that use `EPICS`_ ,
but ophyd's design and some of its objects are also used to integrate with
other control systems.

* Put the details specific to a device or control system behind a **high-level
  interface** with methods like ``trigger()``, ``read()``, and ``set(...)``.
* **Group** individual control channels (such as EPICS V3 PVs) into logical
  "Devices" to be configured and used as units with internal coordination.
* Assign readings with **names meaningful for data analysis** that will
  propagate into metadata.
* **Categorize** readings by "kind" (primary reading, configuration,
  engineering/debugging) which can be read selectively.

============== ==============================================================
PyPI           ``pip install ophyd``
Conda          ``pip install -c nsls2forge ophyd``
Source code    https://github.com/bluesky/ophyd
Documentation  https://blueskyproject.io/ophyd
============== ==============================================================

See the tutorials for usage examples.

.. |build_status| image:: https://github.com/bluesky/ophyd/workflows/Unit%20Tests/badge.svg?branch=master
    :target: https://github.com/bluesky/ophyd/actions?query=workflow%3A%22Unit+Tests%22
    :alt: Build Status

.. |coverage| image:: https://codecov.io/gh/bluesky/ophyd/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/bluesky/ophyd
    :alt: Test Coverage

.. |pypi_version| image:: https://img.shields.io/pypi/v/ophyd.svg
    :target: https://pypi.org/project/ophyd
    :alt: Latest PyPI version

.. |license| image:: https://img.shields.io/badge/License-BSD%203--Clause-blue.svg
    :target: https://opensource.org/licenses/BSD-3-Clause
    :alt: BSD 3-Clause License

.. _Bluesky Run Engine: http://blueskyproject.io/bluesky

.. _EPICS: http://www.aps.anl.gov/epics/

..
    Anything below this line is used when viewing README.rst and will be replaced
    when included in index.rst

See https://blueskyproject.io/ophyd for more detailed documentation.
