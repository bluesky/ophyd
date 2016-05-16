
import logging

from collections import (OrderedDict, namedtuple)

from .signal import (EpicsSignal, EpicsSignalRO)
from .device import Device
from .device import Component as C, DynamicDeviceComponent as DDC
from .areadetector import EpicsSignalWithRBV as SignalWithRBV
from .device import Staged


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

       Parameters:
       -----------
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
    stop_signal = C(EpicsSignal, '.STOP')
    preset_real_time = C(EpicsSignal, '.PRTM')
    preset_live_time = C(EpicsSignal, '.PLTM')
    elapsed_real_time = C(EpicsSignalRO, '.ERTM')
    elapsed_live_time = C(EpicsSignalRO, '.ELTM')

    spectrum = C(EpicsSignalRO, '.VAL')
    background = C(EpicsSignalRO, '.BG')
    mode = C(EpicsSignal, '.MODE', string=True)

    rois = DDC(add_rois(range(0, 32)))

    def __init__(self, prefix, *, read_attrs=None, configuration_attrs=None,
                 name=None, parent=None, **kwargs):

        if read_attrs is None:
            read_attrs = ['spectrum', 'preset_real_time', 'elapsed_real_time']

        if configuration_attrs is None:
            configuration_attrs = ['preset_real_time']

        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs,
                         name=name, parent=parent, **kwargs)

        # could arguably be made a configuration_attr instead...
        self.stage_sigs[self.mode] = 'PHA'

    def stop(self):
        self.stop_signal.put(1)


class EpicsMCA(EpicsMCARecord):
    '''mca records with extras from mca.db'''
    start = C(EpicsSignal, 'Start')
    stop_signal = C(EpicsSignal, 'Stop')
    erase = C(EpicsSignal, 'Erase')
    erase_start = C(EpicsSignal, 'EraseStart', trigger_value=1)

    check_acquiring = C(EpicsSignal, 'CheckACQG')
    client_wait = C(EpicsSignal, 'ClientWait')
    enable_wait = C(EpicsSignal, 'EnableWait')
    read = C(EpicsSignal, 'Read')
    set_client_wait = C(EpicsSignal, 'SetClientWait')
    status = C(EpicsSignal, 'Status')
    when_acq_stops = C(EpicsSignal, 'WhenAcqStops')
    why1 = C(EpicsSignal, 'Why1')
    why2 = C(EpicsSignal, 'Why2')
    why3 = C(EpicsSignal, 'Why3')
    why4 = C(EpicsSignal, 'Why4')


class EpicsMCAReadNotify(EpicsMCARecord):
    '''mca record with extras from mcaReadNotify.db'''
    start = C(EpicsSignal, 'Start')
    stop_signal = C(EpicsSignal, 'Stop')
    erase = C(EpicsSignal, 'Erase')
    erase_start = C(EpicsSignal, 'EraseStart', trigger_value=1)

    check_acquiring = C(EpicsSignal, 'CheckACQG')
    client_wait = C(EpicsSignal, 'ClientWait')
    enable_wait = C(EpicsSignal, 'EnableWait')
    read = C(EpicsSignal, 'Read')
    set_client_wait = C(EpicsSignal, 'SetClientWait')
    status = C(EpicsSignal, 'Status')


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


class EpicsDXPSystem(Device):
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


class SaturnMCA(EpicsMCA, EpicsMCACallback):
    pass


class SaturnDXP(EpicsDXP, EpicsDXPLowLevel):
    pass


class Saturn(EpicsDXPSystem):
    '''DXP Saturn with 1 channel example'''
    dxp = C(SaturnDXP, 'dxp1:')
    mca = C(SaturnMCA, 'mca1')


class MercuryDXP(EpicsDXP, EpicsDXPLowLevel):
    pass


class Mercury1(EpicsDXPSystem):
    '''DXP Mercury with 1 channel example'''
    dxp = C(MercuryDXP, 'dxp1:')
    mca = C(EpicsMCARecord, 'mca1')

