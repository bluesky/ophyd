from __future__ import print_function
from .detector import SignalDetector
from .signal import EpicsSignal
from epics import caget, caput
import platform
import hashlib
import getpass
import time


class AreaDetector(SignalDetector):
    def __init__(self, basename, *args, **kwargs):
        super(AreaDetector, self).__init__(*args, **kwargs)
        self._basename = basename

        signals = []
        signals.append(self._ad_signal('cam1:Acquire', '_acquire'))
        signals.append(self._ad_signal('cam1:AcquireTime', '_acquire_time'))
        signals.append(self._ad_signal('cam1:NumImages', '_num_images'))
        signals.append(self._ad_signal('cam1:ImageMode', '_image_mode'))

        # Add Stats Signals

        for n in range(1, 6):
            signals.append(self._ad_signal('Stats{}:Total'.format(n),
                                           '_total{}'.format(n),
                                           rw=False))

        for sig in signals:
            self.add_signal(sig)

        self._acq_signal = self._acquire

    def _ad_signal(self, suffix, alias, **kwargs):
        """Return a signal made from areaDetector database"""
        return EpicsSignal('{}{}_RBV'.format(self._basename, suffix),
                           write_pv='{}{}'.format(self._basename, suffix),
                           name='{}{}'.format(self.name, alias),
                           alias=alias, **kwargs)

    def configure(self, **kwargs):
        """Configure areaDetctor detector"""

        # Stop Acquisition
        self._old_acquire = self._acquire.get()
        self._acquire.put(0, wait=True)

        # Set the image mode to multiple
        self._old_image_mode = self._image_mode.get()
        self._image_mode.put(1, wait=True)

    def deconfigure(self, **kwargs):
        """DeConfigure areaDetector detector"""
        self._image_mode.put(self._old_image_mode, wait=True)
        self._acquire.put(self._old_acquire, wait=False)


class AreaDetectorFileStore(AreaDetector):
    def __init__(self, *args, **kwargs):
        super(AreaDetectorFileStore, self).__init__(*args, **kwargs)
        self._file_plugin = 'HDF1:'
        self.file_path = '/GPFS/xf23id/xf23id1/test_2/'

    def _write_plugin(self, name, value, wait=True, as_string=False,
                      verify=True):
        caput('{}{}{}'.format(self._basename, self._file_plugin, name),
              value, wait=wait)
        if verify:
            time.sleep(0.1)
            val = self._read_plugin(name, as_string=as_string)
            if val != value:
                raise IOError('Unable to correctly set {}'.format(name))

    def _read_plugin(self, name, **kwargs):
        return caget('{}{}{}_RBV'.format(self._basename,
                                         self._file_plugin, name),
                     **kwargs)

    def _make_filename(self):
        self._filename = hashlib.sha1('{}{}{}{}'
                                      .format(time.time(),
                                              platform.node(),
                                              getpass.getuser(),
                                              self._basename)).hexdigest()

    def configure(self, *args, **kwargs):
        super(AreaDetectorFileStore, self).configure(*args, **kwargs)

        self._make_filename()
        self._write_plugin('FilePath', self.file_path, as_string=True)
        self._write_plugin('FileName', self._filename, as_string=True)
        if self._read_plugin('FilePathExists') == 0:
            raise Exception('File Path does not exits on server')
        self._write_plugin('AutoIncrement', 1)
        self._write_plugin('FileNumber', 0)
        self._write_plugin('FileTemplate', '%s%s_%3.3d.h5', as_string=True)
        self._write_plugin('NumCapture', 0)
        self._write_plugin('AutoSave', 1)
        self._write_plugin('FileWriteMode', 2)
        self._write_plugin('EnableCallbacks', 1)
        self._write_plugin('Capture', 1, wait=False)

    def deconfigure(self, *args, **kwargs):
        self._write_plugin('Capture', 0, wait=True)
        super(AreaDetectorFileStore, self).deconfigure(*args, **kwargs)

    @property
    def source(self):
        src = AreaDetector.source(self)
        print(src)
        # Insert into here any additional parts for source
        return src

    def read(self):
        val = AreaDetector.read(self)
        print(val)
        # Add to val any parts to insert into MDS
        return val
