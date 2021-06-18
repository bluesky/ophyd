.. _signal_indx:

Signals
*******

In EPICS, **Signal** maybe backed by a read-only PV, a single
read-write PV, or a pair of read and write PVs, grouped together.  In
any of those cases, a single value is exposed to `bluesky
<https://nsls-ii.github.io/bluesky>`_.  For more complex hardware, for
example a `motor record
<http://www.aps.anl.gov/bcda/synApps/motor/>`_, the relationships
between the individual process variables needs to be encoded in a
:class:`~device.Device` (a :class:`~epics_motor.EpicsMotor` class
ships with ophyd for this case).  This includes both what **Signals**
are grouped together, but also how to manipulate them a coordinated
fashion to achieve the high-level action (moving a motor, changing a
temperature, opening a valve, or taking data).  More complex devices,
like a diffractometer or a Area Detector, can be assembled out of
simpler component devices.


A ``Signal`` is much like a ``Device`` -- they share almost the same
interface -- but a ``Signal`` has no sub-components. In ophyd's hierarchical,
tree-like representation of a complex piece of hardware, the signals are
the leaves. Each one represents a single PV or a read--write pair of PVs.

.. index:: kind attribute
.. _kind:

:attr:`kind`
-------------

The :attr:`kind` attribute is the means to identify a signal that is
relevant for handling by a callback.
:attr:`kind` controls whether the signal's parent
Device will include it in ``read()``, ``read_configuration()``, and/or
``hints.fields``.
The first use of :attr:`kind` is to inform
visualization callbacks about the independent and dependent display
axes for plotting.
A Component marked as hinted will return a dictionary with that component's fields list.

The :attr:`kind` attribute takes string values of: ``config``,
``hinted``, ``normal``, and ``omitted``.
These values are like bit flags, a signal could have multiple values.

The value may be set either when the :class:`~signal.Signal` is created or
programmatically.
Use the :attr:`kind` attribute when creating a :class:`~signal.Signal`
or :class:`Component`, such as:

.. code-block:: python

  from ophyd import Kind

  camera.stats1.total.kind = Kind.hinted
  camera.stats2.total.kind = Kind.hinted

or, as a convenient shortcut (eliminates the import)

.. code-block:: python

  camera.stats1.total.kind = 'hinted'
  camera.stats2.total.kind = 'hinted'

With ophyd v1.2.0 or higher, use :attr:`kind` instead of setting
the :attr:`hints` attribute of the :class:`~device.Device`.  See
:ref:`hints_fields` for more details.

.. index:: labels attribute
.. _labels:

:attr:`labels`
--------------

:class:`~signal.Signal` and :class:`~device.Device` now accept
a :attr:`labels` attribute.  The value is a list of text strings
--- presumed but not (yet) forced to be strings --- which the user can use
for grouping and displaying available hardware or other ophyd constructs.
The labels are accessible via
an attribute ``_ophyd_labels_``, so named to facilitate duck-typing across
libraries. For example, the bluesky IPython "magics" use this to identify
objects for the purpose of displaying them in labeled groups.

The IPython magic command ``wa`` (available if bluesky is installed as well
as ophyd) groups items by labels.  Here is an example:

.. code-block:: python

	m1 = EpicsMotor('prj:m1', name='m1', labels=("general",))
	m2 = EpicsMotor('prj:m2', name='m2', labels=("general",))

	class MyRig(Device):
		t = Component(EpicsMotor, "m5", labels=("rig",),)
		l = Component(EpicsMotor, "m6", labels=("rig",))
		b = Component(EpicsMotor, "m7", labels=("rig",))
		r = Component(EpicsMotor, "m8", labels=("rig",))


	rig = MyRig("prj:", name="rig")

Then in an ipython session:

.. code-block:: python

	In [1]: wa
	general
	  Positioner                     Value       Low Limit   High Limit  Offset
	  m1                             1.0         -100.0      100.0       0.0
	  m2                             0.0         -100.0      100.0       0.0

	  Local variable name                    Ophyd name (to be recorded as metadata)
	  m1                                     m1
	  m2                                     m2

	rig
	  Positioner                     Value       Low Limit   High Limit  Offset
	  rig_b                          0.0         -100.0      100.0       0.0
	  rig_l                          0.0         -100.0      100.0       0.0
	  rig_r                          0.0         -100.0      100.0       0.0
	  rig_t                          0.0         -100.0      100.0       0.0

	  Local variable name                    Ophyd name (to be recorded as metadata)
	  rig.b                                  rig_b
	  rig.l                                  rig_l
	  rig.r                                  rig_r
	  rig.t                                  rig_t


.. automodule:: ophyd.signal
   :noindex:
