from __future__ import print_function, division, absolute_import

from collections import deque
from datetime import datetime

from .detector import SignalDetector, DetectorStatus
from .signal import EpicsSignal, Signal
from epics import caput


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

    @property
    def count_time(self):
        return self.acquire_time * self.num_images

    @count_time.setter
    def count_time(self, val):
        self.acquire_time = val / self.num_images

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
