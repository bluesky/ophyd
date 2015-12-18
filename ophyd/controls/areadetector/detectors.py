# vi: ts=4 sw=4
'''
:mod:`ophyd.control.areadetector` - areaDetector
================================================

.. module:: ophyd.controls.areadetector.detectors
 :synopsis:  `areaDetector`_ detector abstractions

.. _areaDetector: http://cars.uchicago.edu/software/epics/areaDetector.html
'''

from __future__ import print_function
import logging
import time as ttime

from .base import (ADBase, ADComponent as C)
from . import cam
from ..ophydobj import DeviceStatus

logger = logging.getLogger(__name__)


__all__ = ['AreaDetector',
           'Andor3Detector',
           'AndorDetector',
           'BrukerDetector',
           'FirewireLinDetector',
           'FirewireWinDetector',
           'LightFieldDetector',
           'Mar345Detector',
           'MarCCDDetector',
           'PerkinElmerDetector',
           'PilatusDetector',
           'PixiradDetector',
           'PointGreyDetector',
           'ProsilicaDetector',
           'PSLDetector',
           'PvcamDetector',
           'RoperDetector',
           'SimDetector',
           'URLDetector',
           ]


class TriggerBase:
    "Base class for trigger mixin class"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # settings
        self._stage_sigs = {self.cam.acquire: 0,  # If acquiring, stop.
                            self.cam.image_mode: 1  # 'Multiple' mode
                           }
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
        return self._status

    def _acquire_changed(self, value=None, old_value=None, **kwargs):
        "This is called when the 'acquire' signal changes."
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
    >>> det = MyDetector(acq_cycle={'image_gain': [1, 2, 8]})
    """
    # OphydObj subscriptions
    _SUB_ACQ_DONE = 'acq_done'
    _SUB_TRIGGER_DONE = 'trigger_done'

    def __init__(self, *args, acq_cycle=None, **kwargs):
        if acq_cycle is None:
            acq_cycle = {}
        self.acq_cycle = acq_cycle

    def stage(self):
        """
        Setup the detector to be triggered.

        This must be called once before any calls to 'trigger'.
        Multiple calls (before unstaging) have no effect.
        """ 
        super().stage()
        self._trigger_counter = 0  # total acquisitions while staged

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

        # When each acquisition finishes, it will immedately start the next one
        # until the desired number has been taken.
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


class AreaDetector(DetectorBase):
    cam = C(cam.AreaDetectorCam, 'cam1:')


class SimDetector(DetectorBase):
    _html_docs = ['simDetectorDoc.html']
    cam = C(cam.SimDetectorCam, 'cam1:')


class AdscDetector(DetectorBase):
    _html_docs = ['adscDoc.html']
    cam = C(cam.AdscDetectorCam, 'cam1:')


class AndorDetector(DetectorBase):
    _html_docs = ['andorDoc.html']
    cam = C(cam.AndorDetectorCam, 'cam1:')


class Andor3Detector(DetectorBase):
    _html_docs = ['andor3Doc.html']
    cam = C(cam.Andor3DetectorCam, 'cam1:')


class BrukerDetector(DetectorBase):
    _html_docs = ['BrukerDoc.html']
    cam = C(cam.Andor3DetectorCam, 'cam1:')


class FirewireLinDetector(DetectorBase):
    _html_docs = ['FirewireWinDoc.html']
    cam = C(cam.FirewireLinDetectorCam, 'cam1:')


class FirewireWinDetector(DetectorBase):
    _html_docs = ['FirewireWinDoc.html']
    cam = C(cam.FirewireWinDetectorCam, 'cam1:')


class LightFieldDetector(DetectorBase):
    _html_docs = ['LightFieldDoc.html']
    cam = C(cam.LightFieldDetectorCam, 'cam1:')


class Mar345Detector(DetectorBase):
    _html_docs = ['Mar345Doc.html']
    cam = C(cam.Mar345DetectorCam, 'cam1:')


class MarCCDDetector(DetectorBase):
    _html_docs = ['MarCCDDoc.html']
    cam = C(cam.MarCCDDetectorCam, 'cam1:')


class PerkinElmerDetector(DetectorBase):
    _html_docs = ['PerkinElmerDoc.html']
    cam = C(cam.LightFieldDetectorCam, 'cam1:')


class PSLDetector(DetectorBase):
    _html_docs = ['PSLDoc.html']
    cam = C(cam.PSLDetectorCam, 'cam1:')


class PilatusDetector(DetectorBase):
    _html_docs = ['pilatusDoc.html']
    cam = C(cam.PilatusDetectorCam, 'cam1:')


class PixiradDetector(DetectorBase):
    _html_docs = ['PixiradDoc.html']
    cam = C(cam.PixiradDetectorCam, 'cam1:')


class PointGreyDetector(DetectorBase):
    _html_docs = ['PointGreyDoc.html']
    cam = C(cam.PointGreyDetectorCam, 'cam1:')


class ProsilicaDetector(DetectorBase):
    _html_docs = ['prosilicaDoc.html']
    cam = C(cam.ProsilicaDetectorCam, 'cam1:')


class PvcamDetector(DetectorBase):
    _html_docs = ['pvcamDoc.html']
    cam = C(cam.PvcamDetectorCam, 'cam1:')


class RoperDetector(DetectorBase):
    _html_docs = ['RoperDoc.html']
    cam = C(cam.RoperDetectorCam, 'cam1:')


class URLDetector(DetectorBase):
    _html_docs = ['URLDoc.html']
    cam = C(cam.URLDetectorCam, 'cam1:')
