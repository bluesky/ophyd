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
                 parent=None, **kwargs):
        if read_attrs is None:
            read_attrs = []

        if configuration_attrs is None:
            configuration_attrs = ['num_points']

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
        self.stop()

    def resume(self):
        # Resume without erasing
        self.control.put('Start', wait=True)

    def stop(self):
        # Stop without clearing buffers
        self.control.put('Stop', wait=True)

    def collect(self):
        self.stop()
        payload_val, payload_time = self._get_waveforms()
        for v, t in zip(payload_val, payload_time):
            yield {'data': {self.name: v},
                   'timestamps': {self.name: t},
                   'time': t}

    def describe_collect(self):
        '''Describe details for the flyer collect() method'''
        return [self._describe_attr_list(['waveform', 'waveform_ts'])]


class WaveformCollector(Device):
    select = C(EpicsSignal, "Sw-Sel")
    reset = C(EpicsSignal, "Rst-Sel")
    waveform_count = C(EpicsSignalRO, "Val:TimeN-I")
    waveform = C(EpicsSignalRO, "Val:Time-Wfrm")
    waveform_nord = C(EpicsSignalRO, "Val:Time-Wfrm.NORD")
    data_is_time = C(Signal)

    def __init__(self, prefix, *, read_attrs=None,
                 configuration_attrs=None, name=None,
                 parent=None, data_is_time=True, **kwargs):
        if read_attrs is None:
            read_attrs = []

        if configuration_attrs is None:
            configuration_attrs = ['data_is_time']

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
        self.stop()

    def resume(self):
        # Resume without erasing
        self.select.put(1, wait=True)

    def stop(self):
        # Stop without clearing buffers
        self.select.put(0, wait=True)

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
        self.stop()
        payload = self._get_waveform()
        if payload:
            data_is_time = self.data_is_time.get()
            for i, v in enumerate(payload):
                x = v if data_is_time else i
                ev = {'data': {self.name: x},
                      'timestamps': {self.name: v},
                      'time': v}
                yield ev

    def _repr_info(self):
        yield from super()._repr_info()
        yield ('data_is_time', self.data_is_time.get())

    def describe_collect(self):
        '''Describe details for the flyer collect() method'''
        return [self._describe_attr_list(['waveform'])]


class MonitorFlyerMixin(Device):
    '''A bluesky flyer device, using monitor_attrs
    '''
    def __init__(self, prefix, monitor_attrs=None, **kwargs):
        if monitor_attrs is None:
            monitor_attrs = []

        self.monitor_attrs = monitor_attrs

        super().__init__(prefix, **kwargs)
        self._acquiring = False

    def kickoff(self):
        self._status = DeviceStatus(self)
        self._collected_data = OrderedDict()
        self._start_time = ttime.time()
        self._acquiring = True

        for attr in self.monitor_attrs:
            obj = getattr(self, attr)
            if isinstance(obj, Device):
                raise ValueError('Cannot monitor sub-devices')
            self._collected_data[attr] = {'values': [],
                                          'timestamps': []
                                          }
            obj.subscribe(functools.partial(self._monitor_callback,
                                            attribute=attr))

        return self._status

    def _monitor_callback(self, attribute=None, obj=None, value=None,
                          timestamp=None, **kwargs):
        if not self._acquiring:
            return

        if value is None or timestamp is None:
            data = obj.read()[obj.name]
            value = data['value']
            timestamp = data['timestamp']

        collected = self._collected_data[attribute]
        collected['values'].append(value)
        collected['timestamps'].append(timestamp)

    def describe_collect(self):
        return [self._describe_attr_list([attr])
                for attr in self.monitor_attrs]

    def _clear_monitors(self):
        for attr in self._collected_data.keys():
            obj = getattr(self, attr)
            try:
                obj.clear_sub(self._monitor_callback)
            except Exception as ex:
                logger.debug('Failed to clear subscription',
                             exc_info=ex)

    def pause(self):
        self._acquiring = False

    def resume(self):
        self._acquiring = True

    def stop(self):
        self._clear_monitors()
        try:
            super().stop()
        finally:
            if not self._status.done:
                self._status._finished(success=True)

    def collect(self):
        self.stop()

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
