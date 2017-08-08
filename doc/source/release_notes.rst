Release Notes
-------------

0.7.0
=====

API Changes
***********

* The module :mod:`ophyd.commands`, a grab bag of convenient tools, has been
  entirely removed. The functionality is available in other ways:

    * The functions :func:`mov` and :func:`movr` ("move" and "move relative")
      have been replaced by bluesky plans in bluesky v0.10.0:

      .. code-block:: python

         from bluesky.plans import mov, movr

         # Move eta to 3 and set temperature to 273, in parallel.
         RE(mov(eta, 3, temp, 273)))

         # Shift eta +1 and temperature to -5, in parallel, relative
         # to initial values.
         RE(movr(eta, 1, temp, -5)))

      And by (experimental) IPython magics, also available from bluesky,
      which accomplish the same thing.

      .. code-block:: python

         %mov eta 3 temp 273
         %movr eta 1 temp -5

    * The function :func:`wh_pos` for surveying current positioners has
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
