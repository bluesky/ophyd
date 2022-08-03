#!/usr/bin/env python3
from caproto.server import (
    PVGroup,
    SubGroup,
    get_pv_pair_wrapper,
    ioc_arg_parser,
    pvproperty,
    run,
)

pvproperty_with_rbv = get_pv_pair_wrapper(setpoint_suffix="", readback_suffix="_RBV")
unknown = int


class MCAROIGroup(PVGroup):
    label = pvproperty(value="label", name="NM")
    count = pvproperty(value=1, name="", read_only=True)
    net_count = pvproperty(name="N", dtype=unknown, read_only=True)
    preset_count = pvproperty(name="P", dtype=unknown)
    is_preset = pvproperty(name="IP", dtype=unknown)
    bkgnd_chans = pvproperty(name="BG", dtype=unknown)
    hi_chan = pvproperty(name="HI", dtype=unknown)
    lo_chan = pvproperty(name="LO", dtype=unknown)


class EpicsMCAGroup(PVGroup):
    stop_signal = pvproperty(name="Stop", dtype=unknown)
    preset_real_time = pvproperty(name=".PRTM", dtype=unknown)
    preset_live_time = pvproperty(name=".PLTM", dtype=unknown)
    elapsed_real_time = pvproperty(name=".ERTM", dtype=unknown, read_only=True)
    elapsed_live_time = pvproperty(name=".ELTM", dtype=unknown, read_only=True)
    spectrum = pvproperty(name="", dtype=float, read_only=True)
    background = pvproperty(name=".BG", dtype=unknown, read_only=True)
    mode = pvproperty(value="List", name=".MODE", dtype=str)

    class RoisGroup(PVGroup):
        roi0 = SubGroup(MCAROIGroup, prefix=".R0")
        roi1 = SubGroup(MCAROIGroup, prefix=".R1")
        roi2 = SubGroup(MCAROIGroup, prefix=".R2")
        roi3 = SubGroup(MCAROIGroup, prefix=".R3")
        roi4 = SubGroup(MCAROIGroup, prefix=".R4")
        roi5 = SubGroup(MCAROIGroup, prefix=".R5")
        roi6 = SubGroup(MCAROIGroup, prefix=".R6")
        roi7 = SubGroup(MCAROIGroup, prefix=".R7")
        roi8 = SubGroup(MCAROIGroup, prefix=".R8")
        roi9 = SubGroup(MCAROIGroup, prefix=".R9")
        roi10 = SubGroup(MCAROIGroup, prefix=".R10")
        roi11 = SubGroup(MCAROIGroup, prefix=".R11")
        roi12 = SubGroup(MCAROIGroup, prefix=".R12")
        roi13 = SubGroup(MCAROIGroup, prefix=".R13")
        roi14 = SubGroup(MCAROIGroup, prefix=".R14")
        roi15 = SubGroup(MCAROIGroup, prefix=".R15")
        roi16 = SubGroup(MCAROIGroup, prefix=".R16")
        roi17 = SubGroup(MCAROIGroup, prefix=".R17")
        roi18 = SubGroup(MCAROIGroup, prefix=".R18")
        roi19 = SubGroup(MCAROIGroup, prefix=".R19")
        roi20 = SubGroup(MCAROIGroup, prefix=".R20")
        roi21 = SubGroup(MCAROIGroup, prefix=".R21")
        roi22 = SubGroup(MCAROIGroup, prefix=".R22")
        roi23 = SubGroup(MCAROIGroup, prefix=".R23")
        roi24 = SubGroup(MCAROIGroup, prefix=".R24")
        roi25 = SubGroup(MCAROIGroup, prefix=".R25")
        roi26 = SubGroup(MCAROIGroup, prefix=".R26")
        roi27 = SubGroup(MCAROIGroup, prefix=".R27")
        roi28 = SubGroup(MCAROIGroup, prefix=".R28")
        roi29 = SubGroup(MCAROIGroup, prefix=".R29")
        roi30 = SubGroup(MCAROIGroup, prefix=".R30")
        roi31 = SubGroup(MCAROIGroup, prefix=".R31")

    rois = SubGroup(RoisGroup, prefix="")

    start = pvproperty(name="Start", dtype=unknown)
    erase = pvproperty(name="Erase", dtype=unknown)
    erase_start = pvproperty(name="EraseStart", dtype=unknown)
    check_acquiring = pvproperty(name="CheckACQG", dtype=unknown)
    client_wait = pvproperty(name="ClientWait", dtype=unknown)
    enable_wait = pvproperty(name="EnableWait", dtype=unknown)
    force_read = pvproperty(name="Read", dtype=unknown)
    set_client_wait = pvproperty(name="SetClientWait", dtype=unknown)
    status = pvproperty(name="Status", dtype=unknown)
    when_acq_stops = pvproperty(name="WhenAcqStops", dtype=unknown)
    why1 = pvproperty(name="Why1", dtype=unknown)
    why2 = pvproperty(name="Why2", dtype=unknown)
    why3 = pvproperty(name="Why3", dtype=unknown)
    why4 = pvproperty(name="Why4", dtype=unknown)


class EpicsDXPGroup(PVGroup):
    preset_mode = pvproperty_with_rbv(value="Live time", name="PresetMode", dtype=str)
    live_time_output = pvproperty_with_rbv(
        value="livetimeoutput", name="LiveTimeOutput", dtype=str
    )
    elapsed_live_time = pvproperty(name="ElapsedLiveTime", dtype=unknown)
    elapsed_real_time = pvproperty(name="ElapsedRealTime", dtype=unknown)
    elapsed_trigger_live_time = pvproperty(name="ElapsedTriggerLiveTime", dtype=unknown)
    trigger_peaking_time = pvproperty_with_rbv(name="TriggerPeakingTime", dtype=unknown)
    trigger_threshold = pvproperty_with_rbv(name="TriggerThreshold", dtype=unknown)
    trigger_gap_time = pvproperty_with_rbv(name="TriggerGapTime", dtype=unknown)
    trigger_output = pvproperty_with_rbv(
        value="trigger_output", name="TriggerOutput", dtype=str
    )
    max_width = pvproperty_with_rbv(name="MaxWidth", dtype=unknown)
    peaking_time = pvproperty_with_rbv(name="PeakingTime", dtype=unknown)
    energy_threshold = pvproperty_with_rbv(name="EnergyThreshold", dtype=unknown)
    gap_time = pvproperty_with_rbv(name="GapTime", dtype=unknown)
    baseline_cut_percent = pvproperty_with_rbv(name="BaselineCutPercent", dtype=unknown)
    baseline_cut_enable = pvproperty_with_rbv(name="BaselineCutEnable", dtype=unknown)
    baseline_filter_length = pvproperty_with_rbv(
        name="BaselineFilterLength", dtype=unknown
    )
    baseline_threshold = pvproperty_with_rbv(name="BaselineThreshold", dtype=unknown)
    baseline_energy_array = pvproperty(name="BaselineEnergyArray", dtype=unknown)
    baseline_histogram = pvproperty(name="BaselineHistogram", dtype=unknown)
    preamp_gain = pvproperty_with_rbv(name="PreampGain", dtype=unknown)
    detector_polarity = pvproperty_with_rbv(name="DetectorPolarity", dtype=unknown)
    reset_delay = pvproperty_with_rbv(name="ResetDelay", dtype=unknown)
    decay_time = pvproperty_with_rbv(name="DecayTime", dtype=unknown)
    max_energy = pvproperty_with_rbv(name="MaxEnergy", dtype=unknown)
    adc_percent_rule = pvproperty_with_rbv(name="ADCPercentRule", dtype=unknown)
    triggers = pvproperty(name="Triggers", dtype=unknown, read_only=True)
    events = pvproperty(name="Events", dtype=unknown, read_only=True)
    overflows = pvproperty(name="Overflows", dtype=unknown, read_only=True)
    underflows = pvproperty(name="Underflows", dtype=unknown, read_only=True)
    input_count_rate = pvproperty(name="InputCountRate", dtype=unknown, read_only=True)
    output_count_rate = pvproperty(
        name="OutputCountRate", dtype=unknown, read_only=True
    )
    mca_bin_width = pvproperty(name="MCABinWidth_RBV", dtype=unknown, read_only=True)
    calibration_energy = pvproperty(
        name="CalibrationEnergy_RBV", dtype=unknown, read_only=True
    )
    current_pixel = pvproperty(name="CurrentPixel", dtype=unknown)
    dynamic_range = pvproperty(name="DynamicRange_RBV", dtype=unknown, read_only=True)
    preset_events = pvproperty_with_rbv(name="PresetEvents", dtype=unknown)
    preset_triggers = pvproperty_with_rbv(name="PresetTriggers", dtype=unknown)
    trace_data = pvproperty(name="TraceData", dtype=unknown)
    trace_mode = pvproperty_with_rbv(value="Mode", name="TraceMode", dtype=str)
    trace_time_array = pvproperty(name="TraceTimeArray", dtype=unknown)
    trace_time = pvproperty_with_rbv(name="TraceTime", dtype=unknown)


class McaDxpIOC(PVGroup):
    mca = SubGroup(EpicsMCAGroup, prefix="mca")
    dxp = SubGroup(EpicsDXPGroup, prefix="dxp:")


if __name__ == "__main__":
    ioc_options, run_options = ioc_arg_parser(
        default_prefix="test_mca:", desc="ophyd.tests.test_mca test IOC"
    )
    ioc = McaDxpIOC(**ioc_options)
    run(ioc.pvdb, **run_options)
