from __future__ import print_function
from .detector import SignalDetector
from .signal import EpicsSignal
from epics import caput
from collections import deque
import time
from datetime import datetime
import os
import filestore.api as fs
import uuid


class AreaDetector(SignalDetector):
    def __init__(self, basename, use_stats=True,
                 *args, **kwargs):
        super(AreaDetector, self).__init__(*args, **kwargs)
        self._basename = basename
        self._use_stats = use_stats

        self.add_signal(self._ad_signal('cam1:Acquire', '_acquire'),
                        recordable=False)
        self.add_signal(self._ad_signal('cam1:ImageMode', '_image_mode'),
                        recordable=False)
        self.add_signal(self._ad_signal('cam1:AcquireTime', '_acquire_time'),
                        add_property=True)
        self.add_signal(self._ad_signal('cam1:NumImages', '_num_images'),
                        add_property=True)

        if self._use_stats:
            # Add Stats Signals
            for n in range(1, 6):
                self.add_signal(self._ad_signal('Stats{}:Total'.format(n),
                                                '_stats_total{}'.format(n),
                                                rw=False),
                                add_property=True)

        self.add_acquire_signal(self._acquire)

    def _ad_signal(self, suffix, alias, plugin='', **kwargs):
        """Return a signal made from areaDetector database"""
        basename = self._basename + plugin + suffix
        return EpicsSignal('{}_RBV'.format(basename),
                           write_pv=basename,
                           name='{}{}'.format(self.name, alias),
                           alias=alias, **kwargs)

    def __repr__(self):
        repr = ['basename={0._basename!r}'.format(self),
                'use_stats={0._use_stats!r}'.format(self)]

        return self._get_repr(repr)

    def configure(self, **kwargs):
        """Configure areaDetctor detector"""

        # Stop Acquisition
        self._old_acquire = self._acquire.get()
        self._acquire.put(0, wait=True)

        # Set the image mode to multiple
        self._old_image_mode = self._image_mode.get()

    def deconfigure(self, **kwargs):
        """DeConfigure areaDetector detector"""
        self._image_mode.put(self._old_image_mode, wait=True)
        self._acquire.put(self._old_acquire, wait=False)

    def read(self, *args, **kwargs):
        """Read the areadetector waiting for the stats plugins"""

        # if self._use_stats:
        #    # Super Hacky to wait for stats plugins to update
        #    while not all([(self._acquire.timestamp -
        #                   getattr(self, '_stats_total{}'.format(n)).timestamp)
        #                  < 0 for n in range(1, 6)]):
        #        time.sleep(0.01)

        return super(AreaDetector, self).read(*args, **kwargs)


class AreaDetectorFileStore(AreaDetector):
    def __init__(self, *args, **kwargs):
        self.store_file_path = kwargs.pop('file_path')
        self.ioc_file_path = kwargs.pop('ioc_file_path', None)
        self._file_template = kwargs.pop('file_template', '%s%s_%3.3d.h5')

        super(AreaDetectorFileStore, self).__init__(*args, **kwargs)

        self._uid_cache = deque()

        # Create the signals for the fileplugin

        self.add_signal(self._ad_signal('FilePath', '_file_path',
                                        self._file_plugin,
                                        string=True),
                        recordable=False)
        self.add_signal(self._ad_signal('FileName', '_file_name',
                                        self._file_plugin,
                                        string=True),
                        recordable=False)
        self.add_signal(self._ad_signal('FileTemplate', '_file_template',
                                        self._file_plugin,
                                        string=True),
                        recordable=False)
        self.add_signal(self._ad_signal('Capture', '_capture',
                                        self._file_plugin),
                        recordable=False)
        self.add_signal(self._ad_signal('NumCaptured', '_num_captured',
                                        self._file_plugin),
                        recordable=False)
        self.add_signal(self._ad_signal('FilePathExists', '_filepath_exists',
                                        self._file_plugin),
                        recordable=False)

    def _write_plugin(self, name, value, wait=True, as_string=False,
                      verify=True):
        caput('{}{}{}'.format(self._basename, self._file_plugin, name),
              value, wait=wait)

    def _make_filename(self, seq=0):
        uid = str(uuid.uuid4())
        self._filename = uid

        # The tree is the year / month / day
        date = datetime.now().date()
        tree = (str(date.year), str(date.month), str(date.day), '')

        path = os.path.join(self.store_file_path, *tree)
        self._store_file_path = path
        self._store_filename = self._file_template.value % (path,
                                                            self._filename, seq)

        if self.ioc_file_path:
            path = os.path.join(self.ioc_file_path, *tree)
            self._ioc_file_path = path
            self._ioc_filename = self._file_template.value % (path,
                                                              self._filename,
                                                              seq)
        else:
            self._ioc_file_path = self._store_file_path
            self._ioc_filename = self._store_filename

    def configure(self, *args, **kwargs):
        super(AreaDetectorFileStore, self).configure(*args, **kwargs)
        self._uid_cache.clear()

        self._write_plugin('AutoIncrement', 1)
        self._write_plugin('FileNumber', 0)
        self._write_plugin('AutoSave', 1)

    @property
    def describe(self):
        desc = super(AreaDetectorFileStore, self).describe

        if self._num_images.value > 1:
            size = (self._num_images.value,
                    self._arraysize1.value,
                    self._arraysize0.value)
        else:
            size = (self._arraysize1.value,
                    self._arraysize0.value)

        desc.update({'{}_{}'.format(self.name, 'image'):
                     {'external': 'FILESTORE:',  # TODO: Need to fix
                      'source': 'PV:{}'.format(self._basename),
                      'shape': size, 'dtype': 'array'}})

        # Insert into here any additional parts for source
        return desc

    def read(self):
        val = super(AreaDetectorFileStore, self).read()
        uid = str(uuid.uuid4())
        val.update({'{}_{}'.format(self.name, 'image'):
                    {'value': uid,
                     'timestamp': self._acq_signal.timestamp}})
        self._uid_cache.append(uid)

        return val


class AreaDetectorFileStoreHDF5(AreaDetectorFileStore):
    def __init__(self, *args, **kwargs):
        self._file_plugin = 'HDF1:'

        super(AreaDetectorFileStoreHDF5, self).__init__(*args, **kwargs)

        # Create Signals for the shape

        for n in range(2):
            sig = self._ad_signal('{}ArraySize{}'
                                  .format(self._file_plugin, n),
                                  '_arraysize{}'.format(n))
            self.add_signal(sig, recordable=False)

    def configure(self, *args, **kwargs):

        # Wait here to make sure we are not still capturing data
        while self._capture.value == 1:
            print('[!!] Still capturing data .... waiting.')
            time.sleep(1)

        self._make_filename()
        self._filestore_res = fs.insert_resource('AD_HDF5',
                                                 self._store_filename,
                                                 {'frame_per_point':
                                                  self._num_images.value})

        super(AreaDetectorFileStoreHDF5, self).configure(*args, **kwargs)

        self._image_mode.put(1, wait=True)
        self._write_plugin('NumCapture', 0)
        self._write_plugin('FileWriteMode', 2)
        self._write_plugin('EnableCallbacks', 1)
        self._write_plugin('FileTemplate', '%s%s_%3.3d.h5', as_string=True)
        self._file_path.put(self._ioc_file_path, wait=True)
        self._file_name.put(self._filename, wait=True)

        if not self._filepath_exists.value:
            raise IOError("Path {} does not exits on IOC!! Please Check"
                          .format(self._file_path.value))

        self._capture.put(1, wait=False)

    def _captured_changed(self, value, *args, **kwargs):
        if value == self._total_images:
            self._num_captured.clear_sub(self._captured_changed)
            # Close the capture plugin (closes the file)
            self._capture.put(0, wait=True)

    def deconfigure(self, *args, **kwargs):
        self._total_images = self._num_images.value * len(self._uid_cache)
        self._num_captured.subscribe(self._captured_changed)

        for i, uid in enumerate(self._uid_cache):
            fs.insert_datum(self._filestore_res, uid, {'point_number': i})

        super(AreaDetectorFileStore, self).deconfigure(*args, **kwargs)


class AreaDetectorFileStoreDriver(AreaDetectorFileStore):
    def __init__(self, *args, **kwargs):
        self._file_plugin = 'cam1:'
        super(AreaDetectorFileStoreDriver, self).__init__(*args, **kwargs)

        sig = self._ad_signal('{}ArraySizeX'
                              .format(self._file_plugin),
                              '_arraysize0')
        self.add_signal(sig, recordable=False)

        sig = self._ad_signal('{}ArraySizeY'
                              .format(self._file_plugin),
                              '_arraysize1')
        self.add_signal(sig, recordable=False)

        self._filename_cache = deque()

    def acquire(self, *args, **kwargs):

        self._make_filename()
        self._file_path.put(self._ioc_file_path, wait=True)
        self._file_name.put(self._filename, wait=True)
        self._write_plugin('FileNumber', 0)
        self._filename_cache.append(self._store_filename)

        rtn = super(AreaDetectorFileStoreDriver, self).acquire(*args, **kwargs)
        print(rtn)
        return rtn

    def configure(self, *args, **kwargs):
        self._image_mode.put(0, wait=True)
        self._write_plugin('FileTemplate', '%s%s_%3.3d.spe', as_string=True)
        super(AreaDetectorFileStoreDriver, self).configure(*args, **kwargs)

    def deconfigure(self, *args, **kwargs):

        for uid, fname in zip(self._uid_cache, self._filename_cache):
            res = fs.insert_resource('AD_SPE', fname)
            fs.insert_datum(res, uid)

        super(AreaDetectorFileStore, self).deconfigure(*args, **kwargs)
