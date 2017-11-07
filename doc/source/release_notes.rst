Release Notes
-------------

v1.0.0
======

This tag marks an important release for ophyd, signifying the conclusion of
the early development phase. From this point on, we intend that this project
will be co-developed between multiple facilities. The 1.x series is planned to
be a long-term-support release.

API Changes
***********

* To access the human-friendly summary of a Device's layout, use
  ``device.summary()`` instead of ``print(device)``. The verbosity of the
  summary was overwhelming when it appeared in error messages and logs, so it
  was moved from ``Device.__str__`` this new method. Now ``Device.__str__``
  gives the same result as ``Device.__repr__``, as it did before v0.7.0.
* Add (empty) hints to `~ophyd.sim.SynSignalWithRegistry`.

Bug Fixes
*********

* Initiate :class:`~ophyd.sim.SynSignal` with a function that returns ``None``
  if no ``func`` parameter is provided.
* Make ophyd importable without pyepics and libca.

0.8.0
=====

API Changes
***********

* Make the ``name`` keyword to Device a required, keyword-only argument. This
  ensures that the names that appear in the read dictionary are always
  human-readable.
* When a ``PseudoPositioner`` is set with only a subset of its parameters
  specified, fill in the unspecified values with the current *target* position,
  not the current *actual* position.

Deprecations
************

* The ``signal_names`` attribute of devices has been renamed
  ``component_names`` for clarity because it may include a mixture of Signals
  and Devices -- any Components. The old name now issues a warning when
  accessed, and it may be removed in a future release of ophyd.
* Status objects' new ``add_callback`` method and ``callbacks`` attribute
  should be preferred over the ``finished_cb`` property, which only supports
  one callback and now warns if set or accessed.

Enhancements
************

* Add ``ophyd.sim`` module with various synthetic 'hardware' for testing and
  teaching.
* The 'children' of a ``PseudoPositioner`` can now be simultaneously used as
  independent axes in a bluesky plan.
* Add ``SubscriptionStatus``, which reports done when a Python function of the
  subscription returns ``True``.
* It is possible to register more than one callback function to be called on
  completion of a Status object (i.e. when a Device is finished triggering or
  moving).
* Status objects support ``__and__``, such that ``status1 & status2`` return a
  new status object that completes when both ``status1`` and ``status2`` are
  complete.
* Do not require a ``prefix`` argument to ``Device``. It is not applicable in
  cases of synthetic 'hardware'.
* Add ``MotorBundle`` for bundling ``EpicsMotors`` and automatically composing
  a useful combined hint.
* Add hints to ``PseudoSingle``, ``PseudoPositioner``, and ``SoftPositioner``.
* Make it possible to plug in a different "control layer" --- i.e. an interface
  to EPICS other than pyepics. This is experimental and may be changed in the
  future in a way that is not backward-compatible.

Bug Fixes
*********

* Avoid a race condition when timing out during a settle time.

Internal Changes
****************

* Reduce set_and_wait log messages to DEBUG level.
* Refactor OphydObj callbacks to make the logic easier to follow. This change
  is fully backward-compatible.

0.7.0
=====

API Changes
***********

* The module :mod:`ophyd.commands`, a grab bag of convenient tools, has been
  entirely removed. The functionality is available in other ways:

    * The functions :func:`mov` and :func:`movr` ("move" and "move relative")
      have been replaced by IPython magics, provided in bluesky v0.10.0:

      .. code-block:: python

         %mov eta 3 temp 273
         %movr eta 1 temp -5

    * The function :func:`wh_pos` for surveying current positioners has also
      been supplanted by an IPython magic packaged with bluesky: ``%wa`` (short
      for "where all", an abbreviation borrowed from SPEC).

       .. code-block:: python

          %wa

    * The fucntionality of :func:`set_pos`---setting zero---is available via a
      device method :meth:`set_current_pos`, if applicable.

    * The functionality of :func:`set_lm` for altering limits has been removed.
      It is not something users should generally change, and now must be done
      directly via EPICS or pyepics.

    * The logging-related functionality, including all functions named
      ``log_*`` and also :func:`get_all_positioners` have been moved to
      `pyOlog <https://github.com/NSLS-II/pyOlog>`_.

    * The function ``setup_ophyd`` was merely a shim to
      :func:`ophyd.setup_ophyd`, which is still available as a top-level
      import.

* When recursing through complex devices, ``read()`` in no longer called as
  part of ``read_configuration()``.
  For complex devices, the same child device may be used in both ``read_attrs``
  and ``read_configuration``.  Putting the read values into the configuration
  is generically not correct. For example, the mean_value of a stats plugin for
  Area Detector should be in the ``read()`` but not in the result of
  ``read_configuration()``. At the bottom, Signals fall back to ``read()`` for
  their read_configuration implementation.
* The area detector 'EnableCallbacks' signal is set using its integer
  representation instead of its enum string. The string representation was
  changed on the NDPluginBase.template file in upstream Area Detector. The int
  value is stable (we hope).
* Low-level changes related to integration between ophyd's area detector code
  and databroker/filestore:

    * Ophyd's optional dependency on filestore, which is now a deprecated
      package, has been replaced by an optional dependency on databroker. In
      area detector classes, the keyword argument and attribute ``fs`` has been
      changed to ``reg``, short for "registry".
    * The ``FileStoreBulkWrite`` mixin classes have been removed. Now that the
      Registry is generating the datum UIDs the 'stash, emit on read, and then
      insert on unstage' is no longer possible.  This means we will never let a
      datum_id which is not in a Registry out into the EventSources.  This
      change is driven by the need to support column based backends from Assets.
    * The method ``generate_datum`` on area detector file plugins requires an
      additional argument, ``datum_kwargs``.

Enhancements
************

* Many devices picked up a new ``hints`` property. Its goal is to highlight the
  most interesting or important fields---often a small subset of all the fields
  that are read---in support of automated visualization and processing. It does
  not affect what is read or recorded; nothing is permanently altered or lost
  if the hints are incorrect. The content of hints may be changed in future
  releases, as this feature is experimental. For now, ``hints`` is a dictionary
  with the key ``fields`` mapped to a list of field names. For movable
  devices, these fields are expected to represent the the independent axes of
  the device. For devices that are only readable, these fields represent the
  most interesting fields, i.e. the fields most likely to be desired in a table
  or plot.
* The string representation of a device, accessible via ``str(...)`` or
  ``print(...)``, provides a human-readable summary of its attributes and
  fields. Example:

  .. code-block:: none

      In [5]: motor = EpicsMotor('XF:31IDA-OP{Tbl-Ax:X1}Mtr', name='motor')

      In [6]: print(motor)
      data keys (* hints)
      -------------------
      *motor
       motor_user_setpoint

      read attrs
      ----------
      user_readback        EpicsSignalRO       ('motor')
      user_setpoint        EpicsSignal         ('motor_user_setpoint')

      config keys
      -----------
      motor_acceleration
      motor_motor_egu
      motor_user_offset
      motor_user_offset_dir
      motor_velocity

      configuration attrs
      ----------
      motor_egu            EpicsSignal         ('motor_motor_egu')
      velocity             EpicsSignal         ('motor_velocity')
      acceleration         EpicsSignal         ('motor_acceleration')
      user_offset          EpicsSignal         ('motor_user_offset')
      user_offset_dir      EpicsSignal         ('motor_user_offset_dir')

      Unused attrs
      ------------
      offset_freeze_switch EpicsSignal         ('motor_offset_freeze_switch')
      set_use_switch       EpicsSignal         ('motor_set_use_switch')
      motor_is_moving      EpicsSignalRO       ('motor_motor_is_moving')
      motor_done_move      EpicsSignalRO       ('motor_motor_done_move')
      high_limit_switch    EpicsSignal         ('motor_high_limit_switch')
      low_limit_switch     EpicsSignal         ('motor_low_limit_switch')
      direction_of_travel  EpicsSignal         ('motor_direction_of_travel')
      motor_stop           EpicsSignal         ('motor_motor_stop')
      home_forward         EpicsSignal         ('motor_home_forward')
      home_reverse         EpicsSignal         ('motor_home_reverse')

* The Area Detector plugins formerly always enabled themselves during staging.
  Now, this behavior is configurable using new methods, ``enable_on_stage()``
  and ``disable_on_stage()``. After unstaging, devices are put into their
  original state, whether enabled or disabled. Additionally, there are methods
  to control blocking callbacks, ``ensure_blocking()`` and
  ``ensure_nonblocking()``. We recommend using blocking callbacks always to
  ensure that file names do not get out of sync with acquisitions.
* A device's default read_attrs and configuration_attrs can be more succinctly
  specified via the class attributes ``_default_read_attrs`` and
  ``_default_configuration_attrs``.
* Some status objects add a new method named ``watch`` which support bluesky's
  new progress bar feature.
* The ``ScalerCH`` class has a new method, ``select_channels`` that
  coordinates several necessary steps of configuration in one convenient
  method.

Bug Fixes
*********

* The area detector plugin ports are validated after staging, giving the
  staging process the opportunity to put them into a valid state.

Maintenance
***********

* Ophyd's automated tests are now included inside the Python package in the
  package ``ophyd.tests``.
* Ophyd has many fewer dependencies. It no longer requires:

    * ``boltons``
    * ``doct``
    * ``ipython``
    * ``prettytable``
    * ``pyOlog`` (This was previous optional; now it is not used at all.)
* :attr:`ophyd.AreaDetector.filestore_mixin.fs_root` has been deprecated in
  favor of :attr:`ophyd.AreaDetector.filestore_mixin.reg_root`.

0.4.0
=====

Enhancements
************

* Allow ``set_and_wait`` to have a timeout.
* Allow a plugin to have no port name.
* Ensure trailing slashes are included in file plugin filepaths to avoid common
  user mistake.

API Changes
***********

* The bluesky interface now expects the ``stop`` method to accept an optional
  ``success`` argument.

0.3.1
=====

Enhancements
************

* Check alarm status of EpicsMotor to decide success/failure
* Allow ``stage_sigs`` to be attribute *names* to enable lazy-loading.
* Add ``target_initial_position`` parameter to ``PseudoSingle``.

Fixes
*****

* Add size-link to ROI plugin.
* Fix QuadEM port name uniqueness.
* Rename ``read`` attribute on MCA, which was shadowing ``read`` method, to
  ``force_read``. Add check to ``Device`` to avoid repeating this mistake in
  the future.

0.3.0
=====

API Changes
***********

* Area detector now checks that all plugins in the pipeline of
  anything that will be collected as part of ``read``.  The
  configuration of all of the plugins in the processing chain will now
  be included in descriptor document.   Tooling to inspect the asyn pipelines
  is now part of `ADBase` and `PluginBase`.

New Features
************

* Add ``pivot`` kwarg to `MonitorFlyierMixin` to optionally provide a
  single event as a time series rather than a time series of many
  events.
* Add `SignalPositionerMixin` to turn a `Signal` into a positioner.
* Add classes for PCO edge

Bug Fixes
*********

* Be more careful about thread safety around ``pyepics``
