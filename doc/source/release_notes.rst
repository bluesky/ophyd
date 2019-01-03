=================
 Release History
=================

v1.3.1 (2019-01-03)
===================

Features
--------

* Add :class:`~ophyd.FakeEpicsSignalWithRBV`, which is to
  :class:`~ophyd.FakeEpicsSignal` as :class:`~ophyd.EpicsSignalWithRBV` is to
  :class:`~ophyd.EpicsSignal`.
* Add enum-spoofing to :class:`~ophyd.FakeEpicsSignal`.
* A default handler is added to the ``'ophyd'`` logger at import time. A new
  convenience function, :func:`~ophyd.set_handler`, addresses common cases
  such as directing the log output to a file.

Bug Fixes
---------

* Always interpret simulated motor positions as floats, even if set to an
  integer position.
* Accept numpy arrays in ``set_and_wait``.
* Log errors with ``set_and_wait`` at the ERROR level rather than the (often
  silenced) DEBUG level.
* Check limits on :class:`~ophyd.SoftPositioner`.
* Produce consistent Datum documents in the old and new asset registry code
  paths in :class:`~ophyd.sim.SynSignalWithRegistry`.
* Fix some missing imports in :mod:`ophyd.areadetector.plugins`.
* The verification that the image plugin has received an array of nonzero size
  was implemented in a way that it would never be tripped.
* Accept any tuple of the right length in :meth:`~ophyd.Device.put`.
* :class:`~ophyd.AttributeSignal` now runs subscriptions when it processes an
  update.
* Fix some bugs in :class:`~ophyd.FakeEpicsSignal`.

v1.3.0 (2018-09-05)
===================

Features
--------

* Teach Area Detector classes how to display the DAG of their pipelines
  via :func:`~ophyd.areadetector.base.ADBase.visualize_asyn_digraph`.


Bug Fixes
---------

* :class:`~ophyd.signal.Signal.describe` correctly reports the type
  and shape of the data.
* make :obj:`Device.component_names` an :class:`tuple` (instead of a
  :class:`list`) as it should not be mutable.
* Fix issue with grand-children not correctly reporting as being in
  ``read_attrs`` or ``configuration_attrs``.

v1.2.0 (2018-06-06)
===================

Features
--------

* On each Signal or Device, attach a Python logger attribute named ``log``
  with a logger name scoped by module name and the ophyd ``name`` of the
  parent Device.
* Signals and Devices now accept ``labels`` argument, a set of labels
  --- presumed but not (yet) forced to be strings --- which the user can use
  for grouping and displaying available hardware. The labels are accessible via
  a new attribute ``_ophyd_labels_``, so name to facilitate duck-typing across
  libraries. For example, the bluesky IPython "magics" use this to identify
  objects for the purpose of displaying them in labeled groups.
* Added ``tolerated_alarm`` attribute to ``EpicsMotors``, a hook to increase
  alarm tolerance for mis-configured motors.
* Ophyd is now fully tested to work against the experimental control layer,
  caproto, in addition to pyepics. The control layer can also be set to 'dummy'
  for testing without EPICS. This is configurable via the
  ``OPHYD_CONTROL_LAYER`` environment variable.
* Added a ``kind`` attribute to each Signal and Device, settable interactively
  or via an argument at initiation time, which controls whether its parent
  Device will include it in ``read()``, ``read_configuration()``, and/or
  ``hints.fields``. This behavior was previously controlled by ``read_attrs``,
  ``configuration_attrs``, ``_default_read_attrs``, and
  ``_default_configuration_attrs`` on parent Devices. Those can still be used
  for *setting* the desired state, but the source of truth is now stored
  locally on each child Signal/Device, and
  ``read_attrs``/``configuration_attrs`` has been re-implemented as a
  convenience API. Documentation is forthcoming; until then we refer to you the
  `narrative-style tests of this feature <https://github.com/NSLS-II/ophyd/blob/master/ophyd/tests/test_kind.py>`_. Also see three breaking changes, listed in a subsequent
  section of these release notes. The existing implementation contained buggy
  and surprising behavior, and addressing that made breaking *something*
  unavoidable.
* Added ``make_fake_device`` factory function that makes a Device out of
  ``FakeEpicsSignal`` based on a Device that has real signals.
* Add ``sum_all`` component to QuadEM.
* Add a ``set`` method to the ROI plugin.
* Validate that a Device or Signal's ``name`` is a string, and raise helpfully
  if it is not.

Bug Fixes
---------

* Allow ``DerivedSignal`` to accept a string name as its target component so
  that it can be used inside Device, where it must defer grabbing its target to
  initialization time.
* Signals that start with underscores are now not renamed by ``namedtuple``.
  This causes issues when the ``.get`` method tries to fill the ``DeviceTuple``.
* Add new ``ad_root`` ("area detector root") to remove the accidental
  assumption that ``ADBase`` is the root ancestor Device of all its subclasses.
* ``ad_group`` generates Components that are lazy by default.
* Catch various edge cases related to the data fed to progress bars from status
  objects.

Deprecations
------------

* This release simplifies the flow of information out of ophyd. Fortunately,
  this major change can be made smoothly. In this transitional release, both
  old and new modes of operation are supported. Old configurations should
  continue to work, unchanged. Nonetheless, users are encouraged to update
  their configurations promptly to take advantage of the better design. The
  old mode of operation will cease to be supported in a future release.

  **How to upgrade your configuration:** Simply remove the ``reg=...``
  parameter everywhere it occurs in area-detector-related configuration.

  **Background:** In the original design, bluesky's RunEngine collected *some*
  information (readings for Event and EventDescriptor documents) and dispatched
  it out to consumers, while ophyd itself pushed other information (Datum and
  Resource documents) directly into a database. There are two problems with
  this design.

  1. Consumers subscribed to bluesky only see partial information. For example,
     to access the filepaths to externally-stored data, they have to perform a
     separate database lookup. There are no guarantees about synchronization:
     the consumer may receive references to objects that do not exist in the
     database yet.
  2. Ophyd is responsible inserting information into a database, which means
     connection information needs to be associated with a Device. This seems
     misplaced.

  In the new design, ophyd merely *caches* Datum and Resource documents and
  leaves it up to bluesky's RunEngine to ask for them and dispatch them out to
  any consumers (such as that database that ophyd used to push to directly).
  Thus, all information flows through bluesky and to consumers in a guaranteed
  order. Ophyd does not need to know about database configuration.

  Ophyd's area detector "filestore" integration classes in
  ``ophyd.areadetector.filestore_mixins`` and ``ophyd.sim`` still *accept*
  a ``Registry`` via their optional ``reg`` parameter. If they receive one,
  they will assume that they are supposed to operate the old way: inserting
  documents directly into the ``Registry``. If the user is running bluesky
  v1.3.0, bluesky will collect these same documents and dispatch them out to
  consumers also.
* The module ``ophyd.control_layer`` has been deprecated in favor of a
  top-level ``cl`` object.

Breaking Changes
----------------

* The 'hints' feature was an experimental feature in previous releases of
  ophyd and is now being incorporated in a first-class way. To ensure
  internal consistency, the ``hints`` attribute of any ``Signal`` or ``Device``
  is no longer directly settable. Instead of

  .. code-block:: python

      camera.hints = {'fields': [camera.stats1.total.name,
                                 camera.stats2.total.name]}

  do

  .. code-block:: python

      from ophyd import Kind

      camera.stats1.total.kind = Kind.hinted
      camera.stats2.total.kind = Kind.hinted

  or, as a convenient shortcut

  .. code-block:: python

      camera.stats1.total.kind = 'hinted'
      camera.stats2.total.kind = 'hinted'
* The ``read_attrs`` / ``configuration_attrs`` lists will now contain all of
  the components touched when walking the Device tree. This also means that
  setting these lists may not always round trip: they may contain extra
  elements in addition to those explicitly set.
* When adding "grandchildren" via ``read_attrs`` / ``configuration_attrs``, we
  no longer allow generation skipping and forcibly set up the state of all of
  the devices along the way to be consistent. Inconsistency arguably should
  never have been possible in the first place.
* A Device's ``__repr__`` no longer includes ``read_attrs`` and
  ``configuration_attrs`` (because they are now so lengthy). This means that
  passing a Device's ``__repr__`` to ``eval()`` does not necessarily
  reconstruct a Device in exactly the same state.

v1.1.0 (2017-02-20)
===================

Features
--------

* Add a new ``run`` keyword, which defaults to ``True``, which can be used to
  keep :class:`.SubscriptionStatus` objects from running callbacks immediately.
* Add an :meth:`unsuscribe_all` method to OphydObj.
* Support timestamps and subscriptions in the simulated motor
  :class:`.SynAxis` and related classes.
* Extend :class:`.DynamicDeviceComponent` to accept optional
  ``default_read_attrs`` and ``default_configuration_attrs`` arguments, which
  it will assign as class attributes on the class it dynamically creates.
* Systematically add ``default_read_attrs=(...)`` to every DDC on every
  Area Detector plugin. Now, for example, adding ``'centroid'`` to the read
  attributes of a :class:`.StatsPlugin` instance also effectively adds
  ``'centroid_x'`` and ``'centroid_y'``, which is presumably the desired
  result.
* On :class:`.ScalerCH`, omit any channels whose name is ``''`` from
  the read attributes by default.
* Add new ``random_state`` keyword to relevant simulated devices so that their
  randomness can be made deterministic for testing purposes.
* Restore namespace-scraping utilities :func:`.instances_from_namespace` and
  :func:`.ducks_from_namespace` which had been moved in pyolog during previous
  refactor.

Bug Fixes
---------

* Fix race condition in :func:`.set_and_wait`.
* Fix a bug in aforementioned namespace-scraping utilities.
* Do not use deprecated API (``signal_names``, now called ``component_names``)
  internally.

v1.0.0 (2017-11-17)
===================

This tag marks an important release for ophyd, signifying the conclusion of
the early development phase. From this point on, we intend that this project
will be co-developed between multiple facilities. The 1.x series is planned to
be a long-term-support release.

Breaking Changes
----------------

* To access the human-friendly summary of a Device's layout, use
  ``device.summary()`` instead of ``print(device)``. The verbosity of the
  summary was overwhelming when it appeared in error messages and logs, so it
  was moved from ``Device.__str__`` this new method. Now ``Device.__str__``
  gives the same result as ``Device.__repr__``, as it did before v0.7.0.
* Add (empty) hints to `~ophyd.sim.SynSignalWithRegistry`.

Bug Fixes
---------

* Initiate :class:`~ophyd.sim.SynSignal` with a function that returns ``None``
  if no ``func`` parameter is provided.
* Make ophyd importable without pyepics and libca.

v0.8.0 (2017-11-01)
===================

Breaking Changes
----------------

* Make the ``name`` keyword to Device a required, keyword-only argument. This
  ensures that the names that appear in the read dictionary are always
  human-readable.
* When a ``PseudoPositioner`` is set with only a subset of its parameters
  specified, fill in the unspecified values with the current *target* position,
  not the current *actual* position.

Deprecations
------------

* The ``signal_names`` attribute of devices has been renamed
  ``component_names`` for clarity because it may include a mixture of Signals
  and Devices -- any Components. The old name now issues a warning when
  accessed, and it may be removed in a future release of ophyd.
* Status objects' new ``add_callback`` method and ``callbacks`` attribute
  should be preferred over the ``finished_cb`` property, which only supports
  one callback and now warns if set or accessed.

Features
--------

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
---------

* Avoid a race condition when timing out during a settle time.

Internal Changes
----------------

* Reduce set_and_wait log messages to DEBUG level.
* Refactor OphydObj callbacks to make the logic easier to follow. This change
  is fully backward-compatible.

v0.7.0 (2017-09-06)
===================

Breaking Changes
----------------

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

Features
--------

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
---------

* The area detector plugin ports are validated after staging, giving the
  staging process the opportunity to put them into a valid state.

Maintenance
-----------

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

v0.6.1 (2017-05-22)
===================

(TO DO)

v0.6.0 (2017-05-05)
===================

(TO DO)

v0.5.0 (2017-01-27)
===================

(TO DO)

v0.4.0 (2016-11-01)
===================

Enhancements
------------

* Allow ``set_and_wait`` to have a timeout.
* Allow a plugin to have no port name.
* Ensure trailing slashes are included in file plugin filepaths to avoid common
  user mistake.

Breaking Changes
----------------

* The bluesky interface now expects the ``stop`` method to accept an optional
  ``success`` argument.

v0.3.1 (2016-09-23)
===================

Enhancements
------------

* Check alarm status of EpicsMotor to decide success/failure
* Allow ``stage_sigs`` to be attribute *names* to enable lazy-loading.
* Add ``target_initial_position`` parameter to ``PseudoSingle``.

Fixes
-----

* Add size-link to ROI plugin.
* Fix QuadEM port name uniqueness.
* Rename ``read`` attribute on MCA, which was shadowing ``read`` method, to
  ``force_read``. Add check to ``Device`` to avoid repeating this mistake in
  the future.

v0.3.0 (2016-07-25)
===================

Breaking Changes
----------------

* Area detector now checks that all plugins in the pipeline of
  anything that will be collected as part of ``read``.  The
  configuration of all of the plugins in the processing chain will now
  be included in descriptor document.   Tooling to inspect the asyn pipelines
  is now part of `ADBase` and `PluginBase`.

New Features
------------

* Add ``pivot`` kwarg to `MonitorFlyierMixin` to optionally provide a
  single event as a time series rather than a time series of many
  events.
* Add `SignalPositionerMixin` to turn a `Signal` into a positioner.
* Add classes for PCO edge

Bug Fixes
---------

* Be more careful about thread safety around ``pyepics``

v0.2.3 (2016-05-05)
===================

(TO DO)

v0.2.2 (2016-03-14)
===================

(TO DO)

v0.2.1 (2016-02-23)
===================

(TO DO)

v0.2.0 (2016-02-10)
===================

(TO DO)
