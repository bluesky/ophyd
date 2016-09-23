Release Notes
-------------

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
