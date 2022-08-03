import logging
from collections import OrderedDict

from .areadetector import EpicsSignalWithRBV as SignalWithRBV
from .device import Component as Cpt
from .device import Device
from .device import DynamicDeviceComponent as DDC
from .device import Kind
from .signal import EpicsSignal, EpicsSignalRO, Signal

logger = logging.getLogger(__name__)


class ROI(Device):

    # 'name' is not an allowed attribute
    label = Cpt(EpicsSignal, "NM", lazy=True)
    count = Cpt(EpicsSignalRO, "", lazy=True)
    net_count = Cpt(EpicsSignalRO, "N", lazy=True)
    preset_count = Cpt(EpicsSignal, "P", lazy=True)
    is_preset = Cpt(EpicsSignal, "IP", lazy=True)
    bkgnd_chans = Cpt(EpicsSignal, "BG", lazy=True)
    hi_chan = Cpt(EpicsSignal, "HI", lazy=True)
    lo_chan = Cpt(EpicsSignal, "LO", lazy=True)

    def __init__(
        self,
        prefix,
        *,
        read_attrs=None,
        configuration_attrs=None,
        name=None,
        parent=None,
        **kwargs
    ):

        super().__init__(
            prefix,
            read_attrs=read_attrs,
            configuration_attrs=configuration_attrs,
            name=name,
            parent=parent,
            **kwargs
        )


def add_rois(range_, **kwargs):
    """Add one or more ROIs to an MCA instance

    Parameters
    ----------
    range_ : sequence of ints
        Must be be in the set [0,31]

    By default, an EpicsMCA is initialized with all 32 rois.
    These provide the following Components as EpicsSignals (N=[0,31]):
    EpicsMCA.rois.roiN.(label,count,net_count,preset_cnt, is_preset,
    bkgnd_chans, hi_chan, lo_chan)
    """
    defn = OrderedDict()

    for roi in range_:
        if not (0 <= roi < 32):
            raise ValueError("roi must be in the set [0,31]")

        attr = "roi{}".format(roi)
        defn[attr] = (ROI, ".R{}".format(roi), kwargs)

    return defn


class EpicsMCARecord(Device):
    """SynApps MCA Record interface"""

    stop_signal = Cpt(EpicsSignal, ".STOP", kind="omitted")
    preset_real_time = Cpt(EpicsSignal, ".PRTM", kind=Kind.config | Kind.normal)
    preset_live_time = Cpt(EpicsSignal, ".PLTM", kind="omitted")
    elapsed_real_time = Cpt(EpicsSignalRO, ".ERTM")
    elapsed_live_time = Cpt(EpicsSignalRO, ".ELTM", kind="omitted")

    spectrum = Cpt(EpicsSignalRO, ".VAL")
    background = Cpt(EpicsSignalRO, ".BG", kind="omitted")
    mode = Cpt(EpicsSignal, ".MODE", string=True, kind="omitted")

    rois = DDC(add_rois(range(0, 32), kind="omitted"), kind="omitted")

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # could arguably be made a configuration_attr instead...
        self.stage_sigs["mode"] = "PHA"

    def stop(self, *, success=False):
        self.stop_signal.put(1)


class EpicsMCA(EpicsMCARecord):
    """mca records with extras from mca.db"""

    start = Cpt(EpicsSignal, "Start", kind="omitted")
    stop_signal = Cpt(EpicsSignal, "Stop", kind="omitted")
    erase = Cpt(EpicsSignal, "Erase", kind="omitted")
    erase_start = Cpt(EpicsSignal, "EraseStart", trigger_value=1, kind="omitted")

    check_acquiring = Cpt(EpicsSignal, "CheckACQG", kind="omitted")
    client_wait = Cpt(EpicsSignal, "ClientWait", kind="omitted")
    enable_wait = Cpt(EpicsSignal, "EnableWait", kind="omitted")
    force_read = Cpt(EpicsSignal, "Read", kind="omitted")
    set_client_wait = Cpt(EpicsSignal, "SetClientWait", kind="omitted")
    status = Cpt(EpicsSignal, "Status", kind="omitted")
    when_acq_stops = Cpt(EpicsSignal, "WhenAcqStops", kind="omitted")
    why1 = Cpt(EpicsSignal, "Why1", kind="omitted")
    why2 = Cpt(EpicsSignal, "Why2", kind="omitted")
    why3 = Cpt(EpicsSignal, "Why3", kind="omitted")
    why4 = Cpt(EpicsSignal, "Why4", kind="omitted")


class EpicsMCAReadNotify(EpicsMCARecord):
    """mca record with extras from mcaReadNotify.db"""

    start = Cpt(EpicsSignal, "Start", kind="omitted")
    stop_signal = Cpt(EpicsSignal, "Stop", kind="omitted")
    erase = Cpt(EpicsSignal, "Erase", kind="omitted")
    erase_start = Cpt(EpicsSignal, "EraseStart", trigger_value=1, kind="omitted")

    check_acquiring = Cpt(EpicsSignal, "CheckACQG", kind="omitted")
    client_wait = Cpt(EpicsSignal, "ClientWait", kind="omitted")
    enable_wait = Cpt(EpicsSignal, "EnableWait", kind="omitted")
    force_read = Cpt(EpicsSignal, "Read", kind="omitted")
    set_client_wait = Cpt(EpicsSignal, "SetClientWait", kind="omitted")
    status = Cpt(EpicsSignal, "Status", kind="omitted")


class EpicsMCACallback(Device):
    """Callback-related signals for MCA devices"""

    read_callback = Cpt(EpicsSignal, "ReadCallback")
    read_data_once = Cpt(EpicsSignal, "ReadDataOnce")
    read_status_once = Cpt(EpicsSignal, "ReadStatusOnce")
    collect_data = Cpt(EpicsSignal, "CollectData")


class EpicsDXP(Device):
    """All high-level DXP parameters for each channel"""

    preset_mode = Cpt(EpicsSignal, "PresetMode", string=True)

    live_time_output = Cpt(SignalWithRBV, "LiveTimeOutput", string=True)
    elapsed_live_time = Cpt(EpicsSignal, "ElapsedLiveTime")
    elapsed_real_time = Cpt(EpicsSignal, "ElapsedRealTime")
    elapsed_trigger_live_time = Cpt(EpicsSignal, "ElapsedTriggerLiveTime")

    # Trigger Filter PVs
    trigger_peaking_time = Cpt(SignalWithRBV, "TriggerPeakingTime")
    trigger_threshold = Cpt(SignalWithRBV, "TriggerThreshold")
    trigger_gap_time = Cpt(SignalWithRBV, "TriggerGapTime")
    trigger_output = Cpt(SignalWithRBV, "TriggerOutput", string=True)
    max_width = Cpt(SignalWithRBV, "MaxWidth")

    # Energy Filter PVs
    peaking_time = Cpt(SignalWithRBV, "PeakingTime")
    energy_threshold = Cpt(SignalWithRBV, "EnergyThreshold")
    gap_time = Cpt(SignalWithRBV, "GapTime")

    # Baseline PVs
    baseline_cut_percent = Cpt(SignalWithRBV, "BaselineCutPercent")
    baseline_cut_enable = Cpt(SignalWithRBV, "BaselineCutEnable")
    baseline_filter_length = Cpt(SignalWithRBV, "BaselineFilterLength")
    baseline_threshold = Cpt(SignalWithRBV, "BaselineThreshold")
    baseline_energy_array = Cpt(EpicsSignal, "BaselineEnergyArray")
    baseline_histogram = Cpt(EpicsSignal, "BaselineHistogram")
    baseline_threshold = Cpt(SignalWithRBV, "BaselineThreshold")

    # Misc PVs
    preamp_gain = Cpt(SignalWithRBV, "PreampGain")
    detector_polarity = Cpt(SignalWithRBV, "DetectorPolarity")
    reset_delay = Cpt(SignalWithRBV, "ResetDelay")
    decay_time = Cpt(SignalWithRBV, "DecayTime")
    max_energy = Cpt(SignalWithRBV, "MaxEnergy")
    adc_percent_rule = Cpt(SignalWithRBV, "ADCPercentRule")
    max_width = Cpt(SignalWithRBV, "MaxWidth")

    # read-only diagnostics
    triggers = Cpt(EpicsSignalRO, "Triggers", lazy=True)
    events = Cpt(EpicsSignalRO, "Events", lazy=True)
    overflows = Cpt(EpicsSignalRO, "Overflows", lazy=True)
    underflows = Cpt(EpicsSignalRO, "Underflows", lazy=True)
    input_count_rate = Cpt(EpicsSignalRO, "InputCountRate", lazy=True)
    output_count_rate = Cpt(EpicsSignalRO, "OutputCountRate", lazy=True)

    mca_bin_width = Cpt(EpicsSignalRO, "MCABinWidth_RBV")
    calibration_energy = Cpt(EpicsSignalRO, "CalibrationEnergy_RBV")
    current_pixel = Cpt(EpicsSignal, "CurrentPixel")
    dynamic_range = Cpt(EpicsSignalRO, "DynamicRange_RBV")

    # Preset options
    preset_events = Cpt(SignalWithRBV, "PresetEvents")
    preset_mode = Cpt(SignalWithRBV, "PresetMode", string=True)
    preset_triggers = Cpt(SignalWithRBV, "PresetTriggers")

    # Trace options
    trace_data = Cpt(EpicsSignal, "TraceData")
    trace_mode = Cpt(SignalWithRBV, "TraceMode", string=True)
    trace_time_array = Cpt(EpicsSignal, "TraceTimeArray")
    trace_time = Cpt(SignalWithRBV, "TraceTime")


class EpicsDXPLowLevelParameter(Device):
    param_name = Cpt(EpicsSignal, "Name")
    value = Cpt(SignalWithRBV, "Val")


class EpicsDXPLowLevel(Device):
    num_low_level_params = Cpt(EpicsSignal, "NumLLParams")
    read_low_level_params = Cpt(EpicsSignal, "ReadLLParams")

    parameter_prefix = "LL{}"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._parameter_cache = {}

    def get_low_level_parameter(self, index):
        """Get a DXP low level parameter

        Parameters
        ----------
        index : int
            In the range of [0, 229]

        Returns
        -------
        param : EpicsDXPLowLevelParameter
        """
        try:
            return self._parameter_cache[index]
        except KeyError:
            pass

        prefix = "{}{}".format(self.prefix, self.parameter_prefix)
        name = "{}_param{}".format(self.name, index)
        param = EpicsDXPLowLevelParameter(prefix, name=name)
        self._parameter_cache[index] = param
        return param


class EpicsDXPMapping(Device):
    apply = Cpt(EpicsSignal, "Apply")
    auto_apply = Cpt(SignalWithRBV, "AutoApply")
    auto_pixels_per_buffer = Cpt(SignalWithRBV, "AutoPixelsPerBuffer")
    buffer_size = Cpt(EpicsSignalRO, "BufferSize_RBV")
    collect_mode = Cpt(SignalWithRBV, "CollectMode")
    ignore_gate = Cpt(SignalWithRBV, "IgnoreGate")
    input_logic_polarity = Cpt(SignalWithRBV, "InputLogicPolarity")
    list_mode = Cpt(SignalWithRBV, "ListMode")
    mbytes_read = Cpt(EpicsSignalRO, "MBytesRead_RBV")
    next_pixel = Cpt(EpicsSignal, "NextPixel")
    pixel_advance_mode = Cpt(SignalWithRBV, "PixelAdvanceMode")
    pixels_per_buffer = Cpt(SignalWithRBV, "PixelsPerBuffer")
    pixels_per_run = Cpt(SignalWithRBV, "PixelsPerRun")
    read_rate = Cpt(EpicsSignalRO, "ReadRate_RBV")
    sync_count = Cpt(SignalWithRBV, "SyncCount")


class EpicsDXPBaseSystem(Device):
    channel_advance = Cpt(EpicsSignal, "ChannelAdvance")
    client_wait = Cpt(EpicsSignal, "ClientWait")
    dwell = Cpt(EpicsSignal, "Dwell")
    max_scas = Cpt(EpicsSignal, "MaxSCAs")
    num_scas = Cpt(SignalWithRBV, "NumSCAs")
    poll_time = Cpt(SignalWithRBV, "PollTime")
    prescale = Cpt(EpicsSignal, "Prescale")
    save_system = Cpt(SignalWithRBV, "SaveSystem")
    save_system_file = Cpt(EpicsSignal, "SaveSystemFile")
    set_client_wait = Cpt(EpicsSignal, "SetClientWait")


class EpicsDXPMultiElementSystem(EpicsDXPBaseSystem):
    # Preset info
    preset_events = Cpt(EpicsSignal, "PresetEvents")
    preset_live_time = Cpt(EpicsSignal, "PresetLive")
    preset_real_time = Cpt(EpicsSignal, "PresetReal")
    preset_mode = Cpt(EpicsSignal, "PresetMode", string=True)
    preset_triggers = Cpt(EpicsSignal, "PresetTriggers")

    # Acquisition
    erase_all = Cpt(EpicsSignal, "EraseAll")
    erase_start = Cpt(EpicsSignal, "EraseStart", trigger_value=1)
    start_all = Cpt(EpicsSignal, "StartAll")
    stop_all = Cpt(EpicsSignal, "StopAll")

    # Status
    set_acquire_busy = Cpt(EpicsSignal, "SetAcquireBusy")
    acquire_busy = Cpt(EpicsSignal, "AcquireBusy")
    status_all = Cpt(EpicsSignal, "StatusAll")
    status_all_once = Cpt(EpicsSignal, "StatusAllOnce")
    acquiring = Cpt(EpicsSignal, "Acquiring")

    # Reading
    read_baseline_histograms = Cpt(EpicsSignal, "ReadBaselineHistograms")
    read_all = Cpt(EpicsSignal, "ReadAll")
    read_all_once = Cpt(EpicsSignal, "ReadAllOnce")

    # As a debugging note, if snl_connected is not '1', your IOC is
    # misconfigured:
    snl_connected = Cpt(EpicsSignal, "SNL_Connected")

    # Copying to individual elements
    copy_adcp_ercent_rule = Cpt(EpicsSignal, "CopyADCPercentRule")
    copy_baseline_cut_enable = Cpt(EpicsSignal, "CopyBaselineCutEnable")
    copy_baseline_cut_percent = Cpt(EpicsSignal, "CopyBaselineCutPercent")
    copy_baseline_filter_length = Cpt(EpicsSignal, "CopyBaselineFilterLength")
    copy_baseline_threshold = Cpt(EpicsSignal, "CopyBaselineThreshold")
    copy_decay_time = Cpt(EpicsSignal, "CopyDecayTime")
    copy_detector_polarity = Cpt(EpicsSignal, "CopyDetectorPolarity")
    copy_energy_threshold = Cpt(EpicsSignal, "CopyEnergyThreshold")
    copy_gap_time = Cpt(EpicsSignal, "CopyGapTime")
    copy_max_energy = Cpt(EpicsSignal, "CopyMaxEnergy")
    copy_max_width = Cpt(EpicsSignal, "CopyMaxWidth")
    copy_peaking_time = Cpt(EpicsSignal, "CopyPeakingTime")
    copy_preamp_gain = Cpt(EpicsSignal, "CopyPreampGain")
    copy_roic_hannel = Cpt(EpicsSignal, "CopyROIChannel")
    copy_roie_nergy = Cpt(EpicsSignal, "CopyROIEnergy")
    copy_roi_sca = Cpt(EpicsSignal, "CopyROI_SCA")
    copy_reset_delay = Cpt(EpicsSignal, "CopyResetDelay")
    copy_trigger_gap_time = Cpt(EpicsSignal, "CopyTriggerGapTime")
    copy_trigger_peaking_time = Cpt(EpicsSignal, "CopyTriggerPeakingTime")
    copy_trigger_threshold = Cpt(EpicsSignal, "CopyTriggerThreshold")

    # do_* executes the process:
    do_read_all = Cpt(EpicsSignal, "DoReadAll")
    do_read_baseline_histograms = Cpt(EpicsSignal, "DoReadBaselineHistograms")
    do_read_traces = Cpt(EpicsSignal, "DoReadTraces")
    do_status_all = Cpt(EpicsSignal, "DoStatusAll")

    # Time
    dead_time = Cpt(EpicsSignal, "DeadTime")
    elapsed_live = Cpt(EpicsSignal, "ElapsedLive")
    elapsed_real = Cpt(EpicsSignal, "ElapsedReal")
    idead_time = Cpt(EpicsSignal, "IDeadTime")

    # low-level
    read_low_level_params = Cpt(EpicsSignal, "ReadLLParams")

    # Traces
    read_traces = Cpt(EpicsSignal, "ReadTraces")
    trace_modes = Cpt(EpicsSignal, "TraceModes", string=True)
    trace_times = Cpt(EpicsSignal, "TraceTimes")


class SaturnMCA(EpicsMCA, EpicsMCACallback):
    pass


class SaturnDXP(EpicsDXP, EpicsDXPLowLevel):
    pass


class Saturn(EpicsDXPBaseSystem):
    """DXP Saturn with 1 channel example"""

    dxp = Cpt(SaturnDXP, "dxp1:")
    mca = Cpt(SaturnMCA, "mca1")


class MercuryDXP(EpicsDXP, EpicsDXPLowLevel):
    pass


class Mercury1(EpicsDXPMultiElementSystem):
    """DXP Mercury with 1 channel example"""

    dxp = Cpt(MercuryDXP, "dxp1:")
    mca = Cpt(EpicsMCARecord, "mca1")


class SoftDXPTrigger(Device):
    """Simple soft trigger for DXP devices

    Parameters
    ----------
    count_signal : str, optional
        Signal to set acquisition time (default: 'preset_real_time')
    preset_mode : str, optional
        Default preset mode for the stage signals (default: 'Real time')
    mode_signal : str, optional
        Preset mode signal attribute (default 'preset_mode')
    stop_signal : str, optional
        Stop signal attribute (default 'stop_all')
    """

    count_time = Cpt(Signal, value=None, doc="bluesky count time")

    def __init__(
        self,
        *args,
        count_signal="preset_real_time",
        stop_signal="stop_all",
        mode_signal="preset_mode",
        preset_mode="Real time",
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._status = None
        self._count_signal = getattr(self, count_signal)

        stop_signal = getattr(self, stop_signal)
        self.stage_sigs[stop_signal] = 1

        mode_signal = getattr(self, mode_signal)
        self.stage_sigs[mode_signal] = preset_mode

    def stage(self):
        if self.count_time.get() is None:
            # remove count_time from the stage signals if count_time unset
            try:
                del self.stage_sigs[self._count_signal]
            except KeyError:
                pass
        else:
            self.stage_sigs[self._count_signal] = self.count_time.get()

        super().stage()
