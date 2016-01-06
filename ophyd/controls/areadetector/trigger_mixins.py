"""Mixin classes that customize the triggering behavior of AreaDetector

To be used like so:

    from ophyd.controls.areadetector.detectors import PerkinElmerDetector
    from ophyd.controls.areadetector.trigger_mixins import SingleTrigger

    class MyDetector(PerkinElmerDetector, SingleTrigger):
        pass
"""

from __future__ import print_function
import logging

from ..ophydobj import DeviceStatus
from ..device import BlueskyInterface

logger = logging.getLogger(__name__)


class TriggerBase(BlueskyInterface):
    "Base class for trigger mixin classes"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # settings
        self.stage_sigs.update(((self.cam.acquire, 0),  # If acquiring, stop.
                                (self.cam.image_mode, 1))  # 'Multiple' mode
                                )
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

    def trigger(self):
        "Trigger one acquisition."
        if not self._staged:
            raise RuntimeError("This detector is not ready to trigger."
                               "Call the stage() method before triggering.")

        self._status = DeviceStatus(self)
        self._acquisition_signal.put(1, wait=False)
        self.dispatch('image')
        return self._status

    def _acquire_changed(self, value=None, old_value=None, **kwargs):
        "This is called when the 'acquire' signal changes."
        if (old_value == 1) and (value == 0):
            # Negative-going edge means an acquisition just finished.
            self._status._finished()
