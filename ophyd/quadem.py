from collections import OrderedDict

from .areadetector import (
    ADBase,
    DetectorBase,
    EpicsSignalWithRBV,
    ImagePlugin,
    SingleTrigger,
    StatsPlugin,
)
from .device import Component as Cpt
from .device import DynamicDeviceComponent as DDCpt
from .device import kind_context
from .signal import EpicsSignal, EpicsSignalRO, Kind, Signal
from .status import DeviceStatus


def _current_fields(attr_base, field_base, range_, **kwargs):
    defn = OrderedDict()
    for i in range_:
        attr = "{attr}{i}".format(attr=attr_base, i=i)
        suffix = "{field}{i}".format(field=field_base, i=i)
        defn[attr] = (EpicsSignal, suffix, kwargs)

    return defn


class QuadEMPort(ADBase):
    port_name = Cpt(Signal, value="")

    def __init__(self, port_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.port_name.put(port_name)


class QuadEM(SingleTrigger, DetectorBase):
    # These settings intentionally shadow the settings inherited from
    # DetectorBase.
    _default_read_attrs = None
    _default_configuration_attrs = None

    _status_type = DeviceStatus  # overrriding the default in SingleTrigger

    # This is needed because ophyd verifies that it can see all
    # of the nodes in the asyn pipeline, however these IOCs do not
    # expose their port name via a PV, but nevertheless server as the
    # root node for the plugins.
    # Leaving this port_name here for compatibility
    integration_time = Cpt(EpicsSignalWithRBV, "IntegrationTime", kind="config")
    averaging_time = Cpt(EpicsSignalWithRBV, "AveragingTime", kind="config")
    with kind_context("omitted") as OCpt:
        conf = Cpt(QuadEMPort, port_name="NSLS_EM")
        model = OCpt(EpicsSignalRO, "Model")
        firmware = OCpt(EpicsSignalRO, "Firmware")

        acquire_mode = OCpt(EpicsSignalWithRBV, "AcquireMode")
        acquire = OCpt(EpicsSignal, "Acquire")

        read_format = OCpt(EpicsSignalWithRBV, "ReadFormat")
        em_range = OCpt(EpicsSignalWithRBV, "Range")
        ping_pong = OCpt(EpicsSignalWithRBV, "PingPong")

        num_channels = OCpt(EpicsSignalWithRBV, "NumChannels")
        geometry = OCpt(EpicsSignalWithRBV, "Geometry")
        resolution = OCpt(EpicsSignalWithRBV, "Resolution")

        bias_state = OCpt(EpicsSignalWithRBV, "BiasState")
        bias_interlock = OCpt(EpicsSignalWithRBV, "BiasInterlock")
        bias_voltage = OCpt(EpicsSignalWithRBV, "BiasVoltage")
        hvs_readback = OCpt(EpicsSignalRO, "HVSReadback")
        hvv_readback = OCpt(EpicsSignalRO, "HVVReadback")
        hvi_readback = OCpt(EpicsSignalRO, "HVIReadback")

        values_per_read = OCpt(EpicsSignalWithRBV, "ValuesPerRead")
        sample_time = OCpt(EpicsSignalRO, "SampleTime_RBV")  # yay consistency
        num_average = OCpt(EpicsSignalRO, "NumAverage_RBV")
        num_averaged = OCpt(EpicsSignalRO, "NumAveraged_RBV")
        num_acquire = OCpt(EpicsSignalWithRBV, "NumAcquire")
        num_acquired = OCpt(EpicsSignalRO, "NumAcquired")
        read_data = OCpt(EpicsSignalRO, "ReadData")
        ring_overflows = OCpt(EpicsSignalRO, "RingOverflows")
        trigger_mode = OCpt(EpicsSignal, "TriggerMode")
        reset = OCpt(EpicsSignal, "Reset")

    current_names = DDCpt(
        _current_fields("ch", "CurrentName", range(1, 5), string=True)
    )
    current_offsets = DDCpt(_current_fields("ch", "CurrentOffset", range(1, 5)))
    current_offset_calcs = DDCpt(
        _current_fields("ch", "ComputeCurrentOffset", range(1, 5))
    )
    current_scales = DDCpt(_current_fields("ch", "CurrentScale", range(1, 5)))

    position_offset_x = Cpt(EpicsSignal, "PositionOffsetX")
    position_offset_y = Cpt(EpicsSignal, "PositionOffsetY")

    position_offset_calc_x = Cpt(EpicsSignal, "ComputePosOffsetX")
    position_offset_calc_y = Cpt(EpicsSignal, "ComputePosOffsetY")

    position_scale_x = Cpt(EpicsSignal, "PositionScaleX")
    position_scale_Y = Cpt(EpicsSignal, "PositionScaleY")

    image = Cpt(ImagePlugin, "image1:")
    current1 = Cpt(StatsPlugin, "Current1:")
    current2 = Cpt(StatsPlugin, "Current2:")
    current3 = Cpt(StatsPlugin, "Current3:")
    current4 = Cpt(StatsPlugin, "Current4:")

    sum_all = Cpt(StatsPlugin, "SumAll:")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.stage_sigs.update(
            [("acquire", 0), ("acquire_mode", 2)]  # if acquiring, stop  # single mode
        )
        self._acquisition_signal = self.acquire

        for i in range(1, 5):
            current = getattr(self, "current{}".format(i))
            current.mean_value.kind = Kind.hinted


class NSLS_EM(QuadEM):
    ...


class TetrAMM(QuadEM):
    conf = Cpt(QuadEMPort, port_name="TetrAMM", kind="omitted")


class APS_EM(QuadEM):
    conf = Cpt(QuadEMPort, port_name="APS_EM", kind="omitted")
