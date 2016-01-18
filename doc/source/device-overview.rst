Overview of a Device
********************

All kinds of hardware -- motors, detectors, temperature controllers, robots --
are represented as a kind of ``Device`` object. All Devices have certain
methods and attributes in common.

.. autoclass:: ophyd.Device

High-level Interface (used by bluesky)
======================================

.. automethod:: ophyd.Device.read
.. automethod:: ophyd.Device.describe
.. automethod:: ophyd.Device.set
.. automethod:: ophyd.Device.trigger
.. automethod:: ophyd.Device.stage
.. automethod:: ophyd.Device.unstage
.. automethod:: ophyd.Device.configure
.. automethod:: ophyd.Device.read_configuration
.. automethod:: ophyd.Device.describe_configuration

Low-level Interface (for exploration, debugging)
================================================

.. autoattribute:: ophyd.Device.connected

   ``True`` is all components are connected, ``False`` if any are not

.. automethod:: ophyd.Device.wait_for_connection
.. automethod:: ophyd.Device.get
.. automethod:: ophyd.Device.put
.. automethod:: ophyd.Device.get_device_tuple
