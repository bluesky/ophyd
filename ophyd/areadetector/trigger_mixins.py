"""Mixin classes that customize the triggering behavior of AreaDetector

To be used like so:

    from ophyd.areadetector.detectors import PerkinElmerDetector
    from ophyd.areadetector.trigger_mixins import SingleTrigger

    class MyDetector(PerkinElmerDetector, SingleTrigger):
        pass
"""

import time as ttime
import logging

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
    acquisitions with, for example, different gain settings.

    There is no specific logic implemented here, but it provides a pattern
    that can be easily modified. See in particular the method `_acquire` and
    the attribute `_num_acq_remaining`.

    Example
    -------
    >>> class MyDetector(SimDetector, MultiTrigger):
    ...     pass
    >>> det = MyDetector(acq_cycle={'name': ['gain1', 'gain2', 'gain8'],
    ...                             'image_gain': [1, 2, 8]})
    """
    # OphydObj subscriptions
    _SUB_ACQ_DONE = 'acq_done'
    _SUB_TRIGGER_DONE = 'trigger_done'

    def __init__(self, *args, acq_cycle=None, **kwargs):
        if acq_cycle is None:
            acq_cycle = {}
        self.acq_cycle = acq_cycle
        super().__init__(*args, **kwargs)

    def trigger(self):
        "Trigger one or more acquisitions."
        if not self._staged:
            raise RuntimeError("This detector is not ready to trigger."
                               "Call the stage() method before triggering.")

        self._num_acq_remaining = len(self._acq_settings)

        # GET READY...

        # Reset subscritpions.
        self._reset_sub(self._SUB_ACQ_DONE)
        self._reset_sub(self._SUB_TRIGGER_DONE)

        # When each acquisition finishes, it will immedately start the next
        # one until the desired number has been taken.
        self.subscribe(self._acquire,
                       event_type=self._SUB_ACQ_DONE, run=False)

        # When *all* the acquisitions are done, increment the trigger counter
        # and kick the status object.
        status = DeviceStatus(self)

        def trigger_finished(**kwargs):
            self._trigger_counter += 1
            status._finished()

        self.subscribe(trigger_finished,
                       event_type=self._SUB_TRIGGER_DONE, run=False)

        # GO!
        self._acquire()

        return status

    def _acquire(self, **kwargs):
        "Start the next acquisition or find that all acquisitions are done."
        logger.debug('_acquire called, %d remaining', self._num_acq_remaining)
        if self._num_acq_remaining:
            # Apply settings particular to each acquisition,
            # such as CCD gain or shutter position.
            for sig, values in self._acq_settings:
                val = values[-self._num_acq_remaining]
                sig.put(val, wait=True)
            self._acquisition_signal.put(1, wait=False)
        else:
            self._run_subs(sub_type=self._SUB_TRIGGER_DONE)

    def _acquire_changed(self, value=None, old_value=None, **kwargs):
        "This is called when the 'acquire' signal changes."
        if (old_value == 1) and (value == 0):
            # Negative-going edge means an acquisition just finished.
            self._num_acq_remaining -= 1
            self._run_subs(sub_type=self._SUB_ACQ_DONE)
