"""Mixin classes that customize the filestore integration of AreaDetector
FilePlugins.

To be used like so ::

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

import os
import logging
import warnings
import uuid
from pathlib import PurePath

from datetime import datetime
from collections import defaultdict
from itertools import count

from ..device import GenerateDatumInterface, BlueskyInterface, Staged
from ..utils import set_and_wait

logger = logging.getLogger(__name__)


def new_uid():
    "uuid4 as a string"
    return str(uuid.uuid4())


def new_short_uid():
    "uuid4, skipping the last stanza because of AD length restrictions."
    return '-'.join(new_uid().split('-')[:-1])


def _ensure_trailing_slash(path):
    """
    'a/b/c' -> 'a/b/c/'

    EPICS adds the trailing slash itself if we do not, so in order for the
    setpoint filepath to match the readback filepath, we need to add the
    trailing slash ourselves.
    """
    return os.path.join(path, '')


class FileStoreBase(BlueskyInterface, GenerateDatumInterface):
    """Base class for FileStore mixin classes

    This class provides

      - python side path management (root, seperate write / read paths)
      - provides :meth:`generate_datum` to work with
        :meth:`~ophyd.areadetector.detectors.DetectorBase.dispatch`
      - cooperative stage / unstage methods
      - cooperative read / describe methods that inject datums

    Separate read and write paths are supported because the IOC that
    writes the files may not have the data storage mounted at the same
    place as the computers that are expected to access it later (for
    example, if the IOC is running on a windows machine and mounting a
    NFS share via samba).

    ``write_path_template`` must always be provided, only provide
    ``read_path_template`` if the writer and reader will not have the
    same mount point.

    The properties :attr:`read_path_template` and
    :attr:`write_path_template` do the following check against
    ``root``

      - if the only ``write_path_template`` is provided

        - Used to generate read and write paths (which are identical)
        - verify that the path starts with :attr:`root` or the path is
          a relative, prepend :attr:`root`

      - if ``read_path_template`` is also provided then the above
        checks are applied to it, but ``write_path_template`` is
        returned without any validation.

    This mixin assumes that it's peers provide an `enable` signal

    Parameters
    ----------
    write_path_template : str
        Template feed to :py:meth:`~datetime.datetime.strftime` to generate the
        path to set the IOC to write saved files to.

        See above for interactions with root and read_path_template

    root : str, optional
        The 'root' of the file path.  This is inserted into filestore and
        enables files to be renamed or re-mounted with only some pain.

        This represents the part of the full path that is not
        'semantic'.  For example in the path
        '/data/XF42ID/2248/05/01/', the first two parts,
        '/data/XF42ID/', would be part of the 'root', where as the
        final 3 parts, '2248/05/01' is the date the data was taken.
        If the files were to be renamed, it is likely that only the
        'root' will be changed (for example of the whole file tree is
        copied to / mounted on another system or external hard drive).

    read_path_template : str, optional
        The read path template, if different from the write path.   See the
        docstings for `write_path_template` and `root`.

    reg : Registry
        If None provided, try to import the top-level api from
        filestore.api This will be deprecated 17Q3.

        This object must provide::

           def register_resource(spec: str,
                                 root: str, rpath: str,
                                 rkwargs: dict,
                                 path_semantics: Optional[str]): -> str
               ...

           def register_datum(resource: str, datum_kwargs: dict): -> str
               ...


    Notes
    -----

    This class in cooperative and expected to particpate in multiple
    inheritance, all ``*args`` and extra ``**kwargs`` are passed up the
    MRO chain.

    This class may be collapsed with :class:`FileStorePluginBase`

    """
    def __init__(self, *args,
                 write_path_template,
                 root=os.path.sep,
                 read_path_template=None,
                 reg=None,
                 **kwargs):
        PH = object()
        fs = kwargs.pop('fs', PH)
        super().__init__(*args, **kwargs)

        if write_path_template is None:
            raise ValueError("write_path_template is required")
        self.reg_root = root
        self.write_path_template = write_path_template
        self.read_path_template = read_path_template

        self._point_counter = None
        self._locked_key_list = False
        self._datum_uids = defaultdict(list)
        if reg is None and fs is not PH:
            reg = fs
            warnings.warn("The device is provided with fs not reg"
                          .format(self),
                          stacklevel=2)

        self._reg = reg

    @property
    def reg_root(self):
        "The 'root' put into the Asset Registry"
        return self._root

    @reg_root.setter
    def reg_root(self, val):
        if val is None:
            val = os.path.sep
        self._root = PurePath(val)

    @property
    def fs_root(self):
        "DEPRECATED: The 'root' put into the Asset registry, use reg_root"
        warnings.warn("fs_root is deprecated, use reg_root instead",
                      stacklevel=2)
        return self.reg_root

    @fs_root.setter
    def fs_root(self, val):
        warnings.warn("fs_root is deprecated, use reg_root instead",
                      stacklevel=2)
        self.reg_root = val

    @property
    def read_path_template(self):
        "Returns write_path_template if read_path_template is not set"
        rootp = self.reg_root

        if self._read_path_template is None:
            ret = PurePath(self.write_path_template)
        else:
            ret = PurePath(self._read_path_template)

        if rootp not in ret.parents:
            if not ret.is_absolute():
                ret = rootp / ret
            else:
                raise ValueError(
                    ('root: {!r} in not consistent with '
                     'read_path_template: {!r}').format(rootp, ret))

        return _ensure_trailing_slash(str(ret))

    @read_path_template.setter
    def read_path_template(self, val):
        if val is not None:
            val = _ensure_trailing_slash(val)
        self._read_path_template = val

    @property
    def write_path_template(self):
        rootp = self.reg_root
        ret = PurePath(self._write_path_template)
        if self._read_path_template is None and rootp not in ret.parents:
            if not ret.is_absolute():
                ret = rootp / ret
            else:
                raise ValueError(
                    ('root: {!r} in not consistent with '
                     'read_path_template: {!r}').format(rootp, ret))

        return _ensure_trailing_slash(str(ret))

    @write_path_template.setter
    def write_path_template(self, val):
        self._write_path_template = _ensure_trailing_slash(val)

    def stage(self):
        self._point_counter = count()
        self._locked_key_list = False
        self._datum_uids.clear()
        super().stage()
        if self.enable.get() and self._reg is None:
            raise RuntimeError('The plugin {!r} is enabled, but '
                               'the Registry (self._reg) is `None`')

    def generate_datum(self, key, timestamp, datum_kwargs):
        "Generate a uid and cache it with its key for later insertion."
        datum_kwargs = datum_kwargs or {}
        if self._locked_key_list:
            if key not in self._datum_uids:
                raise RuntimeError("modifying after lock")
        uid = self._reg.register_datum(self._resource, datum_kwargs)
        reading = {'value': uid, 'timestamp': timestamp}
        # datum_uids looks like {'dark': [reading1, reading2], ...}
        self._datum_uids[key].append(reading)
        return uid

    def describe(self):
        # One object has been 'described' once, no new keys can be added
        # during this stage/unstage cycle.
        self._locked_key_list = (self._staged == Staged.yes)
        res = super().describe()
        for k in self._datum_uids:
            res[k] = self.parent.make_data_key()  # this is on DetectorBase
        return res

    def read(self):
        # One object has been 'read' once, no new keys can be added
        # during this stage/unstage cycle.
        self._locked_key_list = (self._staged == Staged.yes)
        res = super().read()
        for k, v in self._datum_uids.items():
            res[k] = v[-1]
        return res

    def unstage(self):
        self._locked_key_list = False
        self._resource = None
        return super().unstage()


class FileStorePluginBase(FileStoreBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage_sigs.update([('auto_increment', 'Yes'),
                                ('array_counter', 0),
                                ('auto_save', 'Yes'),
                                ('num_capture', 0),
                                ])
        self._fn = None

    def make_filename(self):
        '''Make a filename.

        This is a hook so that the read and write paths can either be modified
        or created on disk prior to configuring the areaDetector plugin.

        Returns
        -------
        filename : str
            The start of the filename
        read_path : str
            Path that ophyd can read from
        write_path : str
            Path that the IOC can write to
        '''
        filename = new_short_uid()
        formatter = datetime.now().strftime
        write_path = formatter(self.write_path_template)
        read_path = formatter(self.read_path_template)
        return filename, read_path, write_path

    def stage(self):
        # Make a filename.
        filename, read_path, write_path = self.make_filename()

        # Ensure we do not have an old file open.
        set_and_wait(self.capture, 0)
        # These must be set before parent is staged (specifically
        # before capture mode is turned on. They will not be reset
        # on 'unstage' anyway.
        set_and_wait(self.file_path, write_path)
        set_and_wait(self.file_name, filename)
        set_and_wait(self.file_number, 0)
        super().stage()

        # AD does this same templating in C, but we can't access it
        # so we do it redundantly here in Python.
        self._fn = self.file_template.get() % (read_path,
                                               filename,
                                               self.file_number.get() - 1)
                                               # file_number is *next* iteration
        self._fp = read_path
        if not self.file_path_exists.get():
            raise IOError("Path %s does not exist on IOC."
                          "" % self.file_path.get())


class FileStoreHDF5(FileStorePluginBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filestore_spec = 'AD_HDF5'  # spec name stored in resource doc
        self.stage_sigs.update([('file_template', '%s%s_%6.6d.h5'),
                                ('file_write_mode', 'Stream'),
                                ('capture', 1)
                                ])

    def get_frames_per_point(self):
        return self.num_capture.get()

    def stage(self):
        super().stage()
        res_kwargs = {'frame_per_point': self.get_frames_per_point()}
        logger.debug("Inserting resource with filename %s", self._fn)
        fn = PurePath(self._fn).relative_to(self.reg_root)
        self._resource = self._reg.register_resource(
            self.filestore_spec,
            str(self.reg_root), str(fn),
            res_kwargs)


class FileStoreTIFF(FileStorePluginBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filestore_spec = 'AD_TIFF'  # spec name stored in resource doc
        self.stage_sigs.update([('file_template', '%s%s_%6.6d.tiff'),
                                ('file_write_mode', 'Single'),
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
        fp = PurePath(self._fp).relative_to(self.reg_root)

        self._resource = self._reg.register_resource(
            self.filestore_spec,
            str(self.reg_root), str(fp),
            res_kwargs)


class FileStoreTIFFSquashing(FileStorePluginBase):
    '''Write out 'squashed' tiffs

    .. note::

       See :class:`FileStoreBase` for the rest of the required parametrs

    This mixin will also configure the ``cam`` and ``proc`` plugins
    on the parent.

    This is useful to work around the dynamic range of detectors
    and minimizing disk spaced used by synthetically increasing
    the exposure time of the saved images.

    Parameters
    ----------
    images_per_set_name, number_of_sets_name : str, optional
        The names of the signals on the parent to get the
        images_pre_set and number_of_sets from.

        The total number of frames extracted from the camera will be
        :math:`number\_of\_sets * images\_per\_set` and result in
        ``number_of_sets`` tiff files each of which is the average of
        ``images_per_set`` frames from the detector.

        Defaults to ``'images_per_set'`` and ``'number_of_sets'``
    cam_name : str, optional
        The name of the :class:`~ophyd.areadetector.cam.CamBase`
        instance on the parent.

        Defaults to ``'cam'``

    proc_name : str, optional
        The name of the
        :class:`~ophyd.areadetector.plugins.ProcessPlugin` instance on
        the parent.

        Defaults to ``'proc1'``

    Notes
    -----

    This class in cooperative and expected to particpate in multiple
    inheritance, all ``*args`` and extra ``**kwargs`` are passed up the
    MRO chain.

    '''

    def __init__(self, *args,
                 images_per_set_name='images_per_set',
                 number_of_sets_name="number_of_sets",
                 cam_name='cam', proc_name='proc1',
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.filestore_spec = 'AD_TIFF'  # spec name stored in resource doc
        self._ips_name = images_per_set_name
        self._num_sets_name = number_of_sets_name
        self._cam_name = cam_name
        self._proc_name = proc_name
        cam = getattr(self.parent, self._cam_name)
        proc = getattr(self.parent, self._proc_name)
        self.stage_sigs.update([('file_template', '%s%s_%6.6d.tiff'),
                                ('file_write_mode', 'Single'),
                                (proc.nd_array_port, cam.port_name.get()),
                                (proc.reset_filter, 1),
                                (proc.enable_filter, 1),
                                (proc.filter_type, 'Average'),
                                (proc.auto_reset_filter, 1),
                                (proc.filter_callbacks, 1),
                                ('nd_array_port', proc.port_name.get())
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
        fp = PurePath(self._fp).relative_to(self.reg_root)

        self._resource = self._reg.register_resource(
            self.filestore_spec,
            str(self.reg_root), str(fp),
            res_kwargs)


class FileStoreIterativeWrite(FileStoreBase):
    "Save records to filestore as they are generated."
    def generate_datum(self, key, timestamp, datum_kwargs):
        'Generate the datum and insert'
        datum_kwargs = datum_kwargs or {}
        i = next(self._point_counter)
        datum_kwargs.update({'point_number': i})
        return super().generate_datum(key, timestamp, datum_kwargs)


# ready-to-use combinations

class FileStoreHDF5IterativeWrite(FileStoreHDF5, FileStoreIterativeWrite):
    pass


class FileStoreTIFFIterativeWrite(FileStoreTIFF, FileStoreIterativeWrite):
    pass
