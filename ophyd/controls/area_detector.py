from __future__ import print_function
from .detector import SignalDetector, DetectorStatus
from .signal import EpicsSignal, Signal
from epics import caput
from collections import deque
import time
from datetime import datetime
import os
import filestore.api as fs
import uuid


class AreaDetector(SignalDetector):
    SUB_ACQ_DONE_ONE = 'acq_done_1'
    SUB_ACQ_DONE_TWO = 'acq_done_2'

    def __init__(self, basename, stats=range(1, 6),
                 shutter=None, shutter_rb=None, shutter_val=(0, 1),
                 *args, **kwargs):
        """Initialize the AreaDetector class

        Parameters
        ----------
        basename : str
            The EPICS PV basename of the areaDetector
        stats : list
            If true, provide data from total counts from the stats plugins
            from the list. For example for stats 1..5 use range(1,6)
        shutter : Signal or str
            Either a ophyd signal or a string to form an EpicsSignal from.
            This signal is used to inhibit the shutter for forming dark frames.
        shutter_rb : str
            If shutter is an str, then use this as the readback PV
        shutter_val : tuple
            These are the values to send to the signal shutter to inhibit or
            enable the shutter. (0, 1) will send 0 to enable the shutter and
            1 to inhibit tthe shutter.
        """

        super(AreaDetector, self).__init__(*args, **kwargs)
        self._basename = basename
        if stats:
            self._use_stats = True
        else:
            self._use_stats = False

        # Acquisition mode (Multiple Images)
        self._image_acq_mode = 1

        # Default to not taking darkfield images
        self._darkfield_int = 0

        # Setup signals on camera
        self.add_signal(self._ad_signal('cam1:Acquire', '_acquire',
                        recordable=False))
        self.add_signal(self._ad_signal('cam1:ImageMode', '_image_mode',
                        recordable=False))
        self.add_signal(self._ad_signal('cam1:AcquireTime', '_acquire_time'),
                        add_property=True)
        self.add_signal(self._ad_signal('cam1:AcquirePeriod',
                                        '_acquire_period'),
                        add_property=True)
        self.add_signal(self._ad_signal('cam1:NumImages', '_num_images'),
                        add_property=True)
        self.add_signal(self._ad_signal('cam1:ArrayCounter', '_array_counter',
                        recordable=False))

        if self._use_stats:
            # Add Stats Signals
            for n in stats:
                self.add_signal(self._ad_signal('Stats{}:Total'.format(n),
                                                '_stats_total{}'.format(n),
                                                rw=False),
                                add_property=True)

        if shutter:
            if isinstance(shutter, Signal):
                self._add_signal(shutter, prop_name='_shutter')
            else:
                self.add_signal(EpicsSignal(write_pv=shutter,
                                            read_pv=shutter_rb,
                                            name='{}_shutter'.format(self.name),
                                            rw=True, alias='_shutter',
                                            recordable=False))
            self._shutter_value = shutter_val
        else:
            self._shutter = None
            self._shutter_value = None

        # Run a subscription on the acquire signal

        self.add_acquire_signal(self._acquire)
        self._acquire.subscribe(self._acquire_changed)

        # Acq Count is used to signal if this is the first or
        # second acquire per acquisition

        self._acq_count = 0

    def _acquire_changed(self, value=None, old_value=None, **kwargs):
        if (old_value == 1) and (value == 0):
            # Negative going edge is done acquiring
            if self._acq_count == 1:
                self._run_subs(sub_type=self.SUB_ACQ_DONE_ONE)
                self._reset_sub(self.SUB_ACQ_DONE_ONE)
            elif self._acq_count == 2:
                self._run_subs(sub_type=self.SUB_ACQ_DONE_TWO)
                self._reset_sub(self.SUB_ACQ_DONE_TWO)

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
        self._old_acquire = self._acquire.value
        self._acquire.put(0, wait=True)
        self._array_counter.value = 0

        # Set the image mode to multiple
        self._old_image_mode = self._image_mode.value
        self._image_mode.value = self._image_acq_mode
        self._acquire_number = 0

    def deconfigure(self, **kwargs):
        """DeConfigure areaDetector detector"""
        self._image_mode.put(self._old_image_mode, wait=True)
        self._acquire.value = self._old_acquire

    @property
    def darkfield_interval(self):
        """Return the interval to take darkfield images

        This property is the interval on which to take darkfield images
        If this set to 2 (for example) then the darkfield image will be taken
        ever second image
        """
        return self._darkfield_int

    @darkfield_interval.setter
    def darkfield_interval(self, value):
        """Set the interval to take darkfield images

        This property is the interval on which to take darkfield images
        If this set to 2 (for example) then the darkfield image will be taken
        ever second image

        Parameters
        ----------
        interval : int

        """
        self._darkfield_int = value

    def _set_shutter(self, value):
        if self._shutter:
            self._shutter.put(self._shutter_value[value], wait=True)

    def acquire(self, **kwargs):
        """Start acquisition including dark frames"""

        # Here start a chain which allows for a darkfield
        # image to be taken after a lightfield
        # First lets set if we need to take one

        status = DetectorStatus(self)

        if self.darkfield_interval:
            val = (self._acquire_number % self.darkfield_interval)
            self._take_darkfield = (val == 0)
        else:
            self._take_darkfield = False

        def finished(**kwargs):
            self._acquire_number += 1
            status._finished()

        def acquire_darkfield(**kwargs):
            self._set_shutter(1)
            self._acq_count = 2
            self._acq_signal.put(1, wait=False)

        # Acquire lighfield image

        self._set_shutter(0)
        self._acq_count = 1
        self._acq_signal.put(1, wait=False)
        if self._take_darkfield:

            self.subscribe(acquire_darkfield,
                           event_type=self.SUB_ACQ_DONE_ONE, run=False)
            self.subscribe(finished,
                           event_type=self.SUB_ACQ_DONE_TWO, run=False)
        else:

            self.subscribe(finished,
                           event_type=self.SUB_ACQ_DONE_ONE, run=False)

        return status


class AreaDetectorFileStore(AreaDetector):
    def __init__(self, *args, **kwargs):
        self.store_file_path = os.path.join(kwargs.pop('file_path'), '')
        self.ioc_file_path = kwargs.pop('ioc_file_path', None)
        if self.ioc_file_path:
            self.ioc_file_path = os.path.join(self.ioc_file_path, '')
        self._uid_cache = deque()
        self._uid_cache_darkfield = deque()

        super(AreaDetectorFileStore, self).__init__(*args, **kwargs)

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
        self._uid_cache_darkfield.clear()

    def deconfigure(self, *args, **kwargs):

        i = 0
        m = 0

        # It is late and i am tired and this should be done better ...

        for n, uid in enumerate(self._uid_cache):
            fs.insert_datum(self._filestore_res, str(uid), {'point_number': i})

            # Now do dark frames
            if self.darkfield_interval:
                if not (n % self.darkfield_interval):
                    i += 1
                    uid_dark = str(self._uid_cache_darkfield[m])
                    m += 1
                    fs.insert_datum(self._filestore_res, uid_dark,
                                    {'point_number': i})

            i += 1

        super(AreaDetectorFileStore, self).deconfigure(*args, **kwargs)

    def describe(self):
        desc = super(AreaDetectorFileStore, self).describe()

        if self._num_images.value > 1:
            size = (self._num_images.value,
                    self._arraysize1.value,
                    self._arraysize0.value)
        else:
            size = (self._arraysize1.value,
                    self._arraysize0.value)

        desc.update({'{}_{}'.format(self.name, 'image_lightfield'):
                     {'external': 'FILESTORE:',  # TODO: Need to fix
                      'source': 'PV:{}'.format(self._basename),
                      'shape': size, 'dtype': 'array'}})

        if self._darkfield_int:
            desc.update({'{}_{}'.format(self.name, 'image_darkfield'):
                        {'external': 'FILESTORE:',  # TODO: Need to fix
                         'source': 'PV:{}'.format(self._basename),
                         'shape': size, 'dtype': 'array'}})

        # Insert into here any additional parts for source
        return desc

    def read(self):
        val = super(AreaDetectorFileStore, self).read()
        uid = str(uuid.uuid4())
        val.update({'{}_{}_lightfield'.format(self.name, 'image'):
                    {'value': uid,
                     'timestamp': self._acq_signal.timestamp}})
        self._uid_cache.append(uid)

        if self._darkfield_int:
            if self._take_darkfield:
                uid = str(uuid.uuid4())
                self._uid_cache_darkfield.append(uid)
            else:
                uid = self._uid_cache_darkfield[-1]

            val.update({'{}_{}_darkfield'.format(self.name, 'image'):
                        {'value': uid,
                        'timestamp': self._acq_signal.timestamp}})

        return val


class AreaDetectorFileStoreHDF5(AreaDetectorFileStore):
    def __init__(self, *args, **kwargs):
        super(AreaDetectorFileStoreHDF5, self).__init__(*args, **kwargs)

        self._file_plugin = 'HDF1:'
        self.file_template = '%s%s_%6.6d.h5'

        # Create Signals for the shape

        for n in range(2):
            sig = self._ad_signal('{}ArraySize{}'
                                  .format(self._file_plugin, n),
                                  '_arraysize{}'.format(n),
                                  recordable=False)
            self.add_signal(sig)

        self.add_signal(self._ad_signal('FilePath', '_file_path',
                                        self._file_plugin,
                                        string=True,
                                        recordable=False))
        self.add_signal(self._ad_signal('FileName', '_file_name',
                                        self._file_plugin,
                                        string=True,
                                        recordable=False))
        self.add_signal(self._ad_signal('FileTemplate', '_file_template',
                                        self._file_plugin,
                                        string=True,
                                        recordable=False))
        self.add_signal(self._ad_signal('Capture', '_capture',
                                        self._file_plugin,
                                        recordable=False))
        self.add_signal(self._ad_signal('NumCaptured', '_num_captured',
                                        self._file_plugin,
                                        recordable=False))
        self.add_signal(self._ad_signal('FilePathExists', '_filepath_exists',
                                        self._file_plugin,
                                        recordable=False))

    def configure(self, *args, **kwargs):
        super(AreaDetectorFileStoreHDF5, self).configure(*args, **kwargs)

        # Wait here to make sure we are not still capturing data

        while self._capture.value == 1:
            print('[!!] Still capturing data .... waiting.')
            time.sleep(1)

        self._image_mode.put(1, wait=True)

        self._file_template.put(self.file_template, wait=True)
        self._write_plugin('AutoIncrement', 1)
        self._write_plugin('FileNumber', 0)
        self._write_plugin('AutoSave', 1)
        self._write_plugin('NumCapture', 1000000)
        self._write_plugin('FileWriteMode', 2)
        self._write_plugin('EnableCallbacks', 1)

        self._make_filename()

        self._file_path.put(self._ioc_file_path, wait=True)
        self._file_name.put(self._filename, wait=True)

        if not self._filepath_exists.value:
            raise IOError("Path {} does not exits on IOC!! Please Check"
                          .format(self._file_path.value))

        self._filestore_res = fs.insert_resource('AD_HDF5',
                                                 self._store_filename,
                                                 {'frame_per_point':
                                                  self._num_images.value})

        self._capture.put(1, wait=False)

    def _captured_changed(self, value, *args, **kwargs):
        if value == self._total_images:
            self._num_captured.clear_sub(self._captured_changed)
            # Close the capture plugin (closes the file)
            self._capture.put(0, wait=True)

    def deconfigure(self, *args, **kwargs):
        self._total_images = self._array_counter.value
        self._num_captured.subscribe(self._captured_changed)

        super(AreaDetectorFileStoreHDF5, self).deconfigure(*args, **kwargs)


class AreaDetectorFileStorePrinceton(AreaDetectorFileStore):
    def __init__(self, *args, **kwargs):
        super(AreaDetectorFileStorePrinceton, self).__init__(*args, **kwargs)

        self._file_plugin = 'cam1:'
        self.file_template = '%s%s_%6.6d.spe'

        sig = self._ad_signal('{}ArraySizeX'
                              .format(self._file_plugin),
                              '_arraysize0',
                              recordable=False)
        self.add_signal(sig)

        sig = self._ad_signal('{}ArraySizeY'
                              .format(self._file_plugin),
                              '_arraysize1',
                              recordable=False)
        self.add_signal(sig)

        self.add_signal(self._ad_signal('FilePath', '_file_path',
                                        self._file_plugin,
                                        string=True,
                                        recordable=False))
        self.add_signal(self._ad_signal('FileName', '_file_name',
                                        self._file_plugin,
                                        string=True,
                                        recordable=False))
        self.add_signal(self._ad_signal('FileTemplate', '_file_template',
                                        self._file_plugin,
                                        string=True,
                                        recordable=False))
        self.add_signal(self._ad_signal('FilePathExists', '_filepath_exists',
                                        self._file_plugin,
                                        recordable=False))

        # Acquisition mode (single image)
        self._image_acq_mode = 0

    def configure(self, *args, **kwargs):
        super(AreaDetectorFileStorePrinceton, self).configure(*args, **kwargs)
        self._image_mode.put(0, wait=True)
        self._file_template.put(self.file_template, wait=True)
        self._make_filename()
        self._file_path.put(self._ioc_file_path, wait=True)
        self._file_name.put(self._filename, wait=True)
        self._write_plugin('FileNumber', 0)
        self._filestore_res = fs.insert_resource('AD_SPE',
                                                 self._store_file_path,
                                                 {'template':
                                                  self._file_template.value,
                                                  'filename':
                                                  self._filename,
                                                  'frame_per_point': 1})
