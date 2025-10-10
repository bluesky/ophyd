.. _signal_indx:

.. currentmodule:: ophyd.signal

Signals
*******

.. FIXME: Start with a non-EPICS description of Signal.

   Signal represents a single value of the hardware system.  (Could be RO, RW, or WO.)

.. TODO: Device is not documented?

In `EPICS <https://epics-controls.org/>`_, :class:`~EpicsSignal` maybe backed by
a read-only process variable (`PV
<https://docs.epics-controls.org/en/latest/getting-started/EPICS_Intro.html>`_),
a single read-write PV, or a pair of read and write PVs, grouped together.  In
any of those cases, a single value is exposed to `bluesky
<https://blueskyproject.io/bluesky>`_.  For more complex hardware, for example
an EPICS `motor record <http://www.aps.anl.gov/bcda/synApps/motor/>`_, the
relationships between the individual process variables need to be encoded in a
:class:`~device.Device` (see the :class:`~ophyd.epics_motor.EpicsMotor` class).
A :class:`~device.Device` describes which **Signals** are grouped together, and
how to manipulate them in a coordinated fashion to achieve the high-level action
(moving a motor, changing a temperature, opening a valve, or taking data).  More
complex devices, like a `diffractometer <https://blueskyproject.io/hklpy2>`_ or
an :ref:`area detector <explain_areadetector>`, can be assembled from simpler
component devices.

.. TODO: Next paragraph should move before the EpicsSignal paragraph above.
.. FIXME: tree & leaf metaphor does not need EPICS reference

A :class:`~Signal` is much like a :class:`~ophyd.device.Device` -- they share
almost the same interface -- but a :class:`~Signal` has no sub-components. In
ophyd's hierarchical, tree-like representation of a complex piece of hardware,
the signals are the leaves. Each one represents a single PV or a read--write
pair of PVs.

Signal Attributes
-----------------

All ophyd Signal classes have these attributes:

.. index:: kind attribute
.. _kind:

:attr:`kind`
++++++++++++

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
the :attr:`hints` attribute of the :class:`~device.Device`.

.. index:: labels attribute
.. _labels:

:attr:`labels`
++++++++++++++

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

.. _signal_classes:

Signal Classes
--------------

.. autosummary::
   :toctree: ../generated

   Signal
   SignalRO
   ArrayAttributeSignal
   AttributeSignal
   DerivedSignal

.. _signal_classes_epics:

Signal Classes for EPICS
----------------------------

.. autosummary::
   :toctree: ../generated

   EpicsSignalBase
   EpicsSignal
   EpicsSignalRO
   EpicsSignalNoValidation

.. _signal_classes_internal:

Signal Classes for Internal Use
--------------------------------

.. autosummary::
   :toctree: ../generated

   InternalSignal
   InternalSignalMixin

.. _signal_exceptions:

Exceptions
----------

A :class:`~ConnectionTimeoutError` (or :class:`~ReadTimeoutError`) typically
occurs when an :class:`~EpicsSignal` fails to connect (or respond to a read
request) within a specified time limit. This can happen due to network issues,
the EPICS IOC (server) or PV is unresponsive or unavailable, or the PV name is
incorrect. Here's an example how these exceptions might be used:

.. code-block:: python
	:linenos:

	from ophyd import EpicsSignal
	from ophyd.signal import ConnectionTimeoutError, ReadTimeoutError

	signal = EpicsSignal("IOC:pv", name='signal')
	try:
		# Set timeouts of 5 seconds.
		signal.wait_for_connection(timeout=5)
		value = signal.get(timeout=5)  
		print(f"{signal.name}={value}")
	except ConnectionTimeoutError:
		print("Connection timeout. Please check EPICS PV {signal.pvname!r}.")
	except ReadTimeoutError:
		print("Read timeout. Please check EPICS PV {signal.pvname!r}.")

An :class:`~InternalSignalError` is raised when an :class:`~InternalSignal` is
written from outside of its own parent class (the :class:`~ophyd.device.Device`
that defined this :class:`~InternalSignal`).  Since an :class:`~InternalSignal`
is designed to be updated only from within the parent class, any other attempts
to write (from outside the parent) will raise this exception. All writes must be
done with ``internal=True``.

.. autoexception:: ConnectionTimeoutError
.. autoexception:: InternalSignalError
.. autoexception:: ReadTimeoutError

.. automodule:: ophyd.signal
   :noindex:

----

.. currentmodule:: ophyd.signal

.. rubric:: Signal Classes
.. autosummary::
   :toctree: ../generated

   ArrayAttributeSignal
   AttributeSignal
   DerivedSignal
   EpicsSignal
   EpicsSignalBase
   EpicsSignalNoValidation
   EpicsSignalRO
   InternalSignal
   InternalSignalMixin
   Signal
   SignalRO

------------

.. TODO

.. currentmodule:: ophyd.areadetector.base
.. autosummary::
   :toctree: ../generated

   NDDerivedSignal
