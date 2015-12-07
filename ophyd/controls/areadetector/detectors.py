# vi: ts=4 sw=4
'''
:mod:`ophyd.control.areadetector` - areaDetector
================================================

.. module:: ophyd.control.areadetector.detector
 :synopsis:  `areaDetector`_ detector/camera abstractions

.. _areaDetector: http://cars.uchicago.edu/software/epics/areaDetector.html
'''

from __future__ import print_function
import logging

from ...utils import enum
from .base import (ADBase, ADComponent as ADC, ad_group, ADEpicsSignal)
from ..signal import (EpicsSignalRO, EpicsSignal)
from ..device import DynamicDeviceComponent as DDC

logger = logging.getLogger(__name__)


__all__ = ['AreaDetector',
           'Andor3Detector',
           'AndorDetector',
           'BrukerDetector',
           'FirewireLinDetector',
           'FirewireWinDetector',
           'LightFieldDetector',
           'Mar345Detector',
           'MarCCDDetector',
           'PerkinElmerDetector',
           'PilatusDetector',
           'PixiradDetector',
           'PointGreyDetector',
           'ProsilicaDetector',
           'PSLDetector',
           'PvcamDetector',
           'RoperDetector',
           'SimDetector',
           'URLDetector',
           ]


class AreaDetector(ADBase):
    _html_docs = ['areaDetectorDoc.html']
    _sep = 'cam1:'
    ImageMode = enum(SINGLE=0, MULTIPLE=1, CONTINUOUS=2)

    acquire = ADC(ADEpicsSignal, 'Acquire')
    acquire_period = ADC(ADEpicsSignal, 'AcquirePeriod')
    acquire_time = ADC(ADEpicsSignal, 'AcquireTime')

    array_callbacks = ADC(ADEpicsSignal, 'ArrayCallbacks')
    array_size = DDC(ad_group(EpicsSignalRO,
                              (('array_size_x', 'ArraySizeX_RBV'),
                               ('array_size_y', 'ArraySizeY_RBV'),
                               ('array_size_z', 'ArraySizeZ_RBV'))),
                     doc='Size of the array in the XYZ dimensions')

    array_size_bytes = ADC(EpicsSignalRO, 'ArraySize_RBV')
    bin_x = ADC(ADEpicsSignal, 'BinX')
    bin_y = ADC(ADEpicsSignal, 'BinY')
    color_mode = ADC(ADEpicsSignal, 'ColorMode')
    data_type = ADC(ADEpicsSignal, 'DataType')
    detector_state = ADC(EpicsSignalRO, 'DetectorState_RBV')
    frame_type = ADC(ADEpicsSignal, 'FrameType')
    gain = ADC(ADEpicsSignal, 'Gain')

    image_mode = ADC(ADEpicsSignal, 'ImageMode')
    manufacturer = ADC(EpicsSignalRO, 'Manufacturer_RBV')

    max_size = DDC(ad_group(EpicsSignalRO,
                            (('max_size_x', 'MaxSizeX_RBV'),
                             ('max_size_y', 'MaxSizeY_RBV'))),
                   doc='Maximum sensor size in the XY directions')

    min_x = ADC(ADEpicsSignal, 'MinX')
    min_y = ADC(ADEpicsSignal, 'MinY')
    model = ADC(EpicsSignalRO, 'Model_RBV')

    num_exposures = ADC(ADEpicsSignal, 'NumExposures')
    num_exposures_counter = ADC(EpicsSignalRO, 'NumExposuresCounter_RBV')
    num_images = ADC(ADEpicsSignal, 'NumImages')
    num_images_counter = ADC(EpicsSignalRO, 'NumImagesCounter_RBV')

    read_status = ADC(EpicsSignal, 'ReadStatus')
    reverse = DDC(ad_group(ADEpicsSignal,
                           (('reverse_x', 'ReverseX'),
                            ('reverse_y', 'ReverseY'))
                           ))

    shutter_close_delay = ADC(ADEpicsSignal, 'ShutterCloseDelay')
    shutter_close_epics = ADC(EpicsSignal, 'ShutterCloseEPICS')
    shutter_control = ADC(ADEpicsSignal, 'ShutterControl')
    shutter_control_epics = ADC(EpicsSignal, 'ShutterControlEPICS')
    shutter_fanout = ADC(EpicsSignal, 'ShutterFanout')
    shutter_mode = ADC(ADEpicsSignal, 'ShutterMode')
    shutter_open_delay = ADC(ADEpicsSignal, 'ShutterOpenDelay')
    shutter_open_epics = ADC(EpicsSignal, 'ShutterOpenEPICS')
    shutter_status_epics = ADC(EpicsSignalRO, 'ShutterStatusEPICS_RBV')
    shutter_status = ADC(EpicsSignalRO, 'ShutterStatus_RBV')

    size = DDC(ad_group(ADEpicsSignal,
                        (('size_x', 'SizeX'),
                         ('size_y', 'SizeY'))
                        ))

    status_message = ADC(EpicsSignalRO, 'StatusMessage_RBV', string=True)
    string_from_server = ADC(EpicsSignalRO, 'StringFromServer_RBV', string=True)
    string_to_server = ADC(EpicsSignalRO, 'StringToServer_RBV', string=True)
    temperature = ADC(ADEpicsSignal, 'Temperature')
    temperature_actual = ADC(EpicsSignal, 'TemperatureActual')
    time_remaining = ADC(EpicsSignalRO, 'TimeRemaining_RBV')
    trigger_mode = ADC(ADEpicsSignal, 'TriggerMode')


class SimDetector(AreaDetector):
    _html_docs = ['simDetectorDoc.html']

    gain_rgb = DDC(ad_group(ADEpicsSignal,
                            (('gain_red', 'GainRed'),
                             ('gain_green', 'GainGreen'),
                             ('gain_blue', 'GainBlue'))),
                   doc='Gain rgb components')
    gain_xy = DDC(ad_group(ADEpicsSignal,
                           (('gain_x', 'GainX'),
                            ('gain_y', 'GainY'))),
                  doc='Gain in XY')

    noise = ADC(ADEpicsSignal, 'Noise')
    peak_num = DDC(ad_group(ADEpicsSignal,
                            (('peak_num_x', 'PeakNumX'),
                             ('peak_num_y', 'PeakNumY'))),
                   doc='Peak number in XY')

    peak_start = DDC(ad_group(ADEpicsSignal,
                              (('peak_start_x', 'PeakStartX'),
                               ('peak_start_y', 'PeakStartY'))),
                     doc='Peak start in XY')

    peak_step = DDC(ad_group(ADEpicsSignal,
                             (('peak_step_x', 'PeakStepX'),
                              ('peak_step_y', 'PeakStepY'))),
                    doc='Peak step in XY')

    peak_variation = ADC(ADEpicsSignal, 'PeakVariation')
    peak_width = DDC(ad_group(ADEpicsSignal,
                              (('peak_width_x', 'PeakWidthX'),
                               ('peak_width_y', 'PeakWidthY'))),
                     doc='Peak width in XY')

    reset = ADC(ADEpicsSignal, 'Reset')
    sim_mode = ADC(ADEpicsSignal, 'SimMode')


class AdscDetector(AreaDetector):
    _html_docs = ['adscDoc.html']

    adsc_2theta = ADC(ADEpicsSignal, 'ADSC2Theta')
    adsc_adc = ADC(ADEpicsSignal, 'ADSCAdc')
    adsc_axis = ADC(ADEpicsSignal, 'ADSCAxis')
    adsc_beam_x = ADC(ADEpicsSignal, 'ADSCBeamX')
    adsc_beam_y = ADC(ADEpicsSignal, 'ADSCBeamY')
    adsc_dezingr = ADC(ADEpicsSignal, 'ADSCDezingr')
    adsc_distance = ADC(ADEpicsSignal, 'ADSCDistnce')
    adsc_im_width = ADC(ADEpicsSignal, 'ADSCImWidth')
    adsc_im_xform = ADC(ADEpicsSignal, 'ADSCImXform')
    adsc_kappa = ADC(ADEpicsSignal, 'ADSCKappa')
    adsc_last_error = ADC(EpicsSignal, 'ADSCLastError')
    adsc_last_image = ADC(EpicsSignal, 'ADSCLastImage')
    adsc_omega = ADC(ADEpicsSignal, 'ADSCOmega')
    adsc_phi = ADC(ADEpicsSignal, 'ADSCPhi')
    adsc_raw = ADC(ADEpicsSignal, 'ADSCRaw')
    adsc_read_conditn = ADC(EpicsSignal, 'ADSCReadConditn')
    adsc_reus_drk = ADC(ADEpicsSignal, 'ADSCReusDrk')
    adsc_soft_reset = ADC(EpicsSignal, 'ADSCSoftReset')
    adsc_state = ADC(EpicsSignal, 'ADSCState')
    adsc_status = ADC(EpicsSignal, 'ADSCStatus')
    adsc_stp_ex_retry_count = ADC(EpicsSignal, 'ADSCStpExRtryCt')
    adsc_str_drks = ADC(ADEpicsSignal, 'ADSCStrDrks')
    adsc_wavelen = ADC(ADEpicsSignal, 'ADSCWavelen')

    bin_x_changed = ADC(EpicsSignal, 'BinXChanged')
    bin_y_changed = ADC(EpicsSignal, 'BinYChanged')
    ext_trig_ctl = ADC(EpicsSignal, 'ExSwTrCtl')
    ext_trig_ctl_rsp = ADC(EpicsSignal, 'ExSwTrCtlRsp')
    ext_trig_ok_to_exp = ADC(EpicsSignal, 'ExSwTrOkToExp')


class AndorDetector(AreaDetector):
    _html_docs = ['andorDoc.html']

    andor_adc_speed = ADC(ADEpicsSignal, 'AndorADCSpeed')
    andor_accumulate_period = ADC(ADEpicsSignal, 'AndorAccumulatePeriod')
    andor_cooler = ADC(ADEpicsSignal, 'AndorCooler')
    andor_message = ADC(EpicsSignalRO, 'AndorMessage_RBV')
    andor_pre_amp_gain = ADC(ADEpicsSignal, 'AndorPreAmpGain')
    andor_shutter_ex_ttl = ADC(EpicsSignal, 'AndorShutterExTTL')
    andor_shutter_mode = ADC(EpicsSignal, 'AndorShutterMode')
    andor_temp_status = ADC(EpicsSignalRO, 'AndorTempStatus_RBV')
    file_format = ADC(ADEpicsSignal, 'FileFormat')
    pal_file_path = ADC(ADEpicsSignal, 'PALFilePath')


class Andor3Detector(AreaDetector):
    _html_docs = ['andor3Doc.html']

    a3_binning = ADC(ADEpicsSignal, 'A3Binning')
    a3_shutter_mode = ADC(ADEpicsSignal, 'A3ShutterMode')
    controller_id = ADC(EpicsSignal, 'ControllerID')
    fan_speed = ADC(ADEpicsSignal, 'FanSpeed')
    firmware_version = ADC(EpicsSignal, 'FirmwareVersion')
    frame_rate = ADC(ADEpicsSignal, 'FrameRate')
    full_aoic_ontrol = ADC(EpicsSignal, 'FullAOIControl')
    noise_filter = ADC(ADEpicsSignal, 'NoiseFilter')
    overlap = ADC(ADEpicsSignal, 'Overlap')
    pixel_encoding = ADC(ADEpicsSignal, 'PixelEncoding')
    pre_amp_gain = ADC(ADEpicsSignal, 'PreAmpGain')
    readout_rate = ADC(ADEpicsSignal, 'ReadoutRate')
    readout_time = ADC(EpicsSignal, 'ReadoutTime')
    sensor_cooling = ADC(ADEpicsSignal, 'SensorCooling')
    serial_number = ADC(EpicsSignal, 'SerialNumber')
    software_trigger = ADC(EpicsSignal, 'SoftwareTrigger')
    software_version = ADC(EpicsSignal, 'SoftwareVersion')
    temp_control = ADC(ADEpicsSignal, 'TempControl')
    temp_status = ADC(EpicsSignalRO, 'TempStatus_RBV')
    transfer_rate = ADC(EpicsSignal, 'TransferRate')


class BrukerDetector(AreaDetector):
    _html_docs = ['BrukerDoc.html']

    bis_asyn = ADC(EpicsSignal, 'BISAsyn')
    bis_status = ADC(EpicsSignal, 'BISStatus')
    file_format = ADC(ADEpicsSignal, 'FileFormat')
    num_darks = ADC(ADEpicsSignal, 'NumDarks')
    read_sfrm_timeout = ADC(EpicsSignal, 'ReadSFRMTimeout')


class FirewireLinDetector(AreaDetector):
    _html_docs = ['FirewireWinDoc.html']

    # TODO


class FirewireWinDetector(AreaDetector):
    _html_docs = ['FirewireWinDoc.html']

    colorcode = ADC(ADEpicsSignal, 'COLORCODE')
    current_colorcode = ADC(EpicsSignal, 'CURRENT_COLORCODE')
    current_format = ADC(EpicsSignal, 'CURRENT_FORMAT')
    current_mode = ADC(EpicsSignal, 'CURRENT_MODE')
    current_rate = ADC(EpicsSignal, 'CURRENT_RATE')
    dropped_frames = ADC(ADEpicsSignal, 'DROPPED_FRAMES')
    format_ = ADC(ADEpicsSignal, 'FORMAT')
    frame_rate = ADC(ADEpicsSignal, 'FR')
    mode = ADC(ADEpicsSignal, 'MODE')
    readout_time = ADC(ADEpicsSignal, 'READOUT_TIME')


class LightFieldDetector(AreaDetector):
    _html_docs = ['LightFieldDoc.html']

    # TODO new in AD 2


class Mar345Detector(AreaDetector):
    _html_docs = ['Mar345Doc.html']

    abort = ADC(ADEpicsSignal, 'Abort')
    change_mode = ADC(ADEpicsSignal, 'ChangeMode')
    erase = ADC(ADEpicsSignal, 'Erase')
    erase_mode = ADC(ADEpicsSignal, 'EraseMode')
    file_format = ADC(ADEpicsSignal, 'FileFormat')
    num_erase = ADC(ADEpicsSignal, 'NumErase')
    num_erased = ADC(EpicsSignalRO, 'NumErased_RBV')
    scan_resolution = ADC(ADEpicsSignal, 'ScanResolution')
    scan_size = ADC(ADEpicsSignal, 'ScanSize')
    mar_server_asyn = ADC(EpicsSignal, 'marServerAsyn')


class MarCCDDetector(AreaDetector):
    _html_docs = ['MarCCDDoc.html']

    beam_x = ADC(EpicsSignal, 'BeamX')
    beam_y = ADC(EpicsSignal, 'BeamY')
    dataset_comments = ADC(EpicsSignal, 'DatasetComments')
    detector_distance = ADC(EpicsSignal, 'DetectorDistance')
    file_comments = ADC(EpicsSignal, 'FileComments')
    file_format = ADC(ADEpicsSignal, 'FileFormat')
    frame_shift = ADC(ADEpicsSignal, 'FrameShift')
    mar_acquire_status = ADC(EpicsSignalRO, 'MarAcquireStatus_RBV')
    mar_correct_status = ADC(EpicsSignalRO, 'MarCorrectStatus_RBV')
    mar_dezinger_status = ADC(EpicsSignalRO, 'MarDezingerStatus_RBV')
    mar_readout_status = ADC(EpicsSignalRO, 'MarReadoutStatus_RBV')
    mar_state = ADC(EpicsSignalRO, 'MarState_RBV')
    mar_status = ADC(EpicsSignalRO, 'MarStatus_RBV')
    mar_writing_status = ADC(EpicsSignalRO, 'MarWritingStatus_RBV')
    overlap_mode = ADC(ADEpicsSignal, 'OverlapMode')
    read_tiff_timeout = ADC(EpicsSignal, 'ReadTiffTimeout')
    rotation_axis = ADC(EpicsSignal, 'RotationAxis')
    rotation_range = ADC(EpicsSignal, 'RotationRange')
    stability = ADC(ADEpicsSignal, 'Stability')
    start_phi = ADC(EpicsSignal, 'StartPhi')
    two_theta = ADC(EpicsSignal, 'TwoTheta')
    wavelength = ADC(EpicsSignal, 'Wavelength')
    mar_server_asyn = ADC(EpicsSignal, 'marServerAsyn')


class PerkinElmerDetector(AreaDetector):
    _html_docs = ['PerkinElmerDoc.html']

    pe_acquire_gain = ADC(EpicsSignal, 'PEAcquireGain')
    pe_acquire_offset = ADC(EpicsSignal, 'PEAcquireOffset')
    pe_corrections_dir = ADC(EpicsSignal, 'PECorrectionsDir')
    pe_current_gain_frame = ADC(EpicsSignal, 'PECurrentGainFrame')
    pe_current_offset_frame = ADC(EpicsSignal, 'PECurrentOffsetFrame')
    pe_dwell_time = ADC(ADEpicsSignal, 'PEDwellTime')
    pe_frame_buff_index = ADC(EpicsSignal, 'PEFrameBuffIndex')
    pe_gain = ADC(ADEpicsSignal, 'PEGain')
    pe_gain_available = ADC(EpicsSignal, 'PEGainAvailable')
    pe_gain_file = ADC(EpicsSignal, 'PEGainFile')
    pe_image_number = ADC(EpicsSignal, 'PEImageNumber')
    pe_initialize = ADC(EpicsSignal, 'PEInitialize')
    pe_load_gain_file = ADC(EpicsSignal, 'PELoadGainFile')
    pe_load_pixel_correction = ADC(EpicsSignal, 'PELoadPixelCorrection')
    pe_num_frame_buffers = ADC(ADEpicsSignal, 'PENumFrameBuffers')
    pe_num_frames_to_skip = ADC(ADEpicsSignal, 'PENumFramesToSkip')
    pe_num_gain_frames = ADC(EpicsSignal, 'PENumGainFrames')
    pe_num_offset_frames = ADC(EpicsSignal, 'PENumOffsetFrames')
    pe_offset_available = ADC(EpicsSignal, 'PEOffsetAvailable')
    pe_pixel_correction_available = ADC(EpicsSignal,
                                        'PEPixelCorrectionAvailable')
    pe_pixel_correction_file = ADC(EpicsSignal, 'PEPixelCorrectionFile')
    pe_save_gain_file = ADC(EpicsSignal, 'PESaveGainFile')
    pe_skip_frames = ADC(ADEpicsSignal, 'PESkipFrames')
    pe_sync_time = ADC(ADEpicsSignal, 'PESyncTime')
    pe_system_id = ADC(EpicsSignal, 'PESystemID')
    pe_trigger = ADC(EpicsSignal, 'PETrigger')
    pe_use_gain = ADC(EpicsSignal, 'PEUseGain')
    pe_use_offset = ADC(EpicsSignal, 'PEUseOffset')
    pe_use_pixel_correction = ADC(EpicsSignal, 'PEUsePixelCorrection')


class PSLDetector(AreaDetector):
    _html_docs = ['PSLDoc.html']

    file_format = ADC(ADEpicsSignal, 'FileFormat')
    tiff_comment = ADC(ADEpicsSignal, 'TIFFComment')


class PilatusDetector(AreaDetector):
    _html_docs = ['pilatusDoc.html']

    alpha = ADC(EpicsSignal, 'Alpha')
    angle_incr = ADC(EpicsSignal, 'AngleIncr')
    armed = ADC(EpicsSignal, 'Armed')
    bad_pixel_file = ADC(EpicsSignal, 'BadPixelFile')
    beam_x = ADC(EpicsSignal, 'BeamX')
    beam_y = ADC(EpicsSignal, 'BeamY')
    camserver_asyn = ADC(EpicsSignal, 'CamserverAsyn')
    cbf_template_file = ADC(EpicsSignal, 'CbfTemplateFile')
    chi = ADC(EpicsSignal, 'Chi')
    delay_time = ADC(ADEpicsSignal, 'DelayTime')
    det_2theta = ADC(EpicsSignal, 'Det2theta')
    det_dist = ADC(EpicsSignal, 'DetDist')
    det_v_offset = ADC(EpicsSignal, 'DetVOffset')
    energy_high = ADC(EpicsSignal, 'EnergyHigh')
    energy_low = ADC(EpicsSignal, 'EnergyLow')
    file_format = ADC(ADEpicsSignal, 'FileFormat')
    filter_transm = ADC(EpicsSignal, 'FilterTransm')
    flat_field_file = ADC(EpicsSignal, 'FlatFieldFile')
    flat_field_valid = ADC(EpicsSignal, 'FlatFieldValid')
    flux = ADC(EpicsSignal, 'Flux')
    gain_menu = ADC(EpicsSignal, 'GainMenu')
    gap_fill = ADC(ADEpicsSignal, 'GapFill')
    header_string = ADC(EpicsSignal, 'HeaderString')
    humid0 = ADC(EpicsSignalRO, 'Humid0_RBV')
    humid1 = ADC(EpicsSignalRO, 'Humid1_RBV')
    humid2 = ADC(EpicsSignalRO, 'Humid2_RBV')
    image_file_tmot = ADC(EpicsSignal, 'ImageFileTmot')
    kappa = ADC(EpicsSignal, 'Kappa')
    min_flat_field = ADC(ADEpicsSignal, 'MinFlatField')
    num_bad_pixels = ADC(EpicsSignal, 'NumBadPixels')
    num_oscill = ADC(EpicsSignal, 'NumOscill')
    oscill_axis = ADC(EpicsSignal, 'OscillAxis')
    phi = ADC(EpicsSignal, 'Phi')
    pixel_cut_off = ADC(EpicsSignalRO, 'PixelCutOff_RBV')
    polarization = ADC(EpicsSignal, 'Polarization')
    start_angle = ADC(EpicsSignal, 'StartAngle')
    tvx_version = ADC(EpicsSignalRO, 'TVXVersion_RBV')
    temp0 = ADC(EpicsSignalRO, 'Temp0_RBV')
    temp1 = ADC(EpicsSignalRO, 'Temp1_RBV')
    temp2 = ADC(EpicsSignalRO, 'Temp2_RBV')
    threshold_apply = ADC(EpicsSignal, 'ThresholdApply')
    threshold_auto_apply = ADC(ADEpicsSignal, 'ThresholdAutoApply')
    threshold_energy = ADC(ADEpicsSignal, 'ThresholdEnergy')
    wavelength = ADC(EpicsSignal, 'Wavelength')


class PixiradDetector(AreaDetector):
    _html_docs = ['PixiradDoc.html']

    # TODO new


class PointGreyDetector(AreaDetector):
    _html_docs = ['PointGreyDoc.html']

    # TODO firewirewin


class ProsilicaDetector(AreaDetector):
    _html_docs = ['prosilicaDoc.html']

    ps_bad_frame_counter = ADC(EpicsSignalRO, 'PSBadFrameCounter_RBV')
    ps_byte_rate = ADC(ADEpicsSignal, 'PSByteRate')
    ps_driver_type = ADC(EpicsSignalRO, 'PSDriverType_RBV')
    ps_filter_version = ADC(EpicsSignalRO, 'PSFilterVersion_RBV')
    ps_frame_rate = ADC(EpicsSignalRO, 'PSFrameRate_RBV')
    ps_frames_completed = ADC(EpicsSignalRO, 'PSFramesCompleted_RBV')
    ps_frames_dropped = ADC(EpicsSignalRO, 'PSFramesDropped_RBV')
    ps_packet_size = ADC(EpicsSignalRO, 'PSPacketSize_RBV')
    ps_packets_erroneous = ADC(EpicsSignalRO, 'PSPacketsErroneous_RBV')
    ps_packets_missed = ADC(EpicsSignalRO, 'PSPacketsMissed_RBV')
    ps_packets_received = ADC(EpicsSignalRO, 'PSPacketsReceived_RBV')
    ps_packets_requested = ADC(EpicsSignalRO, 'PSPacketsRequested_RBV')
    ps_packets_resent = ADC(EpicsSignalRO, 'PSPacketsResent_RBV')
    ps_read_statistics = ADC(EpicsSignal, 'PSReadStatistics')
    ps_reset_timer = ADC(EpicsSignal, 'PSResetTimer')
    ps_timestamp_type = ADC(ADEpicsSignal, 'PSTimestampType')
    strobe1_ctl_duration = ADC(ADEpicsSignal, 'Strobe1CtlDuration')
    strobe1_delay = ADC(ADEpicsSignal, 'Strobe1Delay')
    strobe1_duration = ADC(ADEpicsSignal, 'Strobe1Duration')
    strobe1_mode = ADC(ADEpicsSignal, 'Strobe1Mode')
    sync_in1_level = ADC(EpicsSignalRO, 'SyncIn1Level_RBV')
    sync_in2_level = ADC(EpicsSignalRO, 'SyncIn2Level_RBV')
    sync_out1_invert = ADC(ADEpicsSignal, 'SyncOut1Invert')
    sync_out1_level = ADC(ADEpicsSignal, 'SyncOut1Level')
    sync_out1_mode = ADC(ADEpicsSignal, 'SyncOut1Mode')
    sync_out2_invert = ADC(ADEpicsSignal, 'SyncOut2Invert')
    sync_out2_level = ADC(ADEpicsSignal, 'SyncOut2Level')
    sync_out2_mode = ADC(ADEpicsSignal, 'SyncOut2Mode')
    sync_out3_invert = ADC(ADEpicsSignal, 'SyncOut3Invert')
    sync_out3_level = ADC(ADEpicsSignal, 'SyncOut3Level')
    sync_out3_mode = ADC(ADEpicsSignal, 'SyncOut3Mode')
    trigger_delay = ADC(ADEpicsSignal, 'TriggerDelay')
    trigger_event = ADC(ADEpicsSignal, 'TriggerEvent')
    trigger_overlap = ADC(ADEpicsSignal, 'TriggerOverlap')
    trigger_software = ADC(EpicsSignal, 'TriggerSoftware')


class PvcamDetector(AreaDetector):
    _html_docs = ['pvcamDoc.html']

    bit_depth = ADC(EpicsSignalRO, 'BitDepth_RBV')
    camera_firmware_vers = ADC(EpicsSignalRO, 'CameraFirmwareVers_RBV')
    chip_height = ADC(EpicsSignalRO, 'ChipHeight_RBV')
    chip_name = ADC(EpicsSignalRO, 'ChipName_RBV')
    chip_width = ADC(EpicsSignalRO, 'ChipWidth_RBV')
    close_delay = ADC(ADEpicsSignal, 'CloseDelay')
    detector_mode = ADC(ADEpicsSignal, 'DetectorMode')
    detector_selected = ADC(ADEpicsSignal, 'DetectorSelected')
    dev_drv_vers = ADC(EpicsSignalRO, 'DevDrvVers_RBV')
    frame_transfer_capable = ADC(EpicsSignalRO, 'FrameTransferCapable_RBV')
    full_well_capacity = ADC(EpicsSignalRO, 'FullWellCapacity_RBV')
    gain_index = ADC(ADEpicsSignal, 'GainIndex')
    head_ser_num = ADC(EpicsSignalRO, 'HeadSerNum_RBV')
    initialize = ADC(ADEpicsSignal, 'Initialize')
    max_gain_index = ADC(EpicsSignalRO, 'MaxGainIndex_RBV')
    max_set_temperature = ADC(EpicsSignal, 'MaxSetTemperature')
    max_shutter_close_delay = ADC(EpicsSignalRO, 'MaxShutterCloseDelay_RBV')
    max_shutter_open_delay = ADC(EpicsSignalRO, 'MaxShutterOpenDelay_RBV')
    measured_temperature = ADC(EpicsSignalRO, 'MeasuredTemperature_RBV')
    min_set_temperature = ADC(EpicsSignal, 'MinSetTemperature')
    min_shutter_close_delay = ADC(EpicsSignalRO, 'MinShutterCloseDelay_RBV')
    min_shutter_open_delay = ADC(EpicsSignalRO, 'MinShutterOpenDelay_RBV')
    num_parallel_pixels = ADC(EpicsSignalRO, 'NumParallelPixels_RBV')
    num_ports = ADC(EpicsSignalRO, 'NumPorts_RBV')
    num_serial_pixels = ADC(EpicsSignalRO, 'NumSerialPixels_RBV')
    num_speed_table_entries = ADC(EpicsSignalRO, 'NumSpeedTableEntries_RBV')
    open_delay = ADC(ADEpicsSignal, 'OpenDelay')
    pcifw_vers = ADC(EpicsSignalRO, 'PCIFWVers_RBV')
    pv_cam_vers = ADC(EpicsSignalRO, 'PVCamVers_RBV')
    pixel_parallel_dist = ADC(EpicsSignalRO, 'PixelParallelDist_RBV')
    pixel_parallel_size = ADC(EpicsSignalRO, 'PixelParallelSize_RBV')
    pixel_serial_dist = ADC(EpicsSignalRO, 'PixelSerialDist_RBV')
    pixel_serial_size = ADC(EpicsSignalRO, 'PixelSerialSize_RBV')
    pixel_time = ADC(EpicsSignalRO, 'PixelTime_RBV')
    post_mask = ADC(EpicsSignalRO, 'PostMask_RBV')
    post_scan = ADC(EpicsSignalRO, 'PostScan_RBV')
    pre_mask = ADC(EpicsSignalRO, 'PreMask_RBV')
    pre_scan = ADC(EpicsSignalRO, 'PreScan_RBV')
    serial_num = ADC(EpicsSignalRO, 'SerialNum_RBV')
    set_temperature = ADC(ADEpicsSignal, 'SetTemperature')
    slot1_cam = ADC(EpicsSignalRO, 'Slot1Cam_RBV')
    slot2_cam = ADC(EpicsSignalRO, 'Slot2Cam_RBV')
    slot3_cam = ADC(EpicsSignalRO, 'Slot3Cam_RBV')
    speed_table_index = ADC(ADEpicsSignal, 'SpeedTableIndex')
    trigger_edge = ADC(ADEpicsSignal, 'TriggerEdge')


class RoperDetector(AreaDetector):
    _html_docs = ['RoperDoc.html']

    auto_data_type = ADC(ADEpicsSignal, 'AutoDataType')
    comment1 = ADC(ADEpicsSignal, 'Comment1')
    comment2 = ADC(ADEpicsSignal, 'Comment2')
    comment3 = ADC(ADEpicsSignal, 'Comment3')
    comment4 = ADC(ADEpicsSignal, 'Comment4')
    comment5 = ADC(ADEpicsSignal, 'Comment5')
    file_format = ADC(ADEpicsSignal, 'FileFormat')
    num_acquisitions = ADC(ADEpicsSignal, 'NumAcquisitions')
    num_acquisitions_counter = ADC(EpicsSignalRO, 'NumAcquisitionsCounter_RBV')
    roper_shutter_mode = ADC(ADEpicsSignal, 'RoperShutterMode')


class URLDetector(AreaDetector):
    _html_docs = ['URLDoc.html']

    urls = DDC(ad_group(EpicsSignal,
                        (('url_1', 'URL1'),
                         ('url_2', 'URL2'),
                         ('url_3', 'URL3'),
                         ('url_4', 'URL4'),
                         ('url_5', 'URL5'),
                         ('url_6', 'URL6'),
                         ('url_7', 'URL7'),
                         ('url_8', 'URL8'),
                         ('url_9', 'URL9'),
                         ('url_10', 'URL10'))),
               doc='URLs')

    url_select = ADC(EpicsSignal, 'URLSelect')
    url_seq = ADC(EpicsSignal, 'URLSeq')
    url = ADC(EpicsSignalRO, 'URL_RBV')
