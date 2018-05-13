
import logging

from collections import OrderedDict

from .status import DeviceStatus
from .signal import (Signal, EpicsSignal, EpicsSignalRO)
from .device import (Device, Component as C, DynamicDeviceComponent as DDC,
                     Staged, BlueskyInterface, ALL_COMPONENTS, Kind)
from .areadetector import EpicsSignalWithRBV as SignalWithRBV


logger = logging.getLogger(__name__)


class ROI(Device):

    # 'name' is not an allowed attribute
    label = C(EpicsSignal, 'NM', lazy=True)
    count = C(EpicsSignalRO, '', lazy=True)
    net_count = C(EpicsSignalRO, 'N', lazy=True)
    preset_count = C(EpicsSignal, 'P', lazy=True)
    is_preset = C(EpicsSignal, 'IP', lazy=True)
    bkgnd_chans = C(EpicsSignal, 'BG', lazy=True)
    hi_chan = C(EpicsSignal, 'HI', lazy=True)
    lo_chan = C(EpicsSignal, 'LO', lazy=True)

    def __init__(self, prefix, *, read_attrs=None, configuration_attrs=None,
                 name=None, parent=None, **kwargs):

        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs,
                         name=name, parent=parent, **kwargs)


def add_rois(range_, **kwargs):
    '''Add one or more ROIs to an MCA instance

       Parameters
       ----------
       range_ : sequence of ints
           Must be be in the set [0,31]

       By default, an EpicsMCA is initialized with all 32 rois.
       These provide the following Components as EpicsSignals (N=[0,31]):
       EpicsMCA.rois.roiN.(label,count,net_count,preset_cnt, is_preset,
       bkgnd_chans, hi_chan, lo_chan)
       '''
    defn = OrderedDict()

    for roi in range_:
        if not (0 <= roi < 32):
            raise ValueError('roi must be in the set [0,31]')

        attr = 'roi{}'.format(roi)
        defn[attr] = (ROI, '.R{}'.format(roi), kwargs)

    return defn


class EpicsMCARecord(Device):
    '''SynApps MCA Record interface'''
    stop_signal = C(EpicsSignal, '.STOP', kind='omitted')
    preset_real_time = C(EpicsSignal, '.PRTM', kind=Kind.config | Kind.normal)
    preset_live_time = C(EpicsSignal, '.PLTM', kind='omitted')
    elapsed_real_time = C(EpicsSignalRO, '.ERTM')
    elapsed_live_time = C(EpicsSignalRO, '.ELTM', kind='omitted')

    spectrum = C(EpicsSignalRO, '.VAL')
    background = C(EpicsSignalRO, '.BG', kind='omitted')
    mode = C(EpicsSignal, '.MODE', string=True, kind='omitted')

    rois = DDC(add_rois(range(0, 32), kind='omitted'), kind='omitted')

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # could arguably be made a configuration_attr instead...
        self.stage_sigs['mode'] = 'PHA'

    def stop(self, *, success=False):
        self.stop_signal.put(1)


class EpicsMCA(EpicsMCARecord):
    '''mca records with extras from mca.db'''
    start = C(EpicsSignal, 'Start', kind='omitted')
    stop_signal = C(EpicsSignal, 'Stop', kind='omitted')
    erase = C(EpicsSignal, 'Erase', kind='omitted')
    erase_start = C(EpicsSignal, 'EraseStart', trigger_value=1, kind='omitted')

    check_acquiring = C(EpicsSignal, 'CheckACQG', kind='omitted')
    client_wait = C(EpicsSignal, 'ClientWait', kind='omitted')
    enable_wait = C(EpicsSignal, 'EnableWait', kind='omitted')
    force_read = C(EpicsSignal, 'Read', kind='omitted')
    set_client_wait = C(EpicsSignal, 'SetClientWait', kind='omitted')
    status = C(EpicsSignal, 'Status', kind='omitted')
    when_acq_stops = C(EpicsSignal, 'WhenAcqStops', kind='omitted')
    why1 = C(EpicsSignal, 'Why1', kind='omitted')
    why2 = C(EpicsSignal, 'Why2', kind='omitted')
    why3 = C(EpicsSignal, 'Why3', kind='omitted')
    why4 = C(EpicsSignal, 'Why4', kind='omitted')


class EpicsMCAReadNotify(EpicsMCARecord):
    '''mca record with extras from mcaReadNotify.db'''
    start = C(EpicsSignal, 'Start', kind='omitted')
    stop_signal = C(EpicsSignal, 'Stop', kind='omitted')
    erase = C(EpicsSignal, 'Erase', kind='omitted')
    erase_start = C(EpicsSignal, 'EraseStart', trigger_value=1, kind='omitted')

    check_acquiring = C(EpicsSignal, 'CheckACQG', kind='omitted')
    client_wait = C(EpicsSignal, 'ClientWait', kind='omitted')
    enable_wait = C(EpicsSignal, 'EnableWait', kind='omitted')
    force_read = C(EpicsSignal, 'Read', kind='omitted')
    set_client_wait = C(EpicsSignal, 'SetClientWait', kind='omitted')
    status = C(EpicsSignal, 'Status', kind='omitted')


class EpicsMCACallback(Device):
    '''Callback-related signals for MCA devices'''
    read_callback = C(EpicsSignal, 'ReadCallback')
    read_data_once = C(EpicsSignal, 'ReadDataOnce')
    read_status_once = C(EpicsSignal, 'ReadStatusOnce')
    collect_data = C(EpicsSignal, 'CollectData')


class EpicsDXP(Device):
    '''All high-level DXP parameters for each channel'''
    preset_mode = C(EpicsSignal, 'PresetMode', string=True)

    live_time_output = C(SignalWithRBV, 'LiveTimeOutput', string=True)
    elapsed_live_time = C(EpicsSignal, 'ElapsedLiveTime')
    elapsed_real_time = C(EpicsSignal, 'ElapsedRealTime')
    elapsed_trigger_live_time = C(EpicsSignal, 'ElapsedTriggerLiveTime')

    # Trigger Filter PVs
    trigger_peaking_time = C(SignalWithRBV, 'TriggerPeakingTime')
    trigger_threshold = C(SignalWithRBV, 'TriggerThreshold')
    trigger_gap_time = C(SignalWithRBV, 'TriggerGapTime')
    trigger_output = C(SignalWithRBV, 'TriggerOutput', string=True)
    max_width = C(SignalWithRBV, 'MaxWidth')

    # Energy Filter PVs
    peaking_time = C(SignalWithRBV, 'PeakingTime')
    energy_threshold = C(SignalWithRBV, 'EnergyThreshold')
    gap_time = C(SignalWithRBV, 'GapTime')

    # Baseline PVs
    baseline_cut_percent = C(SignalWithRBV, 'BaselineCutPercent')
    baseline_cut_enable = C(SignalWithRBV, 'BaselineCutEnable')
    baseline_filter_length = C(SignalWithRBV, 'BaselineFilterLength')
    baseline_threshold = C(SignalWithRBV, 'BaselineThreshold')
    baseline_energy_array = C(EpicsSignal, 'BaselineEnergyArray')
    baseline_histogram = C(EpicsSignal, 'BaselineHistogram')
    baseline_threshold = C(SignalWithRBV, 'BaselineThreshold')

    # Misc PVs
    preamp_gain = C(SignalWithRBV, 'PreampGain')
    detector_polarity = C(SignalWithRBV, 'DetectorPolarity')
    reset_delay = C(SignalWithRBV, 'ResetDelay')
    decay_time = C(SignalWithRBV, 'DecayTime')
    max_energy = C(SignalWithRBV, 'MaxEnergy')
    adc_percent_rule = C(SignalWithRBV, 'ADCPercentRule')
    max_width = C(SignalWithRBV, 'MaxWidth')

    # read-only diagnostics
    triggers = C(EpicsSignalRO, 'Triggers', lazy=True)
    events = C(EpicsSignalRO, 'Events', lazy=True)
    overflows = C(EpicsSignalRO, 'Overflows', lazy=True)
    underflows = C(EpicsSignalRO, 'Underflows', lazy=True)
    input_count_rate = C(EpicsSignalRO, 'InputCountRate', lazy=True)
    output_count_rate = C(EpicsSignalRO, 'OutputCountRate', lazy=True)

    mca_bin_width = C(EpicsSignalRO, 'MCABinWidth_RBV')
    calibration_energy = C(EpicsSignalRO, 'CalibrationEnergy_RBV')
    current_pixel = C(EpicsSignal, 'CurrentPixel')
    dynamic_range = C(EpicsSignalRO, 'DynamicRange_RBV')

    # Preset options
    preset_events = C(SignalWithRBV, 'PresetEvents')
    preset_mode = C(SignalWithRBV, 'PresetMode', string=True)
    preset_triggers = C(SignalWithRBV, 'PresetTriggers')

    # Trace options
    trace_data = C(EpicsSignal, 'TraceData')
    trace_mode = C(SignalWithRBV, 'TraceMode', string=True)
    trace_time_array = C(EpicsSignal, 'TraceTimeArray')
    trace_time = C(SignalWithRBV, 'TraceTime')


class EpicsDXPLowLevelParameter(Device):
    param_name = C(EpicsSignal, 'Name')
    value = C(SignalWithRBV, 'Val')


class EpicsDXPLowLevel(Device):
    num_low_level_params = C(EpicsSignal, 'NumLLParams')
    read_low_level_params = C(EpicsSignal, 'ReadLLParams')

    parameter_prefix = 'LL{}'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._parameter_cache = {}

    def get_low_level_parameter(self, index):
        '''Get a DXP low level parameter

        Parameters
        ----------
        index : int
            In the range of [0, 229]

        Returns
        -------
        param : EpicsDXPLowLevelParameter
        '''
        try:
            return self._parameter_cache[index]
        except KeyError:
            pass

        prefix = '{}{}'.format(self.prefix, self.parameter_prefix)
        name = '{}_param{}'.format(self.name, index)
        param = EpicsDXPLowLevelParameter(prefix, name=name)
        self._parameter_cache[index] = param
        return param


class EpicsDXPMapping(Device):
    apply = C(EpicsSignal, 'Apply')
    auto_apply = C(SignalWithRBV, 'AutoApply')
    auto_pixels_per_buffer = C(SignalWithRBV, 'AutoPixelsPerBuffer')
    buffer_size = C(EpicsSignalRO, 'BufferSize_RBV')
    collect_mode = C(SignalWithRBV, 'CollectMode')
    ignore_gate = C(SignalWithRBV, 'IgnoreGate')
    input_logic_polarity = C(SignalWithRBV, 'InputLogicPolarity')
    list_mode = C(SignalWithRBV, 'ListMode')
    mbytes_read = C(EpicsSignalRO, 'MBytesRead_RBV')
    next_pixel = C(EpicsSignal, 'NextPixel')
    pixel_advance_mode = C(SignalWithRBV, 'PixelAdvanceMode')
    pixels_per_buffer = C(SignalWithRBV, 'PixelsPerBuffer')
    pixels_per_run = C(SignalWithRBV, 'PixelsPerRun')
    read_rate = C(EpicsSignalRO, 'ReadRate_RBV')
    sync_count = C(SignalWithRBV, 'SyncCount')


class EpicsDXPBaseSystem(Device):
    channel_advance = C(EpicsSignal, 'ChannelAdvance')
    client_wait = C(EpicsSignal, 'ClientWait')
    dwell = C(EpicsSignal, 'Dwell')
    max_scas = C(EpicsSignal, 'MaxSCAs')
    num_scas = C(SignalWithRBV, 'NumSCAs')
    poll_time = C(SignalWithRBV, 'PollTime')
    prescale = C(EpicsSignal, 'Prescale')
    save_system = C(SignalWithRBV, 'SaveSystem')
    save_system_file = C(EpicsSignal, 'SaveSystemFile')
    set_client_wait = C(EpicsSignal, 'SetClientWait')


class EpicsDXPMultiElementSystem(EpicsDXPBaseSystem):
    # Preset info
    preset_events = C(EpicsSignal, 'PresetEvents')
    preset_live_time = C(EpicsSignal, 'PresetLive')
    preset_real_time = C(EpicsSignal, 'PresetReal')
    preset_mode = C(EpicsSignal, 'PresetMode', string=True)
    preset_triggers = C(EpicsSignal, 'PresetTriggers')

    # Acquisition
    erase_all = C(EpicsSignal, 'EraseAll')
    erase_start = C(EpicsSignal, 'EraseStart', trigger_value=1)
    start_all = C(EpicsSignal, 'StartAll')
    stop_all = C(EpicsSignal, 'StopAll')

    # Status
    set_acquire_busy = C(EpicsSignal, 'SetAcquireBusy')
    acquire_busy = C(EpicsSignal, 'AcquireBusy')
    status_all = C(EpicsSignal, 'StatusAll')
    status_all_once = C(EpicsSignal, 'StatusAllOnce')
    acquiring = C(EpicsSignal, 'Acquiring')

    # Reading
    read_baseline_histograms = C(EpicsSignal, 'ReadBaselineHistograms')
    read_all = C(EpicsSignal, 'ReadAll')
    read_all_once = C(EpicsSignal, 'ReadAllOnce')

    # As a debugging note, if snl_connected is not '1', your IOC is
    # misconfigured:
    snl_connected = C(EpicsSignal, 'SNL_Connected')

    # Copying to individual elements
    copy_adcp_ercent_rule = C(EpicsSignal, 'CopyADCPercentRule')
    copy_baseline_cut_enable = C(EpicsSignal, 'CopyBaselineCutEnable')
    copy_baseline_cut_percent = C(EpicsSignal, 'CopyBaselineCutPercent')
    copy_baseline_filter_length = C(EpicsSignal, 'CopyBaselineFilterLength')
    copy_baseline_threshold = C(EpicsSignal, 'CopyBaselineThreshold')
    copy_decay_time = C(EpicsSignal, 'CopyDecayTime')
    copy_detector_polarity = C(EpicsSignal, 'CopyDetectorPolarity')
    copy_energy_threshold = C(EpicsSignal, 'CopyEnergyThreshold')
    copy_gap_time = C(EpicsSignal, 'CopyGapTime')
    copy_max_energy = C(EpicsSignal, 'CopyMaxEnergy')
    copy_max_width = C(EpicsSignal, 'CopyMaxWidth')
    copy_peaking_time = C(EpicsSignal, 'CopyPeakingTime')
    copy_preamp_gain = C(EpicsSignal, 'CopyPreampGain')
    copy_roic_hannel = C(EpicsSignal, 'CopyROIChannel')
    copy_roie_nergy = C(EpicsSignal, 'CopyROIEnergy')
    copy_roi_sca = C(EpicsSignal, 'CopyROI_SCA')
    copy_reset_delay = C(EpicsSignal, 'CopyResetDelay')
    copy_trigger_gap_time = C(EpicsSignal, 'CopyTriggerGapTime')
    copy_trigger_peaking_time = C(EpicsSignal, 'CopyTriggerPeakingTime')
    copy_trigger_threshold = C(EpicsSignal, 'CopyTriggerThreshold')

    # do_* executes the process:
    do_read_all = C(EpicsSignal, 'DoReadAll')
    do_read_baseline_histograms = C(EpicsSignal, 'DoReadBaselineHistograms')
    do_read_traces = C(EpicsSignal, 'DoReadTraces')
    do_status_all = C(EpicsSignal, 'DoStatusAll')

    # Time
    dead_time = C(EpicsSignal, 'DeadTime')
    elapsed_live = C(EpicsSignal, 'ElapsedLive')
    elapsed_real = C(EpicsSignal, 'ElapsedReal')
    idead_time = C(EpicsSignal, 'IDeadTime')

    # low-level
    read_low_level_params = C(EpicsSignal, 'ReadLLParams')

    # Traces
    read_traces = C(EpicsSignal, 'ReadTraces')
    trace_modes = C(EpicsSignal, 'TraceModes', string=True)
    trace_times = C(EpicsSignal, 'TraceTimes')


class SaturnMCA(EpicsMCA, EpicsMCACallback):
    pass


class SaturnDXP(EpicsDXP, EpicsDXPLowLevel):
    pass


class Saturn(EpicsDXPBaseSystem):
    '''DXP Saturn with 1 channel example'''
    dxp = C(SaturnDXP, 'dxp1:')
    mca = C(SaturnMCA, 'mca1')


class MercuryDXP(EpicsDXP, EpicsDXPLowLevel):
    pass


class Mercury1(EpicsDXPMultiElementSystem):
    '''DXP Mercury with 1 channel example'''
    dxp = C(MercuryDXP, 'dxp1:')
    mca = C(EpicsMCARecord, 'mca1')


class SoftDXPTrigger(BlueskyInterface):
    '''Simple soft trigger for DXP devices

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
    '''

    count_time = C(Signal, value=None, doc='bluesky count time')

    def __init__(self, *args, count_signal='preset_real_time',
                 stop_signal='stop_all', mode_signal='preset_mode',
                 preset_mode='Real time',
                 **kwargs):
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
