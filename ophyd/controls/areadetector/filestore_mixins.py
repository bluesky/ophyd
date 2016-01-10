"""Mixin classes that customize the filestore integration of AreaDetector
FilePlugins.

To be used like so:

    from ophyd.controls.areadetector.detectors import PerkinElmerDetector
    from ophyd.controls.areadetector.plugins import HDF5Plugin
    from ophyd.controls.areadetector.trigger_mixins import SingleTrigger
    from ophyd.controls.areadetector.filestore_mixins import (
        FileStoreIterativeWrite)

    class MyPlugin(HDF5Plugin, FileStoreIterativeWrite):
        pass

    dest = '/tmp'  # in production, use a directory on your system -- not /tmp

    class MyDetector(PerkinElmerDetector, SingleTrigger):  # for example
        file_plugin = MyPlugin(suffix='HDF1:', write_file_path=dest)

    det = MyDetector(...)
"""

from __future__ import print_function
import logging
import uuid
import filestore.api as fs

from datetime import datetime
from collections import defaultdict, OrderedDict
from itertools import count
import os

from ..ophydobj import DeviceStatus
from ..device import GenerateDatumInterface, BlueskyInterface

logger = logging.getLogger(__name__)


def new_uid():
    "uuid4 as a string"
    return str(uuid.uuid4())


def new_short_uid():
    "uuid4, skipping the last stanza because of AD length restrictions."
    return '-'.join(new_uid().split('-')[:-1])


class FileStoreBase(BlueskyInterface, GenerateDatumInterface):
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
        self._point_counter = None
        self._locked_key_list = False
        self._datum_uids = defaultdict(list)

    def stage(self):
        self._point_counter = count()
        self._locked_key_list = False
        self._datum_uids.clear()
        # Make a filename.
        self._filename = new_short_uid()
        date = datetime.now().date()
        # AD requires a trailing slash, hence the [''] here
        path = os.path.join(*(date.isoformat().split('-') + ['']))
        full_write_path = os.path.join(self.write_file_path, path)
        full_read_path = os.path.join(self.read_file_path, path)
        self.file_template.put('%s%s_%6.6d.h5')
        ssigs = [
            (self.enable, 1),
            (self.auto_increment, 1),
            (self.array_counter, 0),
            (self.file_number, 0),
            (self.auto_save, 1),
            (self.num_capture, 0),
            (self.file_write_mode, 1),  # 'capture' mode -- for AD 1.x
            (self.file_path, full_write_path),
            (self.file_name, self._filename),
            (self.capture, 1),
        ]
        self.stage_sigs.extend(ssigs)
        super().stage()

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
        uid = new_uid()
        self._datum_uids[key].append(uid)  # e.g., {'dark': [uid, uid], ...}
        return uid

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
        self._resource = None
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
