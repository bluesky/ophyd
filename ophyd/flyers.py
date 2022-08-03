import functools
import logging
import time as ttime
from collections import OrderedDict
from typing import Any, Dict, Generator, Iterable

from .device import BlueskyInterface
from .device import Component as Cpt
from .device import Device
from .signal import EpicsSignal, EpicsSignalRO, Signal
from .status import DeviceStatus, StatusBase
from .utils import OrderedDefaultDict

logger = logging.getLogger(__name__)


class FlyerInterface(BlueskyInterface):
    def kickoff(self) -> StatusBase:
        """Start a flyer

        The status object return is marked as done once flying
        has started.

        Returns
        -------
        kickoff_status : StatusBase
            Indicate when flying has started.

        """

    def complete(self) -> StatusBase:
        """Wait for flying to be complete.

        This can either be a question ("are you done yet") or a
        command ("please wrap up") to accommodate flyers that have a
        fixed trajectory (ex. high-speed raster scans) or that are
        passive collectors (ex MAIA or a hardware buffer).

        In either case, the returned status object should indicate when
        the device is actually finished flying.

        Returns
        -------
        complete_status : StatusBase
            Indicate when flying has completed
        """

    def collect(self) -> Generator[Dict, None, None]:
        """Retrieve data from the flyer as proto-events

        The events can be from a mixture of event streams, it is
        the responsibility of the consumer (ei the RunEngine) to sort
        them out.

        Yields
        ------
        event_data : dict
            Must have the keys {'time', 'timestamps', 'data'}.

        """

    def collect_tables(self) -> Iterable[Any]:
        """Retrieve data from flyer as tables

        PROPOSED


        Yields
        ------
        time : Iterable[Float]

        data : dict

        timestamps : dict
        """

    def describe_collect(self) -> Dict[str, Dict]:
        """Provide schema & meta-data from :meth:`collect`

        This is analogous to :meth:`describe`, but nested by stream name.

        This provides schema related information, (ex shape, dtype), the
        source (ex PV name), and if available, units, limits, precision etc.

        The data_keys are mapped to events from `collect` by matching the
        keys.

        Returns
        -------
        data_keys_by_stream : dict
            The keys must be strings and the values must be dict-like
            with keys that are str and the inner values are dict-like
            with the ``event_model.event_descriptor.data_key`` schema.
        """


class AreaDetectorTimeseriesCollector(Device):
    control = Cpt(EpicsSignal, "TSControl")
    num_points = Cpt(EpicsSignal, "TSNumPoints")
    cur_point = Cpt(EpicsSignalRO, "TSCurrentPoint")
    waveform = Cpt(EpicsSignalRO, "TSTotal")
    waveform_ts = Cpt(EpicsSignalRO, "TSTimestamp")

    _default_configuration_attrs = ("num_points",)
    _default_read_attrs = ()

    def __init__(self, *args, stream_name=None, **kwargs):

        self.stream_name = stream_name

        super().__init__(*args, **kwargs)

    def _get_waveforms(self):
        n = self.cur_point.get()
        if n:
            return (self.waveform.get(count=n), self.waveform_ts.get(count=n))
        else:
            return ([], [])

    def kickoff(self):
        # Erase buffer and start collection
        self.control.put("Erase/Start", wait=True)
        # make status object
        status = DeviceStatus(self)
        # it always done, the scan should never even try to wait for this
        status.set_finished()
        return status

    def pause(self):
        # Stop without clearing buffers
        self.control.put("Stop", wait=True)
        super().pause()

    def resume(self):
        # Resume without erasing
        self.control.put("Start", wait=True)
        super().resume()

    def complete(self):
        if self.control.get(as_string=True) == "Stop":
            raise RuntimeError("Not acquiring")

        self.pause()

        # Data is ready immediately
        st = DeviceStatus(self)
        st.set_finished()
        return st

    def collect(self):
        if self.control.get(as_string=True) != "Stop":
            raise RuntimeError(
                "Acquisition still in progress. Call complete()" " first."
            )

        payload_val, payload_time = self._get_waveforms()
        for v, t in zip(payload_val, payload_time):
            yield {"data": {self.name: v}, "timestamps": {self.name: t}, "time": t}

    def describe_collect(self):
        """Describe details for the flyer collect() method"""
        desc = OrderedDict()
        desc.update(self.waveform.describe())
        desc.update(self.waveform_ts.describe())
        return {self.stream_name: desc}


class WaveformCollector(Device):
    """Waveform collector

    See: https://github.com/NSLS-II-CSX/timestamp

    Parameters
    ----------
    data_is_time : bool, optional
        Use time as the data being acquired
    """

    _default_configuration_attrs = ()
    _default_read_attrs = ()

    select = Cpt(EpicsSignal, "Sw-Sel")
    reset = Cpt(EpicsSignal, "Rst-Sel")
    waveform_count = Cpt(EpicsSignalRO, "Val:TimeN-I")
    waveform = Cpt(EpicsSignalRO, "Val:Time-Wfrm")
    waveform_nord = Cpt(EpicsSignalRO, "Val:Time-Wfrm.NORD")
    data_is_time = Cpt(Signal)

    def __init__(self, *args, data_is_time=True, stream_name=None, **kwargs):
        self.stream_name = stream_name

        super().__init__(*args, **kwargs)

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
        st.set_finished()
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
        status.set_finished()
        return status

    def collect(self):
        payload = self._get_waveform()
        if payload:
            data_is_time = self.data_is_time.get()
            for i, v in enumerate(payload):
                x = v if data_is_time else i
                ev = {"data": {self.name: x}, "timestamps": {self.name: v}, "time": v}
                yield ev
        else:
            yield from []

    def _repr_info(self):
        yield from super()._repr_info()
        yield ("data_is_time", self.data_is_time.get())

    def describe_collect(self):
        """Describe details for the flyer collect() method"""
        desc = self._describe_attr_list(["waveform"])
        return {self.stream_name: desc}


class MonitorFlyerMixin(BlueskyInterface):
    """A bluesky-compatible flyer mixin, using monitor_attrs

    At kickoff(), all monitor_attrs will be subscribed to and monitored for the
    until complete() is called. `complete` returns a DeviceStatus instance,
    which indicates when the data is ready to be collected.  The acquired
    values are then be retrievable as bluesky bulk-readable documents in
    collect().

    Parameters
    ----------
    monitor_attrs : list, optional
        List of signal attribute names to monitor
    stream_names : dict, optional
        A mapping of attribute -> stream name
        If an attribute is not in this dictionary, the stream name will default
        to the object's name.
    pivot : bool, optional
        If set, each value and timestamp pair will be in separate events.
        Otherwise, a single event will be generated with an array. Defaults to
        False.
    """

    def __init__(
        self, *args, monitor_attrs=None, stream_names=None, pivot=False, **kwargs
    ):
        if monitor_attrs is None:
            monitor_attrs = []
        if stream_names is None:
            stream_names = {}

        self.monitor_attrs = monitor_attrs
        self.stream_names = stream_names
        self._acquiring = False
        self._paused = False
        self._collected_data = None
        self._monitors = {}
        self._pivot = pivot

        super().__init__(*args, **kwargs)

    def kickoff(self):
        """Start collection

        Returns
        -------
        DeviceStatus
            This will be set to done when acquisition has begun
        """
        self._collected_data = OrderedDefaultDict(
            lambda: {"values": [], "timestamps": []}
        )
        self._start_time = ttime.time()
        self._acquiring = True
        self._paused = False
        self._add_monitors()
        st = DeviceStatus(self)
        st.set_finished()
        return st

    def _add_monitors(self):
        for attr in self.monitor_attrs:
            obj = getattr(self, attr)
            if isinstance(obj, Device):
                raise ValueError("Cannot monitor Devices, only Signals.")

            cb = functools.partial(self._monitor_callback, attribute=attr)
            self._monitors[obj] = cb
            obj.subscribe(cb)

    def _monitor_callback(
        self, attribute=None, obj=None, value=None, timestamp=None, **kwargs
    ):
        """A monitor_attr signal has changed"""
        if not self._acquiring or self._paused:
            return

        if value is None or timestamp is None:
            data = obj.read()[obj.name]
            value = data["value"]
            timestamp = data["timestamp"]

        collected = self._collected_data[attribute]
        collected["values"].append(value)
        collected["timestamps"].append(timestamp)

    def _get_stream_name(self, attr):
        obj = getattr(self, attr)
        return self.stream_names.get(attr, obj.name)

    def _describe_attr_list(self, attrs):
        desc = OrderedDict()
        for attr in attrs:
            desc.update(getattr(self, attr).describe())
        return desc

    def _describe_with_dtype(self, attr, *, dtype="array"):
        """Describe an attribute and change its dtype"""
        desc = self._describe_attr_list([attr])

        obj = getattr(self, attr)
        desc[obj.name]["dtype"] = dtype
        return desc

    def describe_collect(self):
        """Description of monitored attributes retrieved by collect"""
        if self._pivot:
            return {
                self._get_stream_name(attr): self._describe_attr_list([attr])
                for attr in self.monitor_attrs
            }
        else:
            return {
                self._get_stream_name(attr): self._describe_with_dtype(
                    attr, dtype="array"
                )
                for attr in self.monitor_attrs
            }

    def _clear_monitors(self):
        """Clear all subscriptions"""
        for obj, monitor in self._monitors.items():
            try:
                obj.clear_sub(monitor, event_type=obj._default_sub)
            except Exception as ex:
                logger.debug("Failed to clear subscription", exc_info=ex)

        self._monitors.clear()

    def pause(self):
        """Pause acquisition"""
        if not self._acquiring:
            # nothing to do
            return
        self._paused = True
        self._clear_monitors()
        super().pause()

    def resume(self):
        """Resume acquisition"""
        if not self._acquiring:
            # nothing to do
            return
        self._paused = False
        self._add_monitors()
        super().resume()

    def complete(self):
        """Acquisition completed"""
        if not self._acquiring:
            raise RuntimeError("Not acquiring")

        self._acquiring = False
        self._paused = False
        self._clear_monitors()

        # Data is ready immediately
        st = DeviceStatus(self)
        st.set_finished()
        return st

    def collect(self):
        """Retrieve all collected data"""
        if self._acquiring:
            raise RuntimeError(
                "Acquisition still in progress. Call complete()" " first."
            )

        collected = self._collected_data
        self._collected_data = None

        if self._pivot:
            for attr, data in collected.items():
                name = getattr(self, attr).name
                for ts, value in zip(data["timestamps"], data["values"]):
                    yield dict(
                        time=ts,
                        timestamps={name: ts},
                        data={name: value},
                    )
        else:
            for attr, data in collected.items():
                name = getattr(self, attr).name
                yield dict(
                    time=self._start_time,
                    timestamps={name: data["timestamps"]},
                    data={name: data["values"]},
                )
