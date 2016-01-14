"""Mixin classes that customize the triggering behavior of AreaDetector

To be used like so:

    from ophyd.areadetector.detectors import PerkinElmerDetector
    from ophyd.areadetector.trigger_mixins import SingleTrigger

    class MyDetector(PerkinElmerDetector, SingleTrigger):
        pass
"""

import time as ttime
import logging
import itertools

from ..ophydobj import DeviceStatus
from ..device import BlueskyInterface

logger = logging.getLogger(__name__)


class TriggerBase(BlueskyInterface):
    """Base class for trigger mixin classes

    Subclasses must define a method with this signature:

    `acquire_changed(self, value=None, old_value=None, **kwargs)`
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # settings
        self.stage_sigs.update([(self.cam.acquire, 0),  # If acquiring, stop.
                                (self.cam.image_mode, 1),  # 'Multiple' mode
                               ])
        self._status = None
        self._acquisition_signal = self.cam.acquire
        self._acquisition_signal.subscribe(self._acquire_changed)


class SingleTrigger(TriggerBase):
    """
    This trigger mixin class takes one acquisition per trigger.

    Example
    -------
    >>> class SimDetector(SingleTrigger):
    ...     pass
    """
    def __init__(*args, image_name=None, **kwargs):
        self._image_name = image_name
        super().__init__(*args, **kwargs)

    def trigger(self):
        "Trigger one acquisition."
        if not self._staged:
            raise RuntimeError("This detector is not ready to trigger."
                               "Call the stage() method before triggering.")

        self._status = DeviceStatus(self)
        self._acquisition_signal.put(1, wait=False)
        if self._image_name is None:
            key = '_'.join(self.name, 'image')
        self.dispatch(key, ttime.time())
        return self._status

    def _acquire_changed(self, value=None, old_value=None, **kwargs):
        "This is called when the 'acquire' signal changes."
        if self._status is None:
            return
        if (old_value == 1) and (value == 0):
            # Negative-going edge means an acquisition just finished.
            self._status._finished()


class MultiTrigger(TriggerBase):
    """This trigger mixin class can take multiple acquisitions per trigger.

    This can be used to give more control to the detector. One call to
    'trigger' can be interpreted by the detector as a call to take several
    acquisitions with, for example, different gain settings or shutter
    positions.

    The are two levels of nesting here:
    - cycling through different actions on successive calls to `trigger`
    - within each trigger, executing a list of acquisitions with different
      settings

    See the example below, which takes and 3 and 1 acquisitions in
    alternation.

    Example
    -------
    >>> class MyDetector(SimDetector, MultiTrigger):
    ...     pass
    # On the first trigger, close the shutter and acquire three images
    # with different gain settings on the detector. Then open the shutter
    # and take a light frame.
    # On the next trigger, just take a light frame.
    >>> trigger_cycle=[[('gain1', {'shutter': 'close', 'image_gain': 1}),
    ...                 ('gain2', {'image_gain': 2}),
    ...                 ('gain8', {'image_gain': 8}),
    ...                 ('light', {'shutter': 'open'})],
    ...                [('light', {'shutter': 'open'}]]
    >>> det = MyDetector(trigger_cycle=trigger_cycle)
    # Note: for simplicity, the settings are specified as dictionaries. If
    # you need to control the order that they are processed, use
    # OrderedDict instead.
    """
    # OphydObj subscriptions
    _SUB_ACQ_DONE = 'acq_done'

    def __init__(self, *args, trigger_cycle=None, **kwargs):
        if trigger_cycler is None:
            raise ValueError("must provide a trigger cycle -- see docstring")
        self.trigger_cycle = itertools.cycle(trigger_cycle)
        super().__init__(*args, **kwargs)

    def trigger(self):
        "Trigger one or more acquisitions."
        if not self._staged:
            raise RuntimeError("This detector is not ready to trigger."
                               "Call the stage() method before triggering.")

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
        self.subscribe(self._acquire,
                       event_type=self._SUB_ACQ_DONE, run=False)

        # When *all* the acquisitions are done, increment the trigger counter
        # and kick the status object.
        status = DeviceStatus(self)

        # GO!
        self._acquire()
        return status

    def _acquire(self, **kwargs):
        "Start the next acquisition or find that all acquisitions are done."
        try:
            key, signals_settings = next(self._acq_iter)
        except StopIteration:
            logger.debug("Trigger cycle is complete.")
            self._status._finished()
            return
        logger.debug('Configuring signals for acquisition labeled %s', key)
        for sig, val in signals_settings:
            set_and_wait(sig, val)
        self.dispatch(key, ttime.time())
        self._acquisition_signal.put(1, wait=False)

    def _acquire_changed(self, value=None, old_value=None, **kwargs):
        "This is called when the 'acquire' signal changes."
        if self._status is None:
            return
        if (old_value == 1) and (value == 0):
            # Negative-going edge means an acquisition just finished.
            self._run_subs(sub_type=self._SUB_ACQ_DONE)
