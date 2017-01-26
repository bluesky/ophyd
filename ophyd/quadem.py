from collections import OrderedDict

from . import (EpicsSignalRO, EpicsSignal, Component as Cpt,
               DynamicDeviceComponent as DDCpt, Signal)
from .areadetector import (ADComponent as ADCpt, EpicsSignalWithRBV,
                           ImagePlugin, StatsPlugin, DetectorBase,
                           SingleTrigger)


def _current_fields(attr_base, field_base, range_, **kwargs):
    defn = OrderedDict()
    for i in range_:
        attr = '{attr}{i}'.format(attr=attr_base, i=i)
        suffix = '{field}{i}'.format(field=field_base, i=i)
        defn[attr] = (EpicsSignal, suffix, kwargs)

    return defn


class QuadEM(SingleTrigger, DetectorBase):
    # This is needed because ophyd verifies that it can see all
    # of the nodes in the asyn pipeline, however these IOCs do not
    # expose their port name via a PV, but nevertheless server as the
    # root node for the plugins.
    # Leaving this port_name here for compatibility
    port_name = Cpt(Signal, value='NSLS_EM')
    model = Cpt(EpicsSignalRO, 'Model')
    firmware = Cpt(EpicsSignalRO, 'Firmware')

    acquire_mode = Cpt(EpicsSignalWithRBV, 'AcquireMode')
    acquire = Cpt(EpicsSignal, 'Acquire')

    read_format = Cpt(EpicsSignalWithRBV, 'ReadFormat')
    em_range = Cpt(EpicsSignalWithRBV, 'Range')
    ping_pong = Cpt(EpicsSignalWithRBV, 'PingPong')

    integration_time = Cpt(EpicsSignalWithRBV, 'IntegrationTime')
    num_channels = Cpt(EpicsSignalWithRBV, 'NumChannels')
    geometry = Cpt(EpicsSignalWithRBV, 'Geometry')
    resolution = Cpt(EpicsSignalWithRBV, 'Resolution')

    bias_state = Cpt(EpicsSignalWithRBV, 'BiasState')
    bias_interlock = Cpt(EpicsSignalWithRBV, 'BiasInterlock')
    bias_voltage = Cpt(EpicsSignalWithRBV, 'BiasVoltage')
    hvs_readback = Cpt(EpicsSignalRO, 'HVSReadback')
    hvv_readback = Cpt(EpicsSignalRO, 'HVVReadback')
    hvi_readback = Cpt(EpicsSignalRO, 'HVIReadback')

    values_per_read = Cpt(EpicsSignalWithRBV, 'ValuesPerRead')
    sample_time = Cpt(EpicsSignalRO, 'SampleTime_RBV')  # yay for consistency
    averaging_time = Cpt(EpicsSignalWithRBV, 'AveragingTime')
    num_average = Cpt(EpicsSignalRO, 'NumAverage_RBV')
    num_averaged = Cpt(EpicsSignalRO, 'NumAveraged_RBV')
    num_acquire = Cpt(EpicsSignalWithRBV, 'NumAcquire')
    num_acquired = Cpt(EpicsSignalRO, 'NumAcquired')
    read_data = Cpt(EpicsSignalRO, 'ReadData')
    ring_overflows = Cpt(EpicsSignalRO, 'RingOverflows')
    trigger_mode = Cpt(EpicsSignal, 'TriggerMode')
    reset = Cpt(EpicsSignal, 'Reset')

    current_names = DDCpt(_current_fields('ch', 'CurrentName', range(1, 5),
                                          string=True))
    current_offsets = DDCpt(_current_fields('ch', 'CurrentOffset',
                                            range(1, 5)))
    current_offset_calcs = DDCpt(_current_fields('ch', 'ComputeCurrentOffset',
                                                 range(1, 5)))
    current_scales = DDCpt(_current_fields('ch', 'CurrentScale', range(1, 5)))

    position_offset_x = Cpt(EpicsSignal, 'PositionOffsetX')
    position_offset_y = Cpt(EpicsSignal, 'PositionOffsetY')

    position_offset_calc_x = Cpt(EpicsSignal, 'ComputePosOffsetX')
    position_offset_calc_y = Cpt(EpicsSignal, 'ComputePosOffsetY')

    position_scale_x = Cpt(EpicsSignal, 'PositionScaleX')
    position_scale_Y = Cpt(EpicsSignal, 'PositionScaleY')

    image = ADCpt(ImagePlugin, 'image1:')
    current1 = ADCpt(StatsPlugin, 'Current1:')
    current2 = ADCpt(StatsPlugin, 'Current2:')
    current3 = ADCpt(StatsPlugin, 'Current3:')
    current4 = ADCpt(StatsPlugin, 'Current4:')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.stage_sigs.update([('acquire', 0),  # if acquiring, stop
                                ('acquire_mode', 2)  # single mode
                                ])
        self._acquisition_signal = self.acquire

        self.configuration_attrs = ['integration_time', 'averaging_time']
        self.read_attrs = ['current1.mean_value', 'current2.mean_value',
                           'current3.mean_value', 'current4.mean_value']


class NSLS_EM(QuadEM):
    port_name = Cpt(Signal, value='NSLS_EM')


class TetrAMM(QuadEM):
    port_name = Cpt(Signal, value='TetrAMM')


class APS_EM(QuadEM):
    port_name = Cpt(Signal, value='APS_EM')

