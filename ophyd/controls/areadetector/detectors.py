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
import time

from ...utils import enum
from .base import (ADBase, ADComponent as ADC, ad_group, ADEpicsSignal)
from ..signal import (EpicsSignalRO, EpicsSignal)
from ..device import DynamicComponent as DC

logger = logging.getLogger(__name__)


# __all__ = ['AreaDetector',
#            'Andor3Detector',
#            'AndorDetector',
#            'BrukerDetector',
#            'FirewireLinDetector',
#            'FirewireWinDetector',
#            'LightFieldDetector',
#            'Mar345Detector',
#            'MarCCDDetector',
#            'PerkinElmerDetector',
#            'PilatusDetector',
#            'PixiradDetector',
#            'PointGreyDetector',
#            'ProsilicaDetector',
#            'PSLDetector',
#            'PvcamDetector',
#            'RoperDetector',
#            'SimDetector',
#            'URLDetector',
#            ]


class AreaDetector(ADBase):
    _html_docs = ['areaDetectorDoc.html']
    _sep = 'cam1:'
    ImageMode = enum(SINGLE=0, MULTIPLE=1, CONTINUOUS=2)

    acquire = ADC(ADEpicsSignal, 'Acquire')
    acquire_period = ADC(ADEpicsSignal, 'AcquirePeriod')
    acquire_time = ADC(ADEpicsSignal, 'AcquireTime')

    array_callbacks = ADC(ADEpicsSignal, 'ArrayCallbacks')
    array_size = DC(ad_group(EpicsSignalRO,
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

    max_size = DC(ad_group(EpicsSignalRO,
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
    reverse = DC(ad_group(ADEpicsSignal,
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

    size = DC(ad_group(ADEpicsSignal,
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

    gain_rgb = DC(ad_group(ADEpicsSignal,
                           (('gain_red', 'GainRed'),
                            ('gain_green', 'GainGreen'),
                            ('gain_blue', 'GainBlue'))),
                  doc='Gain rgb components')
    gain_xy = DC(ad_group(ADEpicsSignal,
                          (('gain_x', 'GainX'),
                           ('gain_y', 'GainY'))),
                 doc='Gain in XY')

    noise = ADC(ADEpicsSignal, 'Noise')
    peak_num = DC(ad_group(ADEpicsSignal,
                           (('peak_num_x', 'PeakNumX'),
                            ('peak_num_y', 'PeakNumY'))),
                  doc='Peak number in XY')

    peak_start = DC(ad_group(ADEpicsSignal,
                             (('peak_start_x', 'PeakStartX'),
                              ('peak_start_y', 'PeakStartY'))),
                    doc='Peak start in XY')

    peak_step = DC(ad_group(ADEpicsSignal,
                            (('peak_step_x', 'PeakStepX'),
                             ('peak_step_y', 'PeakStepY'))),
                   doc='Peak step in XY')

    peak_variation = ADC(ADEpicsSignal, 'PeakVariation')
    peak_width = DC(ad_group(ADEpicsSignal,
                             (('peak_width_x', 'PeakWidthX'),
                              ('peak_width_y', 'PeakWidthY'))),
                    doc='Peak width in XY')

    reset = ADC(ADEpicsSignal, 'Reset')
    sim_mode = ADC(ADEpicsSignal, 'SimMode')


#  class AdscDetector(AreaDetector):
#      _html_docs = ['adscDoc.html']
#
#      adsc_2theta = ADSignal('ADSC2Theta', has_rbv=True)
#      adsc_adc = ADSignal('ADSCAdc', has_rbv=True)
#      adsc_axis = ADSignal('ADSCAxis', has_rbv=True)
#      adsc_beam_x = ADSignal('ADSCBeamX', has_rbv=True)
#      adsc_beam_y = ADSignal('ADSCBeamY', has_rbv=True)
#      adsc_dezingr = ADSignal('ADSCDezingr', has_rbv=True)
#      adsc_distance = ADSignal('ADSCDistnce', has_rbv=True)
#      adsc_im_width = ADSignal('ADSCImWidth', has_rbv=True)
#      adsc_im_xform = ADSignal('ADSCImXform', has_rbv=True)
#      adsc_kappa = ADSignal('ADSCKappa', has_rbv=True)
#      adsc_last_error = ADSignal('ADSCLastError')
#      adsc_last_image = ADSignal('ADSCLastImage')
#      adsc_omega = ADSignal('ADSCOmega', has_rbv=True)
#      adsc_phi = ADSignal('ADSCPhi', has_rbv=True)
#      adsc_raw = ADSignal('ADSCRaw', has_rbv=True)
#      adsc_read_conditn = ADSignal('ADSCReadConditn')
#      adsc_reus_drk = ADSignal('ADSCReusDrk', has_rbv=True)
#      adsc_soft_reset = ADSignal('ADSCSoftReset')
#      adsc_state = ADSignal('ADSCState')
#      adsc_status = ADSignal('ADSCStatus')
#      adsc_stp_ex_retry_count = ADSignal('ADSCStpExRtryCt')
#      adsc_str_drks = ADSignal('ADSCStrDrks', has_rbv=True)
#      adsc_wavelen = ADSignal('ADSCWavelen', has_rbv=True)
#      bin_x_changed = ADSignal('BinXChanged')
#      bin_y_changed = ADSignal('BinYChanged')
#      ext_trig_ctl = ADSignal('ExSwTrCtl')
#      ext_trig_ctl_rsp = ADSignal('ExSwTrCtlRsp')
#      ext_trig_ok_to_exp = ADSignal('ExSwTrOkToExp')
#
#
#  class AndorDetector(AreaDetector):
#      _html_docs = ['andorDoc.html']
#
#      andor_adc_speed = ADSignal('AndorADCSpeed', has_rbv=True)
#      andor_accumulate_period = ADSignal('AndorAccumulatePeriod', has_rbv=True)
#      andor_cooler = ADSignal('AndorCooler', has_rbv=True)
#      andor_message = ADSignal('AndorMessage_RBV', rw=False)
#      andor_pre_amp_gain = ADSignal('AndorPreAmpGain', has_rbv=True)
#      andor_shutter_ex_ttl = ADSignal('AndorShutterExTTL')
#      andor_shutter_mode = ADSignal('AndorShutterMode')
#      andor_temp_status = ADSignal('AndorTempStatus_RBV', rw=False)
#      file_format = ADSignal('FileFormat', has_rbv=True)
#      pal_file_path = ADSignal('PALFilePath', has_rbv=True)
#
#
#  class Andor3Detector(AreaDetector):
#      _html_docs = ['andor3Doc.html']
#
#      a3_binning = ADSignal('A3Binning', has_rbv=True)
#      a3_shutter_mode = ADSignal('A3ShutterMode', has_rbv=True)
#      controller_id = ADSignal('ControllerID')
#      fan_speed = ADSignal('FanSpeed', has_rbv=True)
#      firmware_version = ADSignal('FirmwareVersion')
#      frame_rate = ADSignal('FrameRate', has_rbv=True)
#      full_aoic_ontrol = ADSignal('FullAOIControl')
#      noise_filter = ADSignal('NoiseFilter', has_rbv=True)
#      overlap = ADSignal('Overlap', has_rbv=True)
#      pixel_encoding = ADSignal('PixelEncoding', has_rbv=True)
#      pre_amp_gain = ADSignal('PreAmpGain', has_rbv=True)
#      readout_rate = ADSignal('ReadoutRate', has_rbv=True)
#      readout_time = ADSignal('ReadoutTime')
#      sensor_cooling = ADSignal('SensorCooling', has_rbv=True)
#      serial_number = ADSignal('SerialNumber')
#      software_trigger = ADSignal('SoftwareTrigger')
#      software_version = ADSignal('SoftwareVersion')
#      temp_control = ADSignal('TempControl', has_rbv=True)
#      temp_status = ADSignal('TempStatus_RBV', rw=False)
#      transfer_rate = ADSignal('TransferRate')
#
#
#  class BrukerDetector(AreaDetector):
#      _html_docs = ['BrukerDoc.html']
#
#      bis_asyn = ADSignal('BISAsyn')
#      bis_status = ADSignal('BISStatus')
#      file_format = ADSignal('FileFormat', has_rbv=True)
#      num_darks = ADSignal('NumDarks', has_rbv=True)
#      read_sfrm_timeout = ADSignal('ReadSFRMTimeout')
#
#
#  class FirewireLinDetector(AreaDetector):
#      _html_docs = ['FirewireWinDoc.html']
#
#      # TODO
#
#
#  class FirewireWinDetector(AreaDetector):
#      _html_docs = ['FirewireWinDoc.html']
#
#      colorcode = ADSignal('COLORCODE', has_rbv=True)
#      current_colorcode = ADSignal('CURRENT_COLORCODE')
#      current_format = ADSignal('CURRENT_FORMAT')
#      current_mode = ADSignal('CURRENT_MODE')
#      current_rate = ADSignal('CURRENT_RATE')
#      dropped_frames = ADSignal('DROPPED_FRAMES', has_rbv=True)
#      format_ = ADSignal('FORMAT', has_rbv=True)
#      frame_rate = ADSignal('FR', has_rbv=True)
#      mode = ADSignal('MODE', has_rbv=True)
#      readout_time = ADSignal('READOUT_TIME', has_rbv=True)
#
#
#  class LightFieldDetector(AreaDetector):
#      _html_docs = ['LightFieldDoc.html']
#
#      # TODO new in AD 2
#
#
#  class Mar345Detector(AreaDetector):
#      _html_docs = ['Mar345Doc.html']
#
#      abort = ADSignal('Abort', has_rbv=True)
#      change_mode = ADSignal('ChangeMode', has_rbv=True)
#      erase = ADSignal('Erase', has_rbv=True)
#      erase_mode = ADSignal('EraseMode', has_rbv=True)
#      file_format = ADSignal('FileFormat', has_rbv=True)
#      num_erase = ADSignal('NumErase', has_rbv=True)
#      num_erased = ADSignal('NumErased_RBV', rw=False)
#      scan_resolution = ADSignal('ScanResolution', has_rbv=True)
#      scan_size = ADSignal('ScanSize', has_rbv=True)
#      mar_server_asyn = ADSignal('marServerAsyn')
#
#
#  class MarCCDDetector(AreaDetector):
#      _html_docs = ['MarCCDDoc.html']
#
#      beam_x = ADSignal('BeamX')
#      beam_y = ADSignal('BeamY')
#      dataset_comments = ADSignal('DatasetComments')
#      detector_distance = ADSignal('DetectorDistance')
#      file_comments = ADSignal('FileComments')
#      file_format = ADSignal('FileFormat', has_rbv=True)
#      frame_shift = ADSignal('FrameShift', has_rbv=True)
#      mar_acquire_status = ADSignal('MarAcquireStatus_RBV', rw=False)
#      mar_correct_status = ADSignal('MarCorrectStatus_RBV', rw=False)
#      mar_dezinger_status = ADSignal('MarDezingerStatus_RBV', rw=False)
#      mar_readout_status = ADSignal('MarReadoutStatus_RBV', rw=False)
#      mar_state = ADSignal('MarState_RBV', rw=False)
#      mar_status = ADSignal('MarStatus_RBV', rw=False)
#      mar_writing_status = ADSignal('MarWritingStatus_RBV', rw=False)
#      overlap_mode = ADSignal('OverlapMode', has_rbv=True)
#      read_tiff_timeout = ADSignal('ReadTiffTimeout')
#      rotation_axis = ADSignal('RotationAxis')
#      rotation_range = ADSignal('RotationRange')
#      stability = ADSignal('Stability', has_rbv=True)
#      start_phi = ADSignal('StartPhi')
#      two_theta = ADSignal('TwoTheta')
#      wavelength = ADSignal('Wavelength')
#      mar_server_asyn = ADSignal('marServerAsyn')
#
#
#  class PerkinElmerDetector(AreaDetector):
#      _html_docs = ['PerkinElmerDoc.html']
#
#      pe_acquire_gain = ADSignal('PEAcquireGain')
#      pe_acquire_offset = ADSignal('PEAcquireOffset')
#      pe_corrections_dir = ADSignal('PECorrectionsDir')
#      pe_current_gain_frame = ADSignal('PECurrentGainFrame')
#      pe_current_offset_frame = ADSignal('PECurrentOffsetFrame')
#      pe_dwell_time = ADSignal('PEDwellTime', has_rbv=True)
#      pe_frame_buff_index = ADSignal('PEFrameBuffIndex')
#      pe_gain = ADSignal('PEGain', has_rbv=True)
#      pe_gain_available = ADSignal('PEGainAvailable')
#      pe_gain_file = ADSignal('PEGainFile')
#      pe_image_number = ADSignal('PEImageNumber')
#      pe_initialize = ADSignal('PEInitialize')
#      pe_load_gain_file = ADSignal('PELoadGainFile')
#      pe_load_pixel_correction = ADSignal('PELoadPixelCorrection')
#      pe_num_frame_buffers = ADSignal('PENumFrameBuffers', has_rbv=True)
#      pe_num_frames_to_skip = ADSignal('PENumFramesToSkip', has_rbv=True)
#      pe_num_gain_frames = ADSignal('PENumGainFrames')
#      pe_num_offset_frames = ADSignal('PENumOffsetFrames')
#      pe_offset_available = ADSignal('PEOffsetAvailable')
#      pe_pixel_correction_available = ADSignal('PEPixelCorrectionAvailable')
#      pe_pixel_correction_file = ADSignal('PEPixelCorrectionFile')
#      pe_save_gain_file = ADSignal('PESaveGainFile')
#      pe_skip_frames = ADSignal('PESkipFrames', has_rbv=True)
#      pe_sync_time = ADSignal('PESyncTime', has_rbv=True)
#      pe_system_id = ADSignal('PESystemID')
#      pe_trigger = ADSignal('PETrigger')
#      pe_use_gain = ADSignal('PEUseGain')
#      pe_use_offset = ADSignal('PEUseOffset')
#      pe_use_pixel_correction = ADSignal('PEUsePixelCorrection')
#
#
#  class PSLDetector(AreaDetector):
#      _html_docs = ['PSLDoc.html']
#
#      file_format = ADSignal('FileFormat', has_rbv=True)
#      tiff_comment = ADSignal('TIFFComment', has_rbv=True)
#
#
#  class PilatusDetector(AreaDetector):
#      _html_docs = ['pilatusDoc.html']
#
#      alpha = ADSignal('Alpha')
#      angle_incr = ADSignal('AngleIncr')
#      armed = ADSignal('Armed')
#      bad_pixel_file = ADSignal('BadPixelFile')
#      beam_x = ADSignal('BeamX')
#      beam_y = ADSignal('BeamY')
#      camserver_asyn = ADSignal('CamserverAsyn')
#      cbf_template_file = ADSignal('CbfTemplateFile')
#      chi = ADSignal('Chi')
#      delay_time = ADSignal('DelayTime', has_rbv=True)
#      det_2theta = ADSignal('Det2theta')
#      det_dist = ADSignal('DetDist')
#      det_v_offset = ADSignal('DetVOffset')
#      energy_high = ADSignal('EnergyHigh')
#      energy_low = ADSignal('EnergyLow')
#      file_format = ADSignal('FileFormat', has_rbv=True)
#      filter_transm = ADSignal('FilterTransm')
#      flat_field_file = ADSignal('FlatFieldFile')
#      flat_field_valid = ADSignal('FlatFieldValid')
#      flux = ADSignal('Flux')
#      gain_menu = ADSignal('GainMenu')
#      gap_fill = ADSignal('GapFill', has_rbv=True)
#      header_string = ADSignal('HeaderString')
#      humid0 = ADSignal('Humid0_RBV', rw=False)
#      humid1 = ADSignal('Humid1_RBV', rw=False)
#      humid2 = ADSignal('Humid2_RBV', rw=False)
#      image_file_tmot = ADSignal('ImageFileTmot')
#      kappa = ADSignal('Kappa')
#      min_flat_field = ADSignal('MinFlatField', has_rbv=True)
#      num_bad_pixels = ADSignal('NumBadPixels')
#      num_oscill = ADSignal('NumOscill')
#      oscill_axis = ADSignal('OscillAxis')
#      phi = ADSignal('Phi')
#      pixel_cut_off = ADSignal('PixelCutOff_RBV', rw=False)
#      polarization = ADSignal('Polarization')
#      start_angle = ADSignal('StartAngle')
#      tvx_version = ADSignal('TVXVersion_RBV', rw=False)
#      temp0 = ADSignal('Temp0_RBV', rw=False)
#      temp1 = ADSignal('Temp1_RBV', rw=False)
#      temp2 = ADSignal('Temp2_RBV', rw=False)
#      threshold_apply = ADSignal('ThresholdApply')
#      threshold_auto_apply = ADSignal('ThresholdAutoApply', has_rbv=True)
#      threshold_energy = ADSignal('ThresholdEnergy', has_rbv=True)
#      wavelength = ADSignal('Wavelength')
#
#
#  class PixiradDetector(AreaDetector):
#      _html_docs = ['PixiradDoc.html']
#
#      # TODO new
#
#
#  class PointGreyDetector(AreaDetector):
#      _html_docs = ['PointGreyDoc.html']
#
#      # TODO firewirewin
#
#
#  class ProsilicaDetector(AreaDetector):
#      _html_docs = ['prosilicaDoc.html']
#
#      ps_bad_frame_counter = ADSignal('PSBadFrameCounter_RBV', rw=False)
#      ps_byte_rate = ADSignal('PSByteRate', has_rbv=True)
#      ps_driver_type = ADSignal('PSDriverType_RBV', rw=False)
#      ps_filter_version = ADSignal('PSFilterVersion_RBV', rw=False)
#      ps_frame_rate = ADSignal('PSFrameRate_RBV', rw=False)
#      ps_frames_completed = ADSignal('PSFramesCompleted_RBV', rw=False)
#      ps_frames_dropped = ADSignal('PSFramesDropped_RBV', rw=False)
#      ps_packet_size = ADSignal('PSPacketSize_RBV', rw=False)
#      ps_packets_erroneous = ADSignal('PSPacketsErroneous_RBV', rw=False)
#      ps_packets_missed = ADSignal('PSPacketsMissed_RBV', rw=False)
#      ps_packets_received = ADSignal('PSPacketsReceived_RBV', rw=False)
#      ps_packets_requested = ADSignal('PSPacketsRequested_RBV', rw=False)
#      ps_packets_resent = ADSignal('PSPacketsResent_RBV', rw=False)
#      ps_read_statistics = ADSignal('PSReadStatistics')
#      ps_reset_timer = ADSignal('PSResetTimer')
#      ps_timestamp_type = ADSignal('PSTimestampType', has_rbv=True)
#      strobe1_ctl_duration = ADSignal('Strobe1CtlDuration', has_rbv=True)
#      strobe1_delay = ADSignal('Strobe1Delay', has_rbv=True)
#      strobe1_duration = ADSignal('Strobe1Duration', has_rbv=True)
#      strobe1_mode = ADSignal('Strobe1Mode', has_rbv=True)
#      sync_in1_level = ADSignal('SyncIn1Level_RBV', rw=False)
#      sync_in2_level = ADSignal('SyncIn2Level_RBV', rw=False)
#      sync_out1_invert = ADSignal('SyncOut1Invert', has_rbv=True)
#      sync_out1_level = ADSignal('SyncOut1Level', has_rbv=True)
#      sync_out1_mode = ADSignal('SyncOut1Mode', has_rbv=True)
#      sync_out2_invert = ADSignal('SyncOut2Invert', has_rbv=True)
#      sync_out2_level = ADSignal('SyncOut2Level', has_rbv=True)
#      sync_out2_mode = ADSignal('SyncOut2Mode', has_rbv=True)
#      sync_out3_invert = ADSignal('SyncOut3Invert', has_rbv=True)
#      sync_out3_level = ADSignal('SyncOut3Level', has_rbv=True)
#      sync_out3_mode = ADSignal('SyncOut3Mode', has_rbv=True)
#      trigger_delay = ADSignal('TriggerDelay', has_rbv=True)
#      trigger_event = ADSignal('TriggerEvent', has_rbv=True)
#      trigger_overlap = ADSignal('TriggerOverlap', has_rbv=True)
#      trigger_software = ADSignal('TriggerSoftware')
#
#
#  class PvcamDetector(AreaDetector):
#      _html_docs = ['pvcamDoc.html']
#
#      bit_depth = ADSignal('BitDepth_RBV', rw=False)
#      camera_firmware_vers = ADSignal('CameraFirmwareVers_RBV', rw=False)
#      chip_height = ADSignal('ChipHeight_RBV', rw=False)
#      chip_name = ADSignal('ChipName_RBV', rw=False)
#      chip_width = ADSignal('ChipWidth_RBV', rw=False)
#      close_delay = ADSignal('CloseDelay', has_rbv=True)
#      detector_mode = ADSignal('DetectorMode', has_rbv=True)
#      detector_selected = ADSignal('DetectorSelected', has_rbv=True)
#      dev_drv_vers = ADSignal('DevDrvVers_RBV', rw=False)
#      frame_transfer_capable = ADSignal('FrameTransferCapable_RBV', rw=False)
#      full_well_capacity = ADSignal('FullWellCapacity_RBV', rw=False)
#      gain_index = ADSignal('GainIndex', has_rbv=True)
#      head_ser_num = ADSignal('HeadSerNum_RBV', rw=False)
#      initialize = ADSignal('Initialize', has_rbv=True)
#      max_gain_index = ADSignal('MaxGainIndex_RBV', rw=False)
#      max_set_temperature = ADSignal('MaxSetTemperature')
#      max_shutter_close_delay = ADSignal('MaxShutterCloseDelay_RBV', rw=False)
#      max_shutter_open_delay = ADSignal('MaxShutterOpenDelay_RBV', rw=False)
#      measured_temperature = ADSignal('MeasuredTemperature_RBV', rw=False)
#      min_set_temperature = ADSignal('MinSetTemperature')
#      min_shutter_close_delay = ADSignal('MinShutterCloseDelay_RBV', rw=False)
#      min_shutter_open_delay = ADSignal('MinShutterOpenDelay_RBV', rw=False)
#      num_parallel_pixels = ADSignal('NumParallelPixels_RBV', rw=False)
#      num_ports = ADSignal('NumPorts_RBV', rw=False)
#      num_serial_pixels = ADSignal('NumSerialPixels_RBV', rw=False)
#      num_speed_table_entries = ADSignal('NumSpeedTableEntries_RBV', rw=False)
#      open_delay = ADSignal('OpenDelay', has_rbv=True)
#      pcifw_vers = ADSignal('PCIFWVers_RBV', rw=False)
#      pv_cam_vers = ADSignal('PVCamVers_RBV', rw=False)
#      pixel_parallel_dist = ADSignal('PixelParallelDist_RBV', rw=False)
#      pixel_parallel_size = ADSignal('PixelParallelSize_RBV', rw=False)
#      pixel_serial_dist = ADSignal('PixelSerialDist_RBV', rw=False)
#      pixel_serial_size = ADSignal('PixelSerialSize_RBV', rw=False)
#      pixel_time = ADSignal('PixelTime_RBV', rw=False)
#      post_mask = ADSignal('PostMask_RBV', rw=False)
#      post_scan = ADSignal('PostScan_RBV', rw=False)
#      pre_mask = ADSignal('PreMask_RBV', rw=False)
#      pre_scan = ADSignal('PreScan_RBV', rw=False)
#      serial_num = ADSignal('SerialNum_RBV', rw=False)
#      set_temperature = ADSignal('SetTemperature', has_rbv=True)
#      slot1_cam = ADSignal('Slot1Cam_RBV', rw=False)
#      slot2_cam = ADSignal('Slot2Cam_RBV', rw=False)
#      slot3_cam = ADSignal('Slot3Cam_RBV', rw=False)
#      speed_table_index = ADSignal('SpeedTableIndex', has_rbv=True)
#      trigger_edge = ADSignal('TriggerEdge', has_rbv=True)
#
#
#  class RoperDetector(AreaDetector):
#      _html_docs = ['RoperDoc.html']
#
#      auto_data_type = ADSignal('AutoDataType', has_rbv=True)
#      comment1 = ADSignal('Comment1', has_rbv=True)
#      comment2 = ADSignal('Comment2', has_rbv=True)
#      comment3 = ADSignal('Comment3', has_rbv=True)
#      comment4 = ADSignal('Comment4', has_rbv=True)
#      comment5 = ADSignal('Comment5', has_rbv=True)
#      file_format = ADSignal('FileFormat', has_rbv=True)
#      num_acquisitions = ADSignal('NumAcquisitions', has_rbv=True)
#      num_acquisitions_counter = ADSignal('NumAcquisitionsCounter_RBV', rw=False)
#      roper_shutter_mode = ADSignal('RoperShutterMode', has_rbv=True)
#
#
#  class URLDetector(AreaDetector):
#      _html_docs = ['URLDoc.html']
#
#      url_1 = ADSignal('URL1')
#      url_2 = ADSignal('URL2')
#      url_3 = ADSignal('URL3')
#      url_4 = ADSignal('URL4')
#      url_5 = ADSignal('URL5')
#      url_6 = ADSignal('URL6')
#      url_7 = ADSignal('URL7')
#      url_8 = ADSignal('URL8')
#      url_9 = ADSignal('URL9')
#      url_10 = ADSignal('URL10')
#
#      urls = ADSignalGroup(url_1, url_2, url_3, url_4, url_5,
#                           url_6, url_7, url_8, url_9, url_10,
#                           doc='URLs')
#
#      url_select = ADSignal('URLSelect')
#      url_seq = ADSignal('URLSeq')
#      url = ADSignal('URL_RBV', rw=False)
