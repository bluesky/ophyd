"""Mixin classes that customize the filestore integration of AreaDetector
FilePlugins.

To be used like so:

    from ophyd.areadetector.detectors import PerkinElmerDetector
    from ophyd.areadetector.plugins import HDF5Plugin
    from ophyd.areadetector.trigger_mixins import SingleTrigger
    from ophyd.areadetector.filestore_mixins import (
        FileStoreIterativeWrite)

    class MyPlugin(HDF5Plugin, FileStoreIterativeWrite):
        pass

    dest = '/tmp'  # in production, use a directory on your system -- not /tmp

    class MyDetector(PerkinElmerDetector, SingleTrigger):  # for example
        file_plugin = MyPlugin(suffix='HDF1:', write_path_template=dest)

    det = MyDetector(...)
"""

import logging
import uuid
import filestore.api as fs

from datetime import datetime
from collections import defaultdict
from itertools import count

from ..device import GenerateDatumInterface, BlueskyInterface
from ..utils import set_and_wait

logger = logging.getLogger(__name__)


def new_uid():
    "uuid4 as a string"
    return str(uuid.uuid4())


def new_short_uid():
    "uuid4, skipping the last stanza because of AD length restrictions."
    return '-'.join(new_uid().split('-')[:-1])


class FileStoreBase(BlueskyInterface, GenerateDatumInterface):
    """Base class for FileStore mixin classes

    The `write_path_template` and `read_path_template` are formatted using
    `datetime.strftime`, which accepts the standard tokens, such as
    %Y-%m-%d.
    """
    def __init__(self, *args, write_path_template=None,
                 read_path_template=None, **kwargs):
        # TODO Can we make these args? Depends on plugin details.
        if write_path_template is None:
            raise ValueError("write_path_template is required")
        self.write_path_template = write_path_template
        self._read_path_template = read_path_template
        super().__init__(*args, **kwargs)
        self._point_counter = None
        self._locked_key_list = False
        self._datum_uids = defaultdict(list)
        self.stage_sigs.update([(self.auto_increment, 'Yes'),
                                (self.array_counter, 0),
                                (self.auto_save, 'Yes'),
                                (self.num_capture, 0),
                                ])

    @property
    def read_path_template(self):
        "Returns write_path_template if read_path_template is not set"
        if self._read_path_template is None:
            return self.write_path_template
        else:
            return self._read_path_template

    @read_path_template.setter
    def read_path_template(self, val):
        self._read_path_template = val

    def stage(self):
        self._point_counter = count()
        self._locked_key_list = False
        self._datum_uids.clear()
        # Make a filename.
        self._filename = new_short_uid()
        formatter = datetime.now().strftime
        write_path = formatter(self.write_path_template)
        read_path = formatter(self.read_path_template)
        # Ensure we do not have an old file open.
        set_and_wait(self.capture, 0)
        # These must be set before parent is staged (specifically
        # before capture mode is turned on. They will not be reset
        # on 'unstage' anyway.
        set_and_wait(self.file_path, write_path)
        set_and_wait(self.file_name, self._filename)
        set_and_wait(self.file_number, 0)
        super().stage()

        # AD does this same templating in C, but we can't access it
        # so we do it redundantly here in Python.
        self._fn = self.file_template.get() % (read_path,
                                               self._filename,
                                               self.file_number.get() - 1)
                                               # file_number is *next* iteration
        self._fp = read_path
        if not self.file_path_exists.get():
            raise IOError("Path %s does not exist on IOC."
                          "" % self.file_path.get())

    def generate_datum(self, key, timestamp):
        "Generate a uid and cache it with its key for later insertion."
        if self._locked_key_list:
            if key not in self._datum_uids:
                raise RuntimeError("modifying after lock")
        uid = new_uid()
        reading = {'value': uid, 'timestamp': timestamp}
        # datum_uids looks like {'dark': [reading1, reading2], ...}
        self._datum_uids[key].append(reading)
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


class FileStoreHDF5(FileStoreBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage_sigs.update([(self.file_template, '%s%s_%6.6d.h5'),
                                (self.file_write_mode, 'Stream'),
                                (self.capture, 1)
                                ])

    def get_frames_per_point(self):
        return self.num_capture.get()

    def stage(self):
        super().stage()
        res_kwargs = {'frame_per_point': self.get_frames_per_point()}
        logger.debug("Inserting resource with filename %s", self._fn)
        self._resource = fs.insert_resource('AD_HDF5', self._fn, res_kwargs)


class FileStoreTIFF(FileStoreBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage_sigs.update([(self.file_template, '%s%s_%6.6d.tiff'),
                                (self.file_write_mode, 'Single'),
                                ])
        # 'Single' file_write_mode means one image : one file.
        # It does NOT mean that 'num_images' is ignored.

    def get_frames_per_point(self):
        return self.parent.cam.num_images.get()

    def stage(self):
        super().stage()
        res_kwargs = {'template': self.file_template.get(),
                      'filename': self.file_name.get(),
                      'frame_per_point': self.get_frames_per_point()}
        self._resource = fs.insert_resource('AD_TIFF', self._fp, res_kwargs)


class FileStoreTIFFSquashing(FileStoreBase):
    def __init__(self, *args, images_per_set_name='images_per_set',
                 number_of_sets_name="number_of_sets",
                 cam_name='cam', proc_name='proc1', **kwargs):
        super().__init__(*args, **kwargs)
        self._ips_name = images_per_set_name
        self._num_sets_name = number_of_sets_name
        self._cam_name = cam_name
        self._proc_name = proc_name
        cam = getattr(self.parent, self._cam_name)
        proc = getattr(self.parent, self._proc_name)
        self.stage_sigs.update([(self.file_template, '%s%s_%6.6d.tiff'),
                                (self.file_write_mode, 'Single'),
                                (proc.nd_array_port, cam.port_name.get()),
                                (proc.reset_filter, 1),
                                (proc.enable_filter, 1),
                                (proc.filter_type, 'Average'),
                                (proc.auto_reset_filter, 1),
                                (proc.filter_callbacks, 1),
                                (self.nd_array_port, proc.port_name.get())
                                ])
        # 'Single' file_write_mode means one image : one file.
        # It does NOT mean that 'num_images' is ignored.

    def get_frames_per_point(self):
        return getattr(self.parent, self._num_sets_name).get()

    def stage(self):
        cam = getattr(self.parent, self._cam_name)
        proc = getattr(self.parent, self._proc_name)
        images_per_set = getattr(self.parent, self._ips_name).get()
        num_sets = getattr(self.parent, self._num_sets_name).get()

        self.stage_sigs.update([(proc.num_filter, images_per_set),
                                (cam.num_images, images_per_set * num_sets)])
        super().stage()

        res_kwargs = {'template': self.file_template.get(),
                      'filename': self.file_name.get(),
                      'frame_per_point': self.get_frames_per_point()}
        self._resource = fs.insert_resource('AD_TIFF', self._fp, res_kwargs)


class FileStoreIterativeWrite(FileStoreBase):
    "Save records to filestore as they are generated."
    def generate_datum(self, key, timestamp):
        uid = super().generate_datum(key, timestamp)
        i = next(self._point_counter)
        fs.insert_datum(self._resource, uid, {'point_number': i})
        return uid


class FileStoreBulkWrite(FileStoreBase):
    "Cache records as they are created and save them all at the end."
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._datum_kwargs_map = dict()  # store kwargs for each uid

    def generate_datum(self, key, timestamp):
        "Stash kwargs for each datum, to be used below by unstage."
        uid = super().generate_datum(key, timestamp)
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


# ready-to-use combinations

class FileStoreHDF5IterativeWrite(FileStoreHDF5, FileStoreIterativeWrite):
    pass


class FileStoreHDF5BulkWrite(FileStoreHDF5, FileStoreBulkWrite):
    pass


class FileStoreTIFFIterativeWrite(FileStoreTIFF, FileStoreIterativeWrite):
    pass


class FileStoreTIFFBulkWrite(FileStoreTIFF, FileStoreBulkWrite):
    pass
