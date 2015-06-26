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
    _SUB_ACQ_DONE = 'acq_done'
    _SUB_DONE = 'done'
    _SUB_ACQ_CHECK = 'acq_check'

    def __init__(self, basename, stats=range(1, 6),
                 shutter=None, shutter_rb=None, shutter_val=(0, 1),
                 cam='cam1:', proc_plugin='Proc1:',
                 *args, **kwargs):
        """Initialize the AreaDetector class

        Parameters
        ----------
        basename : str
            The EPICS PV basename of the areaDetector
        cam : str
            The camera suffix (usually 'cam1:')
        proc_plugin : str
            The process plugin suffix
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
            1 to inhibit the shutter.
        """

        super(AreaDetector, self).__init__(*args, **kwargs)

        self._basename = basename
        self._cam = cam
        self._proc_plugin = proc_plugin

        # Acquisition mode (Multiple Images)
        self._image_acq_mode = 1

        # Default to not taking darkfield images
        self._darkfield_int = 0
        self._take_darkfield = False

        # Setup signals on camera
        self.add_signal(self._ad_signal('{}Acquire'.format(self._cam),
                                        '_acquire',
                                        recordable=False))
        self.add_signal(self._ad_signal('{}ImageMode'.format(self._cam),
                                        '_image_mode',
                                        recordable=False))
        self.add_signal(self._ad_signal('{}AcquireTime'.format(self._cam),
                                        '_acquire_time'),
                        add_property=True)
        self.add_signal(self._ad_signal('{}AcquirePeriod'.format(self._cam),
                                        '_acquire_period'),
                        add_property=True)
        self.add_signal(self._ad_signal('{}NumImages'.format(self._cam),
                                        '_num_images',
                                        recordable=False),
                        add_property=True)
        self.add_signal(self._ad_signal('{}NumExposures'.format(self._cam),
                                        '_num_exposures',
                                        recordable=False),
                        add_property=True)
        self.add_signal(self._ad_signal('{}ArrayCounter'.format(self._cam),
                                        '_array_counter',
                                        recordable=False))

        self._use_stats = bool(stats)
        self._stats = stats
        if self._use_stats:

            self._stats_counter = 0

            # Add Stats Signals
            for n in stats:
                # Here are the total counts (for point counters)

                sig = self._ad_signal('Stats{}:Total'.format(n),
                                      '_stats_total{}'.format(n),
                                      rw=False, recordable=True)

                self.add_signal(sig, add_property=True)

                # sig.subscribe(self._stats_changed)

        self._shutter_val = shutter
        self._shutter_rb_val = shutter_rb
        self._acq_num = None

        if shutter:
            if isinstance(shutter, Signal):
                self.add_signal(shutter, prop_name='_shutter')
            else:
                self.add_signal(EpicsSignal(write_pv=shutter,
                                            read_pv=shutter_rb,
                                            name='{}_shutter'.format(
                                                self.name),
                                            rw=True, alias='_shutter',
                                            recordable=False))
            self._shutter_value = shutter_val
        else:
            self._shutter = None
            self._shutter_value = None

        # Run a subscription on the acquire signal

        self._acq_count = 0
        self.add_acquire_signal(self._acquire)
        self._acquire.subscribe(self._acquire_changed)

        # FInally subscribe to our check_if_finished

        self.subscribe(self._check_if_finished,
                       event_type=self._SUB_ACQ_CHECK,
                       run=False)

    def _acquire_changed(self, value=None, old_value=None, **kwargs):
        if (old_value == 1) and (value == 0):
            # Negative going edge is done acquiring
            self._acq_count += 1
            self._run_subs(sub_type=self._SUB_ACQ_DONE)
            self._run_subs(sub_type=self._SUB_ACQ_CHECK)

    def _check_if_finished(self, **kwargs):
        if self._acq_count == self._acq_num:
            self._run_subs(sub_type=self._SUB_DONE)
            self._reset_sub(self._SUB_DONE)

    def _ad_signal(self, suffix, alias, plugin='', **kwargs):
        """Return a signal made from areaDetector database"""
        basename = self._basename + plugin + suffix
        return EpicsSignal('{}_RBV'.format(basename),
                           write_pv=basename,
                           name='{}{}'.format(self.name, alias),
                           alias=alias, **kwargs)

    def _write_plugin(self, name, value, plugin, wait=True, as_string=False,
                      verify=True):
        caput('{}{}{}'.format(self._basename, plugin, name),
              value, wait=wait)

    def __repr__(self):
        repr = ['basename={0._basename!r}'.format(self),
                'stats={0._stats!r}'.format(self),
                'shutter={0._shutter_val!r}'.format(self),
                'shutter_rb={0._shutter_rb_val!r}'.format(self),
                'shutter_val={0._shutter_value!r}'.format(self)]

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

        # If using the stats, configure the proc plugin

        if self._use_stats:
            self._write_plugin('EnableCallbacks', 1, self._proc_plugin)
            self._write_plugin('EnableFilter', 1, self._proc_plugin)
            self._write_plugin('FilterType', 2, self._proc_plugin)
            self._write_plugin('AutoResetFilter', 1, self._proc_plugin)
            self._write_plugin('FilterCallbacks', 1, self._proc_plugin)
            self._write_plugin('NumFilter', self._num_images.value,
                               self._proc_plugin)
            self._write_plugin('FilterCallbacks', 1, self._proc_plugin)

            # Turn on the stats plugins
            for i in self._stats:
                self._write_plugin('EnableCallbacks', 1,
                                   'Stats{}:'.format(i))
                self._write_plugin('BlockingCallbacks', 1,
                                   'Stats{}:'.format(i))
                self._write_plugin('ComputeStatistics', 1,
                                   'Stats{}:'.format(i))

        # Set the counter for number of acquisitions

        self._acquire_number = 0

        # Setup subscriptions

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

    def _start_acquire(self, **kwargs):
        """Do an actual acquisiiton"""
        if self._acq_count < self._acq_num:
            self._set_shutter(self._acq_count % 2)
            self._acq_signal.put(1, wait=False)

    def acquire(self, **kwargs):
        """Start acquisition including dark frames"""

        # Here start a chain which allows for a darkfield
        # image to be taken after a lightfield
        # First lets set if we need to take one
        self._acq_num = 1
        self._take_darkfield = False
        if self.darkfield_interval:
            if (self._acquire_number % self.darkfield_interval) == 0:
                self._acq_num += 1
                self._take_darkfield = True

        # Setup the return status

        status = DetectorStatus(self)

        def finished(**kwargs):
            self._acquire_number += 1
            status._finished()

        # Set acquire count, and subscriptions

        self._acq_count = 0
        self.subscribe(finished,
                       event_type=self._SUB_DONE, run=False)
        self._reset_sub(self._SUB_ACQ_DONE)
        self.subscribe(self._start_acquire,
                       event_type=self._SUB_ACQ_DONE, run=False)

        self._start_acquire()

        return status


class AreaDetectorFileStore(AreaDetector):
    def __init__(self, *args, **kwargs):
        self.store_file_path = os.path.join(kwargs.pop('file_path'), '')
        self.ioc_file_path = kwargs.pop('ioc_file_path', None)

        if self.ioc_file_path:
            self.ioc_file_path = os.path.join(self.ioc_file_path, '')

        self._reset_state()

        super(AreaDetectorFileStore, self).__init__(*args, **kwargs)

    def _reset_state(self):
        self._uid_cache = deque()
        self._abs_trigger_count = 0
        self._last_dark_uid = None
        self._last_light_uid = None
        self._filestore_res = None
        self._filename = ''

    def __repr__(self):
        repr = ['basename={0._basename!r}'.format(self),
                'stats={0._stats!r}'.format(self),
                'shutter={0._shutter_val!r}'.format(self),
                'shutter_rb={0._shutter_rb_val!r}'.format(self),
                'shutter_val={0._shutter_value!r}'.format(self),
                'file_path={0.store_file_path!r}'.format(self),
                'ioc_file_path={0.ioc_file_path!r}'.format(self)]

        return self._get_repr(repr)

    def _make_filename(self, seq=0):
        uid = str(uuid.uuid4())
        self._filename = uid

        # The tree is the year / month / day
        date = datetime.now().date()
        tree = (str(date.year), str(date.month), str(date.day), '')

        path = os.path.join(self.store_file_path, *tree)
        self._store_file_path = path
        self._store_filename = self._file_template.value % (path,
                                                            self._filename,
                                                            seq)

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
        self._abs_trigger_count = 0
        self._write_plugin('EnableCallbacks', 1, self._file_plugin)

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
        # run the base read
        val = super(AreaDetectorFileStore, self).read()
        # add a new uid + frame index to the internal cache
        self._uid_cache.append((str(uuid.uuid4()),
                                self._abs_trigger_count))
        # stash it for later use
        self._last_light_uid = self._uid_cache[-1]
        # increment the collected frame count (super important)
        self._abs_trigger_count += 1
        #  update the value dictionary
        val.update({'{}_{}_lightfield'.format(self.name, 'image'):
                    {'value': self._last_light_uid[0],
                     'timestamp': self._acq_signal.timestamp}})
        # if we are collecting dark field images
        if self._darkfield_int:
            if self._take_darkfield:
                # assume we have _taken_ a dark field collection after the last
                # light field

                # add an entry to the cache
                self._uid_cache.append((str(uuid.uuid4()),
                                        self._abs_trigger_count))
                # stash it individually for later reuse
                self._last_dark_uid = self._uid_cache[-1]
                # update the trigger count
                self._abs_trigger_count += 1
            # update the value dictionary with the uid of the most recent
            # dark field collection
            val.update({'{}_{}_darkfield'.format(self.name, 'image'):
                        {'value': self._last_dark_uid[0],
                        'timestamp': self._acq_signal.timestamp}})

        return val

    def deconfigure(self, *args, **kwargs):
        # clear state used during collection.
        self._reset_state()
        self._write_plugin('EnableCallbacks', 0, self._file_plugin)
        super(AreaDetectorFileStore, self).deconfigure(*args, **kwargs)


class AreaDetectorFSBulkEntry(AreaDetectorFileStore):
    def deconfigure(self, *args, **kwargs):

        for uid, i in self._uid_cache:
            fs.insert_datum(self._filestore_res, str(uid), {'point_number': i})

        super(AreaDetectorFSBulkEntry, self).deconfigure(*args, **kwargs)


class AreaDetectorFSIterativeWrite(AreaDetectorFileStore):
    def read(self):
        val = super(AreaDetectorFSIterativeWrite, self).read()

        fs.insert_datum(self._filestore_res, self._last_light_uid[0],
                        {'point_number': self._last_light_uid[1]})
        if self._take_darkfield:
            fs.insert_datum(self._filestore_res, self._last_dark_uid[0],
                            {'point_number': self._last_dark_uid[1]})

        return val


class AreaDetectorFileStoreHDF5(AreaDetectorFSBulkEntry):
    def __init__(self, *args, **kwargs):
        """Initialize the AreaDetector class

        Parameters
        ----------
        basename : str
            The EPICS PV basename of the areaDetector
        cam : str
            The camera suffix (usually 'cam1:')
        proc_plugin : str
            The process plugin suffix
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
            1 to inhibit the shutter.
        file_plugin : str
            The file plugin suffix (e.g., 'HDF1:')
        file_path : str
            The file path of where the data is stored. The tree (year / month
            day) is added to the path before writing to the IOC
        ioc_file_path : str
            If not None, this path is sent to the IOC while file_path is
            sent to the file store. This allows for windows style mounts
            where the unix path is different from the windows path.
        """
        self._file_plugin = kwargs.pop('file_plugin', 'HDF1:')

        super(AreaDetectorFileStoreHDF5, self).__init__(*args, **kwargs)

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

        # self._image_mode.put(1, wait=True)

        self._file_template.put(self.file_template, wait=True)
        self._write_plugin('AutoIncrement', 1, self._file_plugin)
        self._write_plugin('FileNumber', 0, self._file_plugin)
        self._write_plugin('AutoSave', 1, self._file_plugin)
        self._write_plugin('NumCapture', 10000000, self._file_plugin)
        self._write_plugin('FileWriteMode', 2, self._file_plugin)
        self._write_plugin('EnableCallbacks', 1, self._file_plugin)

        self._make_filename()

        self._file_path.put(self._ioc_file_path, wait=True)
        self._file_name.put(self._filename, wait=True)

        if not self._filepath_exists.value:
            raise IOError("Path {} does not exits on IOC!! Please Check"
                          .format(self._file_path.value))

        self._filestore_res = self._insert_fs_resource()
        # Place into capture mode
        self._capture.put(1, wait=False)

    def _insert_fs_resource(self):
        return fs.insert_resource('AD_HDF5',
                                  self._store_filename,
                                  {'frame_per_point':
                                   self._num_images.value})

    def _captured_changed(self, value, *args, **kwargs):
        if value == self._total_images:
            self._num_captured.clear_sub(self._captured_changed)

            # Close the capture plugin (closes the file)

            self._capture.put(0, wait=True)

    def deconfigure(self, *args, **kwargs):
        self._total_images = self._array_counter.value
        self._num_captured.subscribe(self._captured_changed)

        super(AreaDetectorFileStoreHDF5, self).deconfigure(*args, **kwargs)


class AreaDetectorFileStorePrinceton(AreaDetectorFSIterativeWrite):
    def __init__(self, *args, **kwargs):
        """Initialize the AreaDetector class

        Parameters
        ----------
        basename : str
            The EPICS PV basename of the areaDetector
        cam : str
            The camera suffix (usually 'cam1:')
        proc_plugin : str
            The process plugin suffix
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
            1 to inhibit the shutter.
        file_plugin : str
            The file plugin suffix (e.g., 'cam1:')
        file_path : str
            The file path of where the data is stored. The tree (year / month
            day) is added to the path before writing to the IOC
        ioc_file_path : str
            If not None, this path is sent to the IOC while file_path is
            sent to the file store. This allows for windows style mounts
            where the unix path is different from the windows path.
        """
        self._file_plugin = kwargs.pop('file_plugin', 'cam1:')

        super(AreaDetectorFileStorePrinceton, self).__init__(*args, **kwargs)

        self.file_template = '%s%s_%6.6d.spe'

        self.add_signal(self._ad_signal('{}ArraySizeX'
                                        .format(self._file_plugin),
                                        '_arraysize0',
                                        recordable=False))

        self.add_signal(self._ad_signal('{}ArraySizeY'
                                        .format(self._file_plugin),
                                        '_arraysize1',
                                        recordable=False))

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
        self._file_template.put(self.file_template, wait=True)
        self._make_filename()
        self._file_path.put(self._ioc_file_path, wait=True)
        self._file_name.put(self._filename, wait=True)
        self._write_plugin('FileNumber', 0, self._file_plugin)
        self._filestore_res = self._insert_fs_resource()

    def _insert_fs_resource(self):
        return fs.insert_resource('AD_SPE', self._store_file_path,
                                  {'template': self._file_template.value,
                                   'filename': self._filename,
                                   'frame_per_point': self._num_images.value})


class AreaDetectorFileStoreTIFF(AreaDetectorFSIterativeWrite):
    def __init__(self, *args, **kwargs):
        """Initialize the AreaDetector class

        Parameters
        ----------
        basename : str
            The EPICS PV basename of the areaDetector
        cam : str
            The camera suffix (usually 'cam1:')
        proc_plugin : str
            The process plugin suffix
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
            1 to inhibit the shutter.
        file_plugin : str
            The file plugin suffix (e.g., 'TIFF1:')
        file_path : str
            The file path of where the data is stored. The tree (year / month
            day) is added to the path before writing to the IOC
        ioc_file_path : str
            If not None, this path is sent to the IOC while file_path is
            sent to the file store. This allows for windows style mounts
            where the unix path is different from the windows path.
        """
        self._file_plugin = kwargs.pop('file_plugin', 'TIFF1:')

        super(AreaDetectorFileStoreTIFF, self).__init__(*args, **kwargs)

        self.file_template = '%s%s_%6.6d.tiff'

        self.add_signal(self._ad_signal('{}ArraySize0'
                                        .format(self._file_plugin),
                                        '_arraysize0',
                                        recordable=False))

        self.add_signal(self._ad_signal('{}ArraySize1'
                                        .format(self._file_plugin),
                                        '_arraysize1',
                                        recordable=False))

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

    def configure(self, *args, **kwargs):
        super(AreaDetectorFileStoreTIFF, self).configure(*args, **kwargs)
        # self._image_mode.put(0, wait=True)
        self._file_template.put(self.file_template, wait=True)
        self._make_filename()
        self._file_path.put(self._ioc_file_path, wait=True)
        self._file_name.put(self._filename, wait=True)
        self._write_plugin('FileNumber', 0, self._file_plugin)
        self._extra_AD_configuration()
        self._filestore_res = self._insert_fs_resource()

    def _insert_fs_resource(self):
        return fs.insert_resource('AD_TIFF', self._store_file_path,
                                  {'template': self._file_template.value,
                                   'filename': self._filename,
                                   'frame_per_point': self._num_images.value})

    def _extra_AD_configuration(self):
        pass


class AreaDetectorFileStoreTIFFSquashing(AreaDetectorFileStoreTIFF):

    def _insert_fs_resource(self):
        return fs.insert_resource('AD_TIFF', self._store_file_path,
                                  {'template': self._file_template.value,
                                   'filename': self._filename,
                                   'frame_per_point': 1})

    def _extra_AD_configuration(self):
        # set up processing to pre-smash image stack
        self._write_plugin('EnableCallbacks', 1, self._proc_plugin)
        self._write_plugin('EnableFilter', 1, self._proc_plugin)
        self._write_plugin('FilterType', 2, self._proc_plugin)
        self._write_plugin('AutoResetFilter', 1, self._proc_plugin)
        self._write_plugin('FilterCallbacks', 1, self._proc_plugin)
        self._write_plugin('NumFilter', self._num_images.value,
                           self._proc_plugin)
        self._write_plugin('FilterCallbacks', 1, self._proc_plugin)
        self._write_plugin('NDArrayPort',
                           self._proc_plugin.strip(':').upper(),
                           self._file_plugin)
