from __future__ import print_function
import logging

from collections import OrderedDict

from .signal import (EpicsSignal, EpicsSignalRO)
from .device import Device
from .device import Component as C, DynamicDeviceComponent as DDC
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

    def __init__(self, prefix, *, read_attrs=None,
                 configuration_attrs=None, monitor_attrs=None, name=None,
                 parent=None, **kwargs):

        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs,
                         monitor_attrs=monitor_attrs,
                         name=name, parent=parent, **kwargs)


def add_rois(range_, **kwargs):
    '''Add one or more ROIs to an MCA instance

       Parameters:
       -----------
       range_ : sequence of ints
           Must be be in the set [0,31]

       By default, an EpicsMCA is initialized with all 32 rois.
       These provide the following Components as EpicsSignals (N=[0,31]):
       EpicsMCA.rois.roiN.(label,count,net_count,preset_cnt, is_preset, bkgnd_chans,
       hi_chan, lo_chan)
       '''
    defn = OrderedDict()

    for roi in range_:
        if not (0 <= roi < 32):
            raise ValueError('roi must be in the set [0,31]')

        attr = 'roi{}'.format(roi)
        defn[attr] = (ROI, '.R{}'.format(roi), kwargs)

    return defn


class EpicsMCA(Device):
    '''SynApps MCA Record interface'''

    start = C(EpicsSignal, 'Start')
    erase_start = C(EpicsSignal, 'EraseStart', trigger_value=1)

    _stop = C(EpicsSignal, '.STOP')
    preset_real_time = C(EpicsSignal, '.ERTM', write_pv='.PRTM')
    preset_live_time = C(EpicsSignal, '.ELTM', write_pv='.PLTM')
    spectrum = C(EpicsSignalRO, '.VAL')
    background = C(EpicsSignalRO, '.BG')
    mode = C(EpicsSignal, '.MODE', string=True)

    rois = DDC(add_rois(range(0,31)))

    def __init__(self, prefix, *, read_attrs=None,
                 configuration_attrs=None, monitor_attrs=None, name=None,
                 parent=None, **kwargs):

        default_read_attrs = ['spectrum', 'preset_real_time']
        default_configuration_attrs = ['preset_real_time']

        if read_attrs is None:
            read_attrs = default_read_attrs

        if configuration_attrs is None:
            configuration_attrs = default_configuration_attrs

        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs,
                         monitor_attrs=monitor_attrs,
                         name=name, parent=parent, **kwargs)

    def stop(self):
        self._stop.put(1)

    def stage(self):
        '''Stage the MCA for data acquisition'''
        self._old_mode = self.mode.get()
        self.mode.put(0)

    def unstage(self):
        '''Unstage from acquisition; restore the pre-scan mode'''
        self.mode.put(self._old_mode)


class EpicsDXP(Device):
    preset_mode = C(EpicsSignal, 'PresetMode', string=True)

    # NOTE: all SignalWithRBV are "lazy=True"
    # Trigger Filter PVs
    trigger_peaking_time = C(SignalWithRBV, 'TriggerPeakingTime')
    trigger_threshold = C(SignalWithRBV, 'TriggerThreshold')
    trigger_gap_time = C(SignalWithRBV, 'TriggerGapTime')

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

    # Misc PVs
    preamp_gain = C(SignalWithRBV, 'PreampGain')
    detector_polarity = C(SignalWithRBV, 'DetectorPolarity')
    reset_delay = C(SignalWithRBV, 'ResetDelay')
    decay_time = C(SignalWithRBV, 'DecayTime')
    max_energy = C(SignalWithRBV, 'MaxEnergy')
    adc_percent_rule = C(SignalWithRBV, 'ADCPercentRule')

    # read-only diagnostics
    triggers = C(EpicsSignalRO, 'Triggers', lazy=True)
    events = C(EpicsSignalRO, 'Events', lazy=True)
    overflows = C(EpicsSignalRO, 'Overflows', lazy=True)
    underflows = C(EpicsSignalRO, 'Underflows', lazy=True)
    input_count_rate = C(EpicsSignalRO, 'InputCountRate', lazy=True)
    output_count_rate = C(EpicsSignalRO, 'OutputCountRate', lazy=True)

    def __init__(self, prefix, *, read_attrs=None,
                 configuration_attrs=None, monitor_attrs=None, name=None,
                 parent=None, **kwargs):

        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs,
                         monitor_attrs=monitor_attrs,
                         name=name, parent=parent, **kwargs)
