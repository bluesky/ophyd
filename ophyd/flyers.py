import time as ttime
import functools
import logging
from collections import OrderedDict

from .signal import (Signal, EpicsSignal, EpicsSignalRO)
from .status import DeviceStatus
from .device import (Device, Component as C)


logger = logging.getLogger(__name__)


class AreaDetectorTimeseriesCollector(Device):
    control = C(EpicsSignal, "TSControl")
    num_points = C(EpicsSignal, "TSNumPoints")
    cur_point = C(EpicsSignalRO, "TSCurrentPoint")
    waveform = C(EpicsSignalRO, "TSTotal")
    waveform_ts = C(EpicsSignalRO, "TSTimestamp")

    def __init__(self, prefix, *, read_attrs=None,
                 configuration_attrs=None, name=None,
                 parent=None, stream_name=None, **kwargs):
        if read_attrs is None:
            read_attrs = []

        if configuration_attrs is None:
            configuration_attrs = ['num_points']

        self.stream_name = stream_name

        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs,
                         name=name, parent=parent, **kwargs)

    def _get_waveforms(self):
        n = self.cur_point.get()
        if n:
            return (self.waveform.get(count=n),
                    self.waveform_ts.get(count=n))
        else:
            return ([], [])

    def kickoff(self):
        # Erase buffer and start collection
        self.control.put('Erase/Start', wait=True)
        # make status object
        status = DeviceStatus(self)
        # it always done, the scan should never even try to wait for this
        status._finished()
        return status

    def pause(self):
        # Stop without clearing buffers
        self.control.put('Stop', wait=True)

    def resume(self):
        # Resume without erasing
        self.control.put('Start', wait=True)

    def complete(self):
        if self.control.get(as_string=True) == 'Stop':
            raise RuntimeError('Not acquiring')

        self.pause()

        # Data is ready immediately
        st = DeviceStatus(self)
        st._finished(success=True)
        return st

    def collect(self):
        if self.control.get(as_string=True) != 'Stop':
            raise RuntimeError('Acquisition still in progress. Call complete()'
                               ' first.')

        payload_val, payload_time = self._get_waveforms()
        for v, t in zip(payload_val, payload_time):
            yield {'data': {self.name: v},
                   'timestamps': {self.name: t},
                   'time': t}

    def describe_collect(self):
        '''Describe details for the flyer collect() method'''
        desc = self._describe_attr_list(['waveform', 'waveform_ts'])
        return {self.stream_name: desc}


class WaveformCollector(Device):
    '''Waveform collector

    See: https://github.com/NSLS-II-CSX/timestamp

    Parameters
    ----------
    data_is_time : bool, optional
        Use time as the data being acquired
    '''
    select = C(EpicsSignal, "Sw-Sel")
    reset = C(EpicsSignal, "Rst-Sel")
    waveform_count = C(EpicsSignalRO, "Val:TimeN-I")
    waveform = C(EpicsSignalRO, "Val:Time-Wfrm")
    waveform_nord = C(EpicsSignalRO, "Val:Time-Wfrm.NORD")
    data_is_time = C(Signal)

    def __init__(self, prefix, *, read_attrs=None, configuration_attrs=None,
                 name=None, parent=None, data_is_time=True, stream_name=None,
                 **kwargs):
        if read_attrs is None:
            read_attrs = []

        if configuration_attrs is None:
            configuration_attrs = ['data_is_time']

        self.stream_name = stream_name

        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs,
                         name=name, parent=parent, **kwargs)

        self.data_is_time.put(data_is_time)

    def _get_waveform(self):
        if self.waveform_count.get():
            return self.waveform.get(count=int(self.waveform_nord.get()))
        else:
            return []

    def pause(self):
        # Stop without clearing buffers
        self.select.put(0, wait=True)

    def resume(self):
        # Resume without erasing
        self.select.put(1, wait=True)

    def complete(self):
        self.pause()
        st = DeviceStatus(self)
        st._finished(success=True)
        return st

    def kickoff(self):
        # Put us in reset mode
        self.select.put(2, wait=True)
        # Trigger processing
        self.reset.put(1, wait=True)
        # Start Buffer
        self.select.put(1, wait=True)
        # make status object
        status = DeviceStatus(self)
        # it always done, the scan should never even try to wait for this
        status._finished()
        return status

    def collect(self):
        payload = self._get_waveform()
        if payload:
            data_is_time = self.data_is_time.get()
            for i, v in enumerate(payload):
                x = v if data_is_time else i
                ev = {'data': {self.name: x},
                      'timestamps': {self.name: v},
                      'time': v}
                yield ev
        else:
            yield from []

    def _repr_info(self):
        yield from super()._repr_info()
        yield ('data_is_time', self.data_is_time.get())

    def describe_collect(self):
        '''Describe details for the flyer collect() method'''
        desc = self._describe_attr_list(['waveform'])
        return {self.stream_name: desc}


class MonitorFlyerMixin:
    '''A bluesky-compatible flyer mixin, using monitor_attrs

    At kickoff(), all monitor_attrs will be subscribed to and monitored for the
    until complete() is called. `complete` returns a DeviceStatus instance,
    which indicates when the data is ready to be collected.  The acquired
    values are then be retrievable as bluesky bulk-readable documents in
    collect().

    Parameters
    ----------
    monitor_attrs : list, optional
        List of signal attribute names to monitor
    '''
    def __init__(self, *args, monitor_attrs=None, stream_name=None, **kwargs):
        if monitor_attrs is None:
            monitor_attrs = []
        self.monitor_attrs = monitor_attrs
        self.stream_name = stream_name
        self._acquiring = False
        self._paused = False

        super().__init__(*args, **kwargs)

    def kickoff(self):
        '''Start collection

        Returns
        -------
        DeviceStatus
            This will be set to done when acquisition has begun
        '''
        self._collected_data = OrderedDict()
        self._start_time = ttime.time()
        self._acquiring = True
        self._paused = False

        for attr in self.monitor_attrs:
            obj = getattr(self, attr)
            if isinstance(obj, Device):
                raise ValueError('Cannot monitor sub-devices')
            self._collected_data[attr] = {'values': [],
                                          'timestamps': []
                                          }
            obj.subscribe(functools.partial(self._monitor_callback,
                                            attribute=attr))

        st = DeviceStatus(self)
        st._finished(success=True)
        return st

    def _monitor_callback(self, attribute=None, obj=None, value=None,
                          timestamp=None, **kwargs):
        '''A monitor_attr signal has changed'''
        if not self._acquiring or self._paused:
            return

        if value is None or timestamp is None:
            data = obj.read()[obj.name]
            value = data['value']
            timestamp = data['timestamp']

        collected = self._collected_data[attribute]
        collected['values'].append(value)
        collected['timestamps'].append(timestamp)

    def describe_collect(self):
        '''Description of monitored attributes retrieved by collect'''
        # single stream?
        desc = OrderedDict()
        for attr in self.monitor_attrs:
            desc.update(self._describe_attr_list([attr]))
        return {self.stream_name: desc}

    def _clear_monitors(self):
        '''Clear all subscriptions'''
        for attr in self._collected_data.keys():
            obj = getattr(self, attr)
            try:
                obj.clear_sub(self._monitor_callback)
            except Exception as ex:
                logger.debug('Failed to clear subscription',
                             exc_info=ex)

    def pause(self):
        '''Pause acquisition'''
        self._paused = True

    def resume(self):
        '''Resume acquisition'''
        self._paused = False

    def complete(self):
        '''Acquisition completed'''
        if not self._acquiring:
            raise RuntimeError('Not acquiring')

        self._acquiring = False
        self._paused = False
        self._clear_monitors()

        # Data is ready immediately
        st = DeviceStatus(self)
        st._finished(success=True)
        return st

    def collect(self):
        '''Retrieve all collected data'''
        if self._acquiring:
            raise RuntimeError('Acquisition still in progress. Call complete()'
                               ' first.')

        names = [getattr(self, attr).name
                 for attr in self._collected_data]

        collected = [dict(time=self._start_time,
                          timestamps={name: data['timestamps']},
                          data={name: data['values']},
                          )
                     for name, data in zip(names,
                                           self._collected_data.values())
                     ]

        self._collected_data = None
        return collected
