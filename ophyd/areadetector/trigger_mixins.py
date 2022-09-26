"""Mixin classes that customize the triggering behavior of AreaDetector

To be used like so ::

    from ophyd.areadetector.detectors import PerkinElmerDetector
    from ophyd.areadetector.trigger_mixins import SingleTrigger

    class MyDetector(PerkinElmerDetector, SingleTrigger):
        pass
"""

import itertools
import logging
import time as ttime

from ..device import BlueskyInterface, Staged
from ..status import DeviceStatus

logger = logging.getLogger(__name__)


class ADTriggerStatus(DeviceStatus):
    """
    A Status for AreaDetector triggers

    A special status object that notifies watches (progress bars)
    based on comparing device.cam.array_counter to  device.cam.num_images.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_ts = ttime.time()

        # Notify watchers (things like progress bars) of new values
        # at the device's natural update rate.
        if not self.done:
            self.device.cam.array_counter.subscribe(self._notify_watchers)
            # some state needed only by self._notify_watchers
            self._name = self.device.name
            self._initial_count = self.device.cam.array_counter.get()
            self._target_count = self.device.cam.num_images.get()

    def watch(self, func):
        self._watchers.append(func)

    def _notify_watchers(self, value, *args, **kwargs):
        # *args and **kwargs catch extra inputs from pyepics, not needed here
        if self.done:
            self.device.cam.array_counter.clear_sub(self._notify_watchers)
        if not self._watchers:
            return
        # Always start progress bar at 0 regardless of starting value of
        # array_counter.
        current = value - self._initial_count
        target = self._target_count
        initial = 0
        time_elapsed = ttime.time() - self.start_ts
        try:
            fraction = (current - initial) / (target - initial)
        except ZeroDivisionError:
            fraction = 1
        except Exception:
            fraction = None
            time_remaining = None
        else:
            time_remaining = time_elapsed / fraction
        for watcher in self._watchers:
            watcher(
                name=self._name,
                current=current,
                initial=initial,
                target=target,
                unit="images",
                precision=0,
                fraction=fraction,
                time_elapsed=time_elapsed,
                time_remaining=time_remaining,
            )


class TriggerBase(BlueskyInterface):
    """Base class for trigger mixin classes

    Subclasses must define a method with this signature:

    ``acquire_changed(self, value=None, old_value=None, **kwargs)``
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # settings
        # careful here: quadEM devices have areadetector components but,
        # they have no 'cam' plugin. See QuadEM initializer.
        if hasattr(self, "cam"):
            self.stage_sigs.update(
                [
                    ("cam.acquire", 0),  # If acquiring, stop
                    ("cam.image_mode", 1),  # 'Multiple' mode
                ]
            )
            self._acquisition_signal = self.cam.acquire

        self._status = None


class SingleTrigger(TriggerBase):
    """
    This trigger mixin class takes one acquisition per trigger.

    Examples
    --------

    >>> class SimDetector(SingleTrigger):
    ...     pass
    >>> det = SimDetector('..pv..')
    # optionally, customize name of image
    >>> det = SimDetector('..pv..', image_name='fast_detector_image')
    """

    _status_type = ADTriggerStatus

    def __init__(self, *args, image_name=None, **kwargs):
        super().__init__(*args, **kwargs)
        if image_name is None:
            image_name = "_".join([self.name, "image"])
        self._image_name = image_name

    def stage(self):
        self._acquisition_signal.subscribe(self._acquire_changed)
        super().stage()

    def unstage(self):
        super().unstage()
        self._acquisition_signal.clear_sub(self._acquire_changed)

    def trigger(self):
        "Trigger one acquisition."
        if self._staged != Staged.yes:
            raise RuntimeError(
                "This detector is not ready to trigger."
                "Call the stage() method before triggering."
            )

        self._status = self._status_type(self)
        self._acquisition_signal.put(1, wait=False)
        self.generate_datum(self._image_name, ttime.time(), {})
        return self._status

    def _acquire_changed(self, value=None, old_value=None, **kwargs):
        "This is called when the 'acquire' signal changes."
        if self._status is None:
            return
        if (old_value == 1) and (value == 0):
            # Negative-going edge means an acquisition just finished.
            self._status.set_finished()
            self._status = None


class MultiTrigger(TriggerBase):
    """This trigger mixin class can take multiple acquisitions per trigger.

    This can be used to give more control to the detector. One call to
    'trigger' can be interpreted by the detector as a call to take several
    acquisitions with, for example, different gain settings or shutter
    positions.

    The are two levels of nesting here:

     - cycling through different actions on successive calls to ``trigger``
     - within each trigger, executing a list of acquisitions with different
       settings

    See the example below, which takes and 3 and 1 acquisitions in
    alternation.

    Examples
    --------

    >>> class MyDetector(SimDetector, MultiTrigger):
    ...     pass
    # EXAMPLE:
    # 1. On the first trigger, close the shutter and acquire three images
    # with different gain settings on the detector. Then open the shutter
    # and take a light frame.
    # 2. On the next trigger, just take a light frame.
    # Repeat.
    #
    # Each element of this list specifies one acquisition. It gives a
    # a label for each kind of image that will be taken and a dictionary
    # mapping signals to values that must be set for that acquisition.
    >>> dark_and_light = [('gain1', {'shutter': 'close', 'image_gain': 1}),
    ...                   ('gain2', {'image_gain': 2}),
    ...                   ('gain8', {'image_gain': 8}),
    ...                   ('light', {'shutter': 'open'})],
    # This list only has one element; it will only take one acquisition.
    >>> light_only = [('light', {'shutter': 'open'}]]
    # Finally, put the lists together. The detector will cycle through
    # this list as it is triggered.
    >>> trigger_cycle = [dark_and_light, light_only]
    >>> det = MyDetector(trigger_cycle=trigger_cycle)
    # Note: for simplicity, the settings were specified as dictionaries. If
    # you need to control the order that they are processed, use
    # OrderedDict instead.
    """

    # OphydObj subscriptions
    _SUB_ACQ_DONE = "acq_done"

    def __init__(self, *args, trigger_cycle=None, **kwargs):
        if trigger_cycle is None:
            raise ValueError("must provide trigger_cycle -- see docstring")
        self.trigger_cycle = trigger_cycle
        super().__init__(*args, **kwargs)

    def stage(self):
        self._acquisition_signal.subscribe(self._acquire_changed)
        super().stage()

    def unstage(self):
        super().unstage()
        self._acquisition_signal.clear_sub(self._acquire_changed)

    @property
    def trigger_cycle(self):
        return self._trigger_cycle

    @trigger_cycle.setter
    def trigger_cycle(self, val):
        self._trigger_cycle = itertools.cycle(val)

    def trigger(self):
        "Trigger one or more acquisitions."
        if self._staged != Staged.yes:
            raise RuntimeError(
                "This detector is not ready to trigger."
                "Call the stage() method before triggering."
            )

        # For each trigger, we have a list of one of more acquisitions to
        # take. These are names (e.g., 'light' or 'dark') paired with
        # an ordered dict of signals and values to set.
        acq_list = next(self.trigger_cycle)
        self._acq_iter = iter(acq_list)

        # GET READY...

        # Reset subscritpions.
        self._reset_sub(self._SUB_ACQ_DONE)

        # When each acquisition finishes, it will immedately start the next
        # one until the desired number has been taken.
        self.subscribe(self._acquire, event_type=self._SUB_ACQ_DONE, run=False)

        # When *all* the acquisitions are done, increment the trigger counter
        # and kick the status object.
        self._status = DeviceStatus(self)

        # GO!
        self._acquire()
        return self._status

    def _acquire(self, **kwargs):
        "Start the next acquisition or find that all acquisitions are done."
        try:
            key, signals_settings = next(self._acq_iter)
        except StopIteration:
            logger.debug("Trigger cycle is complete.")
            self._status.set_finished()
            return
        logger.debug("Configuring signals for acquisition labeled %r", key)
        for sig, val in signals_settings.items():
            sig.set(val).wait()
        self.generate_datum(key, ttime.time(), {})
        self._acquisition_signal.put(1, wait=False)

    def _acquire_changed(self, value=None, old_value=None, **kwargs):
        "This is called when the 'acquire' signal changes."
        logger.debug(
            "_acquire_chaged has been called: old_value %r, value %r", old_value, value
        )
        if self._status is None:
            return
        if (old_value == 1) and (value == 0):
            # Negative-going edge means an acquisition just finished.
            self._run_subs(sub_type=self._SUB_ACQ_DONE)
