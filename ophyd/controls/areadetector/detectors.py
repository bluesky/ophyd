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
import uuid
import filestore.api as fs

from datetime import datetime
from collections import defaultdict, OrderedDict
from itertools import count
import os

from .base import (ADBase, ADComponent as C)
from . import cam
from ..ophydobj import DeviceStatus
from ..device import OphydDevice

logger = logging.getLogger(__name__)


__all__ = ['DetectorBase',
           'AreaDetector',
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


class TriggerBase(OphydDevice):
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


def new_uid():
    "Use uuid4, but skip the last stanza because of AD length restrictions."
    return '-'.join(str(uuid.uuid4()).split('-')[:-1])


class FileStoreBase(OphydDevice):
    "Base class for FileStore mixin classes"
    def __init__(self, *args, write_file_path=None, read_file_path=None,
                 **kwargs):
        # TODO Can we make these args? Depends on plugin details.
        if write_file_path is None:
            raise ValueError("write_file_path is required")
        self.write_file_path = write_file_path
        if read_file_path is None:
            self.read_file_path = write_file_path
        else:
            self.read_file_path = read_file_path
        super().__init__(*args, **kwargs)
        self._locked_key_list = False
        self._datum_uids = defaultdict(list)

    def stage(self):
        self._point_counter = count()
        self._locked_key_list = False
        self._datum_uids.clear()
        # Make a filename.
        self._filename = new_uid()
        date = datetime.now().date()
        # AD requires a trailing slash, hence the [''] here
        path = os.path.join(*(date.isoformat().split('-') + ['']))
        full_write_path = os.path.join(self.write_file_path, path)
        full_read_path = os.path.join(self.read_file_path, path)
        self.file_template.put('%s%s_%6.6d.h5')
        ssigs = OrderedDict((
            (self.enable, 1),
            (self.auto_increment, 1),
            (self.array_counter, 0),
            (self.file_number, 0),
            (self.auto_save, 1),
            (self.num_capture, 0),
            (self.file_write_mode, 2),
            (self.file_path, full_write_path),
            (self.file_name, self._filename),
            (self.capture, 1),
        ))
        self.stage_sigs.update(ssigs)
        super().stage()

        # fail early!
        assert self.file_template.get() == '%s%s_%6.6d.h5'
        assert self.file_path.get() == full_write_path
        assert self.file_name.get() == self._filename

        # AD does this same templating in C, but we can't access it
        # so we do it redundantly here in Python.
        fn = self.file_template.get() % (full_read_path, self._filename,
                                         self.file_number.get())

        if not self.file_path_exists.get():
            raise IOError("Path %s does not exist on IOC.", self.file_path)

        res_kwargs = {'frame_per_point': self.num_captured.get()}
        self._resource = fs.insert_resource('AD_HDF5', fn, res_kwargs)

    def generate_datum(self, key):
        "Generate a uid and cache it with its key for later insertion."
        if self._locked_key_list:
            if key not in self._datum_uids:
                raise RuntimeError("modifying after lock")
        nd = new_uid()
        self._datum_uids[key].append(nd)  # e.g., {'dark': [uid, uid], ...}
        return nd

    def describe(self):
        # One object has been 'described' once, no new keys can be added
        # during this stage/unstage cycle.
        self._locked_key_list = self._staged
        res = super().describe()
        for k in self._datum_uids:
            res[k] = self.parent.make_data_key()  # this is on DetectorBase
        return res

    def read(self):
        # One object has been 'read' once, no new keys can be added
        # during this stage/unstage cycle.
        self._locked_key_list = self._staged
        res = super().read()
        for k, v in self._datum_uids.items():
            res[k] = v[-1]
        return res

    def unstage(self):
        self._locked_key_list = False
        return super().unstage()


class FileStoreIterativeWrite(FileStoreBase):
    "Save records to filestore as they are generated."
    def generate_datum(self, key):
        uid = super().generate_datum(key)
        i = next(self._point_counter)
        fs.insert_datum(self._resource, uid, {'point_number': i})
        return uid


class FileStoreBulkEntry(FileStoreBase):
    "Cache records as they are created and save them all at the end."
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._datum_kwargs_map = dict()  # store kwargs for each uid

    def generate_datum(self, key):
        "Stash kwargs for each datum, to be used below by unstage."
        uid = super().generate_datum(key)
        i = next(self._point_counter)
        self._datum_kwargs_map[uid] = {'point_number': i}
        # (don't insert, obviously)
        return uid

    def unstage(self):
        "Insert all datums at the end."
        for uids in self._datum_uids.values():
            for uid in uids:
                kwargs = self._datum_kwargs_maps[uid]
                fs.insert_datum(self._resource, uid, kwargs)
        return super().unstage()


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


class DetectorBase(ADBase):
    """
    The base class for the hardware-specific classes that follow.

    Note that Plugin also inherits from ADBase.
    This adds some AD-specific methods that are not shared by the plugins.
    """
    def dispatch(self, key):
        """When a new acquisition is finished, this method is called with a
        key which is a label like 'light', 'dark', or 'gain8'.

        It in turn calls all of the file plugins and makes them insert a
        datum into FileStore.
        """
        from .plugins import FilePlugin  # terrible but necesary unless we move
        file_plugins = [a for _, a in self._signals.items() if
                        isinstance(a, FilePlugin)]
        for p in file_plugins:
            p.generate_datum(key)

    def make_data_keys(self):
        source = 'PV:{}'.format(self.prefix)
        shape = tuple(self.cam.array_size)  # casting for paranoia's sake
        return dict(shape=shape, source=source, dtype='array',
                    external='FILESTORE:')

    def generate_datum(self):
        # overridden by FileStore mixin classes, if any
        pass


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
