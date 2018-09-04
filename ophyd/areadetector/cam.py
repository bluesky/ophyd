import logging

from ..utils import enum
from .base import (ADBase, ADComponent as C, ad_group,
                   EpicsSignalWithRBV as SignalWithRBV)
from ..signal import (EpicsSignalRO, EpicsSignal)
from ..device import DynamicDeviceComponent as DDC

logger = logging.getLogger(__name__)


__all__ = ['CamBase',
           'AdscDetectorCam',
           'Andor3DetectorCam',
           'AndorDetectorCam',
           'BrukerDetectorCam',
           'FirewireLinDetectorCam',
           'FirewireWinDetectorCam',
           'LightFieldDetectorCam',
           'Mar345DetectorCam',
           'MarCCDDetectorCam',
           'PSLDetectorCam',
           'PcoDetectorCam',
           'PcoDetectorIO',
           'PcoDetectorSimIO',
           'PerkinElmerDetectorCam',
           'PilatusDetectorCam',
           'PixiradDetectorCam',
           'PointGreyDetectorCam',
           'ProsilicaDetectorCam',
           'PvcamDetectorCam',
           'RoperDetectorCam',
           'SimDetectorCam',
           'URLDetectorCam',
           ]


class CamBase(ADBase):
    _default_configuration_attrs = (ADBase._default_configuration_attrs +
                                    ('acquire_time', 'acquire_period',
                                     'model', 'num_exposures', 'image_mode',
                                     'manufacturer', 'trigger_mode'))

    ImageMode = enum(SINGLE=0, MULTIPLE=1, CONTINUOUS=2)

    # Shared among all cams and plugins
    array_counter = C(SignalWithRBV, 'ArrayCounter')
    array_rate = C(EpicsSignalRO, 'ArrayRate_RBV')
    asyn_io = C(EpicsSignal, 'AsynIO')

    nd_attributes_file = C(EpicsSignal, 'NDAttributesFile', string=True)
    pool_alloc_buffers = C(EpicsSignalRO, 'PoolAllocBuffers')
    pool_free_buffers = C(EpicsSignalRO, 'PoolFreeBuffers')
    pool_max_buffers = C(EpicsSignalRO, 'PoolMaxBuffers')
    pool_max_mem = C(EpicsSignalRO, 'PoolMaxMem')
    pool_used_buffers = C(EpicsSignalRO, 'PoolUsedBuffers')
    pool_used_mem = C(EpicsSignalRO, 'PoolUsedMem')
    port_name = C(EpicsSignalRO, 'PortName_RBV', string=True)

    # Cam-specific
    acquire = C(SignalWithRBV, 'Acquire')
    acquire_period = C(SignalWithRBV, 'AcquirePeriod')
    acquire_time = C(SignalWithRBV, 'AcquireTime')

    array_callbacks = C(SignalWithRBV, 'ArrayCallbacks')
    array_size = DDC(ad_group(EpicsSignalRO,
                              (('array_size_x', 'ArraySizeX_RBV'),
                               ('array_size_y', 'ArraySizeY_RBV'),
                               ('array_size_z', 'ArraySizeZ_RBV'))),
                     doc='Size of the array in the XYZ dimensions')

    array_size_bytes = C(EpicsSignalRO, 'ArraySize_RBV')
    bin_x = C(SignalWithRBV, 'BinX')
    bin_y = C(SignalWithRBV, 'BinY')
    color_mode = C(SignalWithRBV, 'ColorMode')
    data_type = C(SignalWithRBV, 'DataType')
    detector_state = C(EpicsSignalRO, 'DetectorState_RBV')
    frame_type = C(SignalWithRBV, 'FrameType')
    gain = C(SignalWithRBV, 'Gain')

    image_mode = C(SignalWithRBV, 'ImageMode')
    manufacturer = C(EpicsSignalRO, 'Manufacturer_RBV')

    max_size = DDC(ad_group(EpicsSignalRO,
                            (('max_size_x', 'MaxSizeX_RBV'),
                             ('max_size_y', 'MaxSizeY_RBV'))),
                   doc='Maximum sensor size in the XY directions')

    min_x = C(SignalWithRBV, 'MinX')
    min_y = C(SignalWithRBV, 'MinY')
    model = C(EpicsSignalRO, 'Model_RBV')

    num_exposures = C(SignalWithRBV, 'NumExposures')
    num_exposures_counter = C(EpicsSignalRO, 'NumExposuresCounter_RBV')
    num_images = C(SignalWithRBV, 'NumImages')
    num_images_counter = C(EpicsSignalRO, 'NumImagesCounter_RBV')

    read_status = C(EpicsSignal, 'ReadStatus')
    reverse = DDC(ad_group(SignalWithRBV,
                           (('reverse_x', 'ReverseX'),
                            ('reverse_y', 'ReverseY'))
                           ))

    shutter_close_delay = C(SignalWithRBV, 'ShutterCloseDelay')
    shutter_close_epics = C(EpicsSignal, 'ShutterCloseEPICS')
    shutter_control = C(SignalWithRBV, 'ShutterControl')
    shutter_control_epics = C(EpicsSignal, 'ShutterControlEPICS')
    shutter_fanout = C(EpicsSignal, 'ShutterFanout')
    shutter_mode = C(SignalWithRBV, 'ShutterMode')
    shutter_open_delay = C(SignalWithRBV, 'ShutterOpenDelay')
    shutter_open_epics = C(EpicsSignal, 'ShutterOpenEPICS')
    shutter_status_epics = C(EpicsSignalRO, 'ShutterStatusEPICS_RBV')
    shutter_status = C(EpicsSignalRO, 'ShutterStatus_RBV')

    size = DDC(ad_group(SignalWithRBV,
                        (('size_x', 'SizeX'),
                         ('size_y', 'SizeY'))
                        ))

    status_message = C(EpicsSignalRO, 'StatusMessage_RBV', string=True)
    string_from_server = C(EpicsSignalRO, 'StringFromServer_RBV', string=True)
    string_to_server = C(EpicsSignalRO, 'StringToServer_RBV', string=True)
    temperature = C(SignalWithRBV, 'Temperature')
    temperature_actual = C(EpicsSignal, 'TemperatureActual')
    time_remaining = C(EpicsSignalRO, 'TimeRemaining_RBV')
    trigger_mode = C(SignalWithRBV, 'TriggerMode')


class AreaDetectorCam(CamBase):
    pass


class SimDetectorCam(CamBase):
    _html_docs = ['simDetectorDoc.html']
    gain_rgb = DDC(ad_group(SignalWithRBV,
                            (('gain_red', 'GainRed'),
                             ('gain_green', 'GainGreen'),
                             ('gain_blue', 'GainBlue'))),
                   doc='Gain rgb components')
    gain_xy = DDC(ad_group(SignalWithRBV,
                           (('gain_x', 'GainX'),
                            ('gain_y', 'GainY'))),
                  doc='Gain in XY')

    noise = C(SignalWithRBV, 'Noise')
    peak_num = DDC(ad_group(SignalWithRBV,
                            (('peak_num_x', 'PeakNumX'),
                             ('peak_num_y', 'PeakNumY'))),
                   doc='Peak number in XY')

    peak_start = DDC(ad_group(SignalWithRBV,
                              (('peak_start_x', 'PeakStartX'),
                               ('peak_start_y', 'PeakStartY'))),
                     doc='Peak start in XY')

    peak_step = DDC(ad_group(SignalWithRBV,
                             (('peak_step_x', 'PeakStepX'),
                              ('peak_step_y', 'PeakStepY'))),
                    doc='Peak step in XY')

    peak_variation = C(SignalWithRBV, 'PeakVariation')
    peak_width = DDC(ad_group(SignalWithRBV,
                              (('peak_width_x', 'PeakWidthX'),
                               ('peak_width_y', 'PeakWidthY'))),
                     doc='Peak width in XY')

    reset = C(SignalWithRBV, 'Reset')
    sim_mode = C(SignalWithRBV, 'SimMode')


class AdscDetectorCam(CamBase):
    _html_docs = ['adscDoc.html']
    adsc_2theta = C(SignalWithRBV, 'ADSC2Theta')
    adsc_adc = C(SignalWithRBV, 'ADSCAdc')
    adsc_axis = C(SignalWithRBV, 'ADSCAxis')
    adsc_beam_x = C(SignalWithRBV, 'ADSCBeamX')
    adsc_beam_y = C(SignalWithRBV, 'ADSCBeamY')
    adsc_dezingr = C(SignalWithRBV, 'ADSCDezingr')
    adsc_distance = C(SignalWithRBV, 'ADSCDistnce')
    adsc_im_width = C(SignalWithRBV, 'ADSCImWidth')
    adsc_im_xform = C(SignalWithRBV, 'ADSCImXform')
    adsc_kappa = C(SignalWithRBV, 'ADSCKappa')
    adsc_last_error = C(EpicsSignal, 'ADSCLastError')
    adsc_last_image = C(EpicsSignal, 'ADSCLastImage')
    adsc_omega = C(SignalWithRBV, 'ADSCOmega')
    adsc_phi = C(SignalWithRBV, 'ADSCPhi')
    adsc_raw = C(SignalWithRBV, 'ADSCRaw')
    adsc_read_conditn = C(EpicsSignal, 'ADSCReadConditn')
    adsc_reus_drk = C(SignalWithRBV, 'ADSCReusDrk')
    adsc_soft_reset = C(EpicsSignal, 'ADSCSoftReset')
    adsc_state = C(EpicsSignal, 'ADSCState')
    adsc_status = C(EpicsSignal, 'ADSCStatus')
    adsc_stp_ex_retry_count = C(EpicsSignal, 'ADSCStpExRtryCt')
    adsc_str_drks = C(SignalWithRBV, 'ADSCStrDrks')
    adsc_wavelen = C(SignalWithRBV, 'ADSCWavelen')

    bin_x_changed = C(EpicsSignal, 'BinXChanged')
    bin_y_changed = C(EpicsSignal, 'BinYChanged')
    ext_trig_ctl = C(EpicsSignal, 'ExSwTrCtl')
    ext_trig_ctl_rsp = C(EpicsSignal, 'ExSwTrCtlRsp')
    ext_trig_ok_to_exp = C(EpicsSignal, 'ExSwTrOkToExp')


class AndorDetectorCam(CamBase):
    _html_docs = ['andorDoc.html']
    andor_adc_speed = C(SignalWithRBV, 'AndorADCSpeed')
    andor_accumulate_period = C(SignalWithRBV, 'AndorAccumulatePeriod')
    andor_cooler = C(SignalWithRBV, 'AndorCooler')
    andor_message = C(EpicsSignalRO, 'AndorMessage_RBV')
    andor_pre_amp_gain = C(SignalWithRBV, 'AndorPreAmpGain')
    andor_shutter_ex_ttl = C(EpicsSignal, 'AndorShutterExTTL')
    andor_shutter_mode = C(EpicsSignal, 'AndorShutterMode')
    andor_temp_status = C(EpicsSignalRO, 'AndorTempStatus_RBV')
    file_format = C(SignalWithRBV, 'FileFormat')
    pal_file_path = C(SignalWithRBV, 'PALFilePath')


class Andor3DetectorCam(CamBase):
    _html_docs = ['andor3Doc.html']
    a3_binning = C(SignalWithRBV, 'A3Binning')
    a3_shutter_mode = C(SignalWithRBV, 'A3ShutterMode')
    controller_id = C(EpicsSignal, 'ControllerID')
    fan_speed = C(SignalWithRBV, 'FanSpeed')
    firmware_version = C(EpicsSignal, 'FirmwareVersion')
    frame_rate = C(SignalWithRBV, 'FrameRate')
    full_aoic_ontrol = C(EpicsSignal, 'FullAOIControl')
    noise_filter = C(SignalWithRBV, 'NoiseFilter')
    overlap = C(SignalWithRBV, 'Overlap')
    pixel_encoding = C(SignalWithRBV, 'PixelEncoding')
    pre_amp_gain = C(SignalWithRBV, 'PreAmpGain')
    readout_rate = C(SignalWithRBV, 'ReadoutRate')
    readout_time = C(EpicsSignal, 'ReadoutTime')
    sensor_cooling = C(SignalWithRBV, 'SensorCooling')
    serial_number = C(EpicsSignal, 'SerialNumber')
    software_trigger = C(EpicsSignal, 'SoftwareTrigger')
    software_version = C(EpicsSignal, 'SoftwareVersion')
    temp_control = C(SignalWithRBV, 'TempControl')
    temp_status = C(EpicsSignalRO, 'TempStatus_RBV')
    transfer_rate = C(EpicsSignal, 'TransferRate')


class BrukerDetectorCam(CamBase):
    _html_docs = ['BrukerDoc.html']
    bis_asyn = C(EpicsSignal, 'BISAsyn')
    bis_status = C(EpicsSignal, 'BISStatus')
    file_format = C(SignalWithRBV, 'FileFormat')
    num_darks = C(SignalWithRBV, 'NumDarks')
    read_sfrm_timeout = C(EpicsSignal, 'ReadSFRMTimeout')


class FirewireLinDetectorCam(CamBase):
    _html_docs = []

    bandwidth = C(EpicsSignal, 'BANDWIDTH')
    fanout_disable = C(EpicsSignal, 'FanoutDis')
    framerate_max = C(SignalWithRBV, 'FR')
    is_fixed_mode = C(EpicsSignal, 'IsFixedMode')
    video_mode = C(EpicsSignal, 'VIDEOMODE')


class FirewireWinDetectorCam(CamBase):
    _html_docs = ['FirewireWinDoc.html']
    colorcode = C(SignalWithRBV, 'COLORCODE')
    current_colorcode = C(EpicsSignal, 'CURRENT_COLORCODE')
    current_format = C(EpicsSignal, 'CURRENT_FORMAT')
    current_mode = C(EpicsSignal, 'CURRENT_MODE')
    current_rate = C(EpicsSignal, 'CURRENT_RATE')
    dropped_frames = C(SignalWithRBV, 'DROPPED_FRAMES')
    format_ = C(SignalWithRBV, 'FORMAT')
    frame_rate = C(SignalWithRBV, 'FR')
    mode = C(SignalWithRBV, 'MODE')
    readout_time = C(SignalWithRBV, 'READOUT_TIME')


class LightFieldDetectorCam(CamBase):
    _html_docs = ['LightFieldDoc.html']

    aux_delay = C(SignalWithRBV, 'LFAuxDelay')
    aux_width = C(SignalWithRBV, 'LFAuxWidth')
    background_enable = C(SignalWithRBV, 'LFBackgroundEnable')
    background_file = C(SignalWithRBV, 'LFBackgroundFile')
    background_full_file = C(EpicsSignalRO, 'LFBackgroundFullFile_RBV')
    background_path = C(SignalWithRBV, 'LFBackgroundPath')
    entrance_width = C(SignalWithRBV, 'LFEntranceWidth')
    exit_port = C(SignalWithRBV, 'LFExitPort')
    experiment_name = C(SignalWithRBV, 'LFExperimentName')
    file_name = C(EpicsSignalRO, 'LFFileName_RBV')
    file_path = C(EpicsSignalRO, 'LFFilePath_RBV')
    lf_gain = C(SignalWithRBV, 'LFGain')
    gating_mode = C(SignalWithRBV, 'LFGatingMode')
    grating = C(SignalWithRBV, 'LFGrating')
    grating_wavelength = C(SignalWithRBV, 'LFGratingWavelength')
    image_mode = C(SignalWithRBV, 'ImageMode')
    intensifier_enable = C(SignalWithRBV, 'LFIntensifierEnable')
    intensifier_gain = C(SignalWithRBV, 'LFIntensifierGain')
    num_accumulations = C(SignalWithRBV, 'NumAccumulations')
    ready_to_run = C(EpicsSignal, 'LFReadyToRun')
    rep_gate_delay = C(SignalWithRBV, 'LFRepGateDelay')
    rep_gate_width = C(SignalWithRBV, 'LFRepGateWidth')
    seq_end_gate_delay = C(SignalWithRBV, 'LFSeqEndGateDelay')
    seq_end_gate_width = C(SignalWithRBV, 'LFSeqEndGateWidth')
    seq_start_gate_delay = C(SignalWithRBV, 'LFSeqStartGateDelay')
    seq_start_gate_width = C(SignalWithRBV, 'LFSeqStartGateWidth')
    lf_shutter_mode = C(SignalWithRBV, 'LFShutterMode')
    sync_master2_delay = C(SignalWithRBV, 'LFSyncMaster2Delay')
    sync_master_enable = C(SignalWithRBV, 'LFSyncMasterEnable')
    trigger_frequency = C(SignalWithRBV, 'LFTriggerFrequency')
    update_experiments = C(EpicsSignal, 'LFUpdateExperiments')


class Mar345DetectorCam(CamBase):
    _html_docs = ['Mar345Doc.html']
    abort = C(SignalWithRBV, 'Abort')
    change_mode = C(SignalWithRBV, 'ChangeMode')
    erase = C(SignalWithRBV, 'Erase')
    erase_mode = C(SignalWithRBV, 'EraseMode')
    file_format = C(SignalWithRBV, 'FileFormat')
    num_erase = C(SignalWithRBV, 'NumErase')
    num_erased = C(EpicsSignalRO, 'NumErased_RBV')
    scan_resolution = C(SignalWithRBV, 'ScanResolution')
    scan_size = C(SignalWithRBV, 'ScanSize')
    mar_server_asyn = C(EpicsSignal, 'marServerAsyn')


class MarCCDDetectorCam(CamBase):
    _html_docs = ['MarCCDDoc.html']
    beam_x = C(EpicsSignal, 'BeamX')
    beam_y = C(EpicsSignal, 'BeamY')
    dataset_comments = C(EpicsSignal, 'DatasetComments')
    detector_distance = C(EpicsSignal, 'DetectorDistance')
    file_comments = C(EpicsSignal, 'FileComments')
    file_format = C(SignalWithRBV, 'FileFormat')
    frame_shift = C(SignalWithRBV, 'FrameShift')
    mar_acquire_status = C(EpicsSignalRO, 'MarAcquireStatus_RBV')
    mar_correct_status = C(EpicsSignalRO, 'MarCorrectStatus_RBV')
    mar_dezinger_status = C(EpicsSignalRO, 'MarDezingerStatus_RBV')
    mar_readout_status = C(EpicsSignalRO, 'MarReadoutStatus_RBV')
    mar_state = C(EpicsSignalRO, 'MarState_RBV')
    mar_status = C(EpicsSignalRO, 'MarStatus_RBV')
    mar_writing_status = C(EpicsSignalRO, 'MarWritingStatus_RBV')
    overlap_mode = C(SignalWithRBV, 'OverlapMode')
    read_tiff_timeout = C(EpicsSignal, 'ReadTiffTimeout')
    rotation_axis = C(EpicsSignal, 'RotationAxis')
    rotation_range = C(EpicsSignal, 'RotationRange')
    stability = C(SignalWithRBV, 'Stability')
    start_phi = C(EpicsSignal, 'StartPhi')
    two_theta = C(EpicsSignal, 'TwoTheta')
    wavelength = C(EpicsSignal, 'Wavelength')
    mar_server_asyn = C(EpicsSignal, 'marServerAsyn')


class PcoDetectorCam(CamBase):
    _html_docs = ['']
    adc_mode = C(SignalWithRBV, 'ADC_MODE')
    arm_mode = C(SignalWithRBV, 'ARM_MODE')
    bit_alignment = C(SignalWithRBV, 'BIT_ALIGNMENT')
    camera_setup = C(SignalWithRBV, 'CAMERA_SETUP')
    cam_ram_use = C(EpicsSignalRO, 'CAM_RAM_USE_RBV')
    delay_time = C(SignalWithRBV, 'DELAY_TIME')
    elec_temp = C(EpicsSignalRO, 'ELEC_TEMP_RBV')
    exposure_base = C(EpicsSignalRO, 'EXPOSUREBASE_RBV')
    pco_acquire_mode = C(SignalWithRBV, 'ACQUIRE_MODE')
    pco_image_number = C(EpicsSignalRO, 'IMAGE_NUMBER_RBV')
    pix_rate = C(SignalWithRBV, 'PIX_RATE')
    power_temp = C(EpicsSignalRO, 'POWER_TEMP_RBV')
    recorder_mode = C(SignalWithRBV, 'RECORDER_MODE')
    storage_mode = C(SignalWithRBV, 'STORAGE_MODE')
    timestamp_mode = C(SignalWithRBV, 'TIMESTAMP_MODE')


class PcoDetectorIO(ADBase):
    _html_docs = ['']
    busy = C(EpicsSignal, 'DIO:BUSY')
    capture = C(EpicsSignal, 'DIO:CAPTURE')
    exposing = C(EpicsSignal, 'DIO:EXPOSING')
    ready = C(EpicsSignal, 'DIO:READY')
    trig = C(EpicsSignal, 'DIO:TRIG')
    trig_when_ready = C(EpicsSignal, 'DIO:TrigWhenReady')


class PcoDetectorSimIO(ADBase):
    _html_docs = ['']
    busy = C(EpicsSignal, 'SIM:BUSY')
    dfan = C(EpicsSignal, 'SIM:Dfan')
    exposing = C(EpicsSignal, 'SIM:EXPOSING')
    set_busy = C(EpicsSignal, 'SIM:SetBusy')
    set_exp = C(EpicsSignal, 'SIM:SetExp')
    set_state = C(EpicsSignal, 'SIM:SetState')
    trig = C(EpicsSignal, 'SIM:TRIG')


class PerkinElmerDetectorCam(CamBase):
    _html_docs = ['PerkinElmerDoc.html']
    pe_acquire_gain = C(EpicsSignal, 'PEAcquireGain')
    pe_acquire_offset = C(EpicsSignal, 'PEAcquireOffset')
    pe_corrections_dir = C(EpicsSignal, 'PECorrectionsDir')
    pe_current_gain_frame = C(EpicsSignal, 'PECurrentGainFrame')
    pe_current_offset_frame = C(EpicsSignal, 'PECurrentOffsetFrame')
    pe_dwell_time = C(SignalWithRBV, 'PEDwellTime')
    pe_frame_buff_index = C(EpicsSignal, 'PEFrameBuffIndex')
    pe_gain = C(SignalWithRBV, 'PEGain')
    pe_gain_available = C(EpicsSignal, 'PEGainAvailable')
    pe_gain_file = C(EpicsSignal, 'PEGainFile')
    pe_image_number = C(EpicsSignal, 'PEImageNumber')
    pe_initialize = C(EpicsSignal, 'PEInitialize')
    pe_load_gain_file = C(EpicsSignal, 'PELoadGainFile')
    pe_load_pixel_correction = C(EpicsSignal, 'PELoadPixelCorrection')
    pe_num_frame_buffers = C(SignalWithRBV, 'PENumFrameBuffers')
    pe_num_frames_to_skip = C(SignalWithRBV, 'PENumFramesToSkip')
    pe_num_gain_frames = C(EpicsSignal, 'PENumGainFrames')
    pe_num_offset_frames = C(EpicsSignal, 'PENumOffsetFrames')
    pe_offset_available = C(EpicsSignal, 'PEOffsetAvailable')
    pe_pixel_correction_available = C(EpicsSignal,
                                      'PEPixelCorrectionAvailable')
    pe_pixel_correction_file = C(EpicsSignal, 'PEPixelCorrectionFile')
    pe_save_gain_file = C(EpicsSignal, 'PESaveGainFile')
    pe_skip_frames = C(SignalWithRBV, 'PESkipFrames')
    pe_sync_time = C(SignalWithRBV, 'PESyncTime')
    pe_system_id = C(EpicsSignal, 'PESystemID')
    pe_trigger = C(EpicsSignal, 'PETrigger')
    pe_use_gain = C(EpicsSignal, 'PEUseGain')
    pe_use_offset = C(EpicsSignal, 'PEUseOffset')
    pe_use_pixel_correction = C(EpicsSignal, 'PEUsePixelCorrection')


class PSLDetectorCam(CamBase):
    _html_docs = ['PSLDoc.html']
    file_format = C(SignalWithRBV, 'FileFormat')
    tiff_comment = C(SignalWithRBV, 'TIFFComment')


class PilatusDetectorCam(CamBase):
    _html_docs = ['pilatusDoc.html']
    alpha = C(EpicsSignal, 'Alpha')
    angle_incr = C(EpicsSignal, 'AngleIncr')
    armed = C(EpicsSignal, 'Armed')
    bad_pixel_file = C(EpicsSignal, 'BadPixelFile')
    beam_x = C(EpicsSignal, 'BeamX')
    beam_y = C(EpicsSignal, 'BeamY')
    camserver_asyn = C(EpicsSignal, 'CamserverAsyn')
    cbf_template_file = C(EpicsSignal, 'CbfTemplateFile')
    chi = C(EpicsSignal, 'Chi')
    delay_time = C(SignalWithRBV, 'DelayTime')
    det_2theta = C(EpicsSignal, 'Det2theta')
    det_dist = C(EpicsSignal, 'DetDist')
    det_v_offset = C(EpicsSignal, 'DetVOffset')
    energy_high = C(EpicsSignal, 'EnergyHigh')
    energy_low = C(EpicsSignal, 'EnergyLow')
    file_format = C(SignalWithRBV, 'FileFormat')
    filter_transm = C(EpicsSignal, 'FilterTransm')
    flat_field_file = C(EpicsSignal, 'FlatFieldFile')
    flat_field_valid = C(EpicsSignal, 'FlatFieldValid')
    flux = C(EpicsSignal, 'Flux')
    gain_menu = C(EpicsSignal, 'GainMenu')
    gap_fill = C(SignalWithRBV, 'GapFill')
    header_string = C(EpicsSignal, 'HeaderString')
    humid0 = C(EpicsSignalRO, 'Humid0_RBV')
    humid1 = C(EpicsSignalRO, 'Humid1_RBV')
    humid2 = C(EpicsSignalRO, 'Humid2_RBV')
    image_file_tmot = C(EpicsSignal, 'ImageFileTmot')
    kappa = C(EpicsSignal, 'Kappa')
    min_flat_field = C(SignalWithRBV, 'MinFlatField')
    num_bad_pixels = C(EpicsSignal, 'NumBadPixels')
    num_oscill = C(EpicsSignal, 'NumOscill')
    oscill_axis = C(EpicsSignal, 'OscillAxis')
    phi = C(EpicsSignal, 'Phi')
    pixel_cut_off = C(EpicsSignalRO, 'PixelCutOff_RBV')
    polarization = C(EpicsSignal, 'Polarization')
    start_angle = C(EpicsSignal, 'StartAngle')
    tvx_version = C(EpicsSignalRO, 'TVXVersion_RBV')
    temp0 = C(EpicsSignalRO, 'Temp0_RBV')
    temp1 = C(EpicsSignalRO, 'Temp1_RBV')
    temp2 = C(EpicsSignalRO, 'Temp2_RBV')
    threshold_apply = C(EpicsSignal, 'ThresholdApply')
    threshold_auto_apply = C(SignalWithRBV, 'ThresholdAutoApply')
    threshold_energy = C(SignalWithRBV, 'ThresholdEnergy')
    wavelength = C(EpicsSignal, 'Wavelength')


class PixiradDetectorCam(CamBase):
    _html_docs = ['PixiradDoc.html']

    auto_calibrate = C(EpicsSignal, 'AutoCalibrate')
    humidity_box = C(EpicsSignalRO, 'BoxHumidity_RBV')
    colors_collected = C(EpicsSignalRO, 'ColorsCollected_RBV')
    cooling_state = C(SignalWithRBV, 'CoolingState')
    cooling_status = C(EpicsSignalRO, 'CoolingStatus_RBV')
    dew_point = C(EpicsSignalRO, 'DewPoint_RBV')
    frame_type = C(SignalWithRBV, 'FrameType')
    hv_actual = C(EpicsSignalRO, 'HVActual_RBV')
    hv_current = C(EpicsSignalRO, 'HVCurrent_RBV')
    hv_mode = C(SignalWithRBV, 'HVMode')
    hv_state = C(SignalWithRBV, 'HVState')
    hv_value = C(SignalWithRBV, 'HVValue')
    peltier_power = C(EpicsSignalRO, 'PeltierPower_RBV')
    sync_in_polarity = C(SignalWithRBV, 'SyncInPolarity')
    sync_out_function = C(SignalWithRBV, 'SyncOutFunction')
    sync_out_polarity = C(SignalWithRBV, 'SyncOutPolarity')
    system_reset = C(EpicsSignal, 'SystemReset')

    temperature = C(SignalWithRBV, 'Temperature')
    temperature_actual = C(EpicsSignal, 'TemperatureActual')
    temperature_box = C(EpicsSignalRO, 'BoxTemperature_RBV')
    temperature_hot = C(EpicsSignalRO, 'HotTemperature_RBV')

    threshold_1_actual = C(EpicsSignalRO, 'ThresholdActual1_RBV')
    threshold_2_actual = C(EpicsSignalRO, 'ThresholdActual2_RBV')
    threshold_3_actual = C(EpicsSignalRO, 'ThresholdActual3_RBV')
    threshold_4_actual = C(EpicsSignalRO, 'ThresholdActual4_RBV')
    thresholds_actual = DDC(ad_group(EpicsSignalRO,
                                     (('threshold_1', 'ThresholdActual1_RBV'),
                                      ('threshold_2', 'ThresholdActual2_RBV'),
                                      ('threshold_3', 'ThresholdActual3_RBV'),
                                      ('threshold_4', 'ThresholdActual4_RBV'),
                                      )),
                            doc='Actual thresholds')

    threshold_1 = C(SignalWithRBV, 'Threshold1')
    threshold_2 = C(SignalWithRBV, 'Threshold2')
    threshold_3 = C(SignalWithRBV, 'Threshold3')
    threshold_4 = C(SignalWithRBV, 'Threshold4')
    thresholds = DDC(ad_group(SignalWithRBV,
                              (('threshold_1', 'Threshold1'),
                               ('threshold_2', 'Threshold2'),
                               ('threshold_3', 'Threshold3'),
                               ('threshold_4', 'Threshold4'),
                               )),
                     doc='Thresholds')

    udp_buffers_free = C(EpicsSignalRO, 'UDPBuffersFree_RBV')
    udp_buffers_max = C(EpicsSignalRO, 'UDPBuffersMax_RBV')
    udp_buffers_read = C(EpicsSignalRO, 'UDPBuffersRead_RBV')
    udp_speed = C(EpicsSignalRO, 'UDPSpeed_RBV')


class PointGreyDetectorCam(CamBase):
    _html_docs = ['PointGreyDoc.html']

    bandwidth = C(EpicsSignal, 'Bandwidth')
    binning_mode = C(SignalWithRBV, 'BinningMode')
    convert_pixel_format = C(SignalWithRBV, 'ConvertPixelFormat')
    corrupt_frames = C(EpicsSignalRO, 'CorruptFrames_RBV')
    driver_dropped = C(EpicsSignalRO, 'DriverDropped_RBV')
    dropped_frames = C(EpicsSignalRO, 'DroppedFrames_RBV')
    firmware_version = C(EpicsSignal, 'FirmwareVersion')
    format7_mode = C(SignalWithRBV, 'Format7Mode')
    frame_rate = C(SignalWithRBV, 'FrameRate')
    max_packet_size = C(EpicsSignal, 'MaxPacketSize')
    packet_delay_actual = C(EpicsSignal, 'PacketDelayActual')
    packet_delay = C(SignalWithRBV, 'PacketDelay')
    packet_size_actual = C(EpicsSignal, 'PacketSizeActual')
    packet_size = C(SignalWithRBV, 'PacketSize')
    pixel_format = C(SignalWithRBV, 'PixelFormat')
    read_status = C(EpicsSignal, 'ReadStatus')
    serial_number = C(EpicsSignal, 'SerialNumber')
    skip_frames = C(SignalWithRBV, 'SkipFrames')
    software_trigger = C(EpicsSignal, 'SoftwareTrigger')
    software_version = C(EpicsSignal, 'SoftwareVersion')
    strobe_delay = C(SignalWithRBV, 'StrobeDelay')
    strobe_duration = C(SignalWithRBV, 'StrobeDuration')
    strobe_enable = C(SignalWithRBV, 'StrobeEnable')
    strobe_polarity = C(SignalWithRBV, 'StrobePolarity')
    strobe_source = C(SignalWithRBV, 'StrobeSource')
    time_stamp_mode = C(SignalWithRBV, 'TimeStampMode')
    transmit_failed = C(EpicsSignalRO, 'TransmitFailed_RBV')
    trigger_polarity = C(SignalWithRBV, 'TriggerPolarity')
    trigger_source = C(SignalWithRBV, 'TriggerSource')
    video_mode = C(SignalWithRBV, 'VideoMode')


class ProsilicaDetectorCam(CamBase):
    _html_docs = ['prosilicaDoc.html']
    ps_bad_frame_counter = C(EpicsSignalRO, 'PSBadFrameCounter_RBV')
    ps_byte_rate = C(SignalWithRBV, 'PSByteRate')
    ps_driver_type = C(EpicsSignalRO, 'PSDriverType_RBV')
    ps_filter_version = C(EpicsSignalRO, 'PSFilterVersion_RBV')
    ps_frame_rate = C(EpicsSignalRO, 'PSFrameRate_RBV')
    ps_frames_completed = C(EpicsSignalRO, 'PSFramesCompleted_RBV')
    ps_frames_dropped = C(EpicsSignalRO, 'PSFramesDropped_RBV')
    ps_packet_size = C(EpicsSignalRO, 'PSPacketSize_RBV')
    ps_packets_erroneous = C(EpicsSignalRO, 'PSPacketsErroneous_RBV')
    ps_packets_missed = C(EpicsSignalRO, 'PSPacketsMissed_RBV')
    ps_packets_received = C(EpicsSignalRO, 'PSPacketsReceived_RBV')
    ps_packets_requested = C(EpicsSignalRO, 'PSPacketsRequested_RBV')
    ps_packets_resent = C(EpicsSignalRO, 'PSPacketsResent_RBV')
    ps_read_statistics = C(EpicsSignal, 'PSReadStatistics')
    ps_reset_timer = C(EpicsSignal, 'PSResetTimer')
    ps_timestamp_type = C(SignalWithRBV, 'PSTimestampType')
    strobe1_ctl_duration = C(SignalWithRBV, 'Strobe1CtlDuration')
    strobe1_delay = C(SignalWithRBV, 'Strobe1Delay')
    strobe1_duration = C(SignalWithRBV, 'Strobe1Duration')
    strobe1_mode = C(SignalWithRBV, 'Strobe1Mode')
    sync_in1_level = C(EpicsSignalRO, 'SyncIn1Level_RBV')
    sync_in2_level = C(EpicsSignalRO, 'SyncIn2Level_RBV')
    sync_out1_invert = C(SignalWithRBV, 'SyncOut1Invert')
    sync_out1_level = C(SignalWithRBV, 'SyncOut1Level')
    sync_out1_mode = C(SignalWithRBV, 'SyncOut1Mode')
    sync_out2_invert = C(SignalWithRBV, 'SyncOut2Invert')
    sync_out2_level = C(SignalWithRBV, 'SyncOut2Level')
    sync_out2_mode = C(SignalWithRBV, 'SyncOut2Mode')
    sync_out3_invert = C(SignalWithRBV, 'SyncOut3Invert')
    sync_out3_level = C(SignalWithRBV, 'SyncOut3Level')
    sync_out3_mode = C(SignalWithRBV, 'SyncOut3Mode')
    trigger_delay = C(SignalWithRBV, 'TriggerDelay')
    trigger_event = C(SignalWithRBV, 'TriggerEvent')
    trigger_overlap = C(SignalWithRBV, 'TriggerOverlap')
    trigger_software = C(EpicsSignal, 'TriggerSoftware')


class PvcamDetectorCam(CamBase):
    _html_docs = ['pvcamDoc.html']
    bit_depth = C(EpicsSignalRO, 'BitDepth_RBV')
    camera_firmware_vers = C(EpicsSignalRO, 'CameraFirmwareVers_RBV')
    chip_height = C(EpicsSignalRO, 'ChipHeight_RBV')
    chip_name = C(EpicsSignalRO, 'ChipName_RBV')
    chip_width = C(EpicsSignalRO, 'ChipWidth_RBV')
    close_delay = C(SignalWithRBV, 'CloseDelay')
    detector_mode = C(SignalWithRBV, 'DetectorMode')
    detector_selected = C(SignalWithRBV, 'DetectorSelected')
    dev_drv_vers = C(EpicsSignalRO, 'DevDrvVers_RBV')
    frame_transfer_capable = C(EpicsSignalRO, 'FrameTransferCapable_RBV')
    full_well_capacity = C(EpicsSignalRO, 'FullWellCapacity_RBV')
    gain_index = C(SignalWithRBV, 'GainIndex')
    head_ser_num = C(EpicsSignalRO, 'HeadSerNum_RBV')
    initialize = C(SignalWithRBV, 'Initialize')
    max_gain_index = C(EpicsSignalRO, 'MaxGainIndex_RBV')
    max_set_temperature = C(EpicsSignal, 'MaxSetTemperature')
    max_shutter_close_delay = C(EpicsSignalRO, 'MaxShutterCloseDelay_RBV')
    max_shutter_open_delay = C(EpicsSignalRO, 'MaxShutterOpenDelay_RBV')
    measured_temperature = C(EpicsSignalRO, 'MeasuredTemperature_RBV')
    min_set_temperature = C(EpicsSignal, 'MinSetTemperature')
    min_shutter_close_delay = C(EpicsSignalRO, 'MinShutterCloseDelay_RBV')
    min_shutter_open_delay = C(EpicsSignalRO, 'MinShutterOpenDelay_RBV')
    num_parallel_pixels = C(EpicsSignalRO, 'NumParallelPixels_RBV')
    num_ports = C(EpicsSignalRO, 'NumPorts_RBV')
    num_serial_pixels = C(EpicsSignalRO, 'NumSerialPixels_RBV')
    num_speed_table_entries = C(EpicsSignalRO, 'NumSpeedTableEntries_RBV')
    open_delay = C(SignalWithRBV, 'OpenDelay')
    pcifw_vers = C(EpicsSignalRO, 'PCIFWVers_RBV')
    pv_cam_vers = C(EpicsSignalRO, 'PVCamVers_RBV')
    pixel_parallel_dist = C(EpicsSignalRO, 'PixelParallelDist_RBV')
    pixel_parallel_size = C(EpicsSignalRO, 'PixelParallelSize_RBV')
    pixel_serial_dist = C(EpicsSignalRO, 'PixelSerialDist_RBV')
    pixel_serial_size = C(EpicsSignalRO, 'PixelSerialSize_RBV')
    pixel_time = C(EpicsSignalRO, 'PixelTime_RBV')
    post_mask = C(EpicsSignalRO, 'PostMask_RBV')
    post_scan = C(EpicsSignalRO, 'PostScan_RBV')
    pre_mask = C(EpicsSignalRO, 'PreMask_RBV')
    pre_scan = C(EpicsSignalRO, 'PreScan_RBV')
    serial_num = C(EpicsSignalRO, 'SerialNum_RBV')
    set_temperature = C(SignalWithRBV, 'SetTemperature')
    slot1_cam = C(EpicsSignalRO, 'Slot1Cam_RBV')
    slot2_cam = C(EpicsSignalRO, 'Slot2Cam_RBV')
    slot3_cam = C(EpicsSignalRO, 'Slot3Cam_RBV')
    speed_table_index = C(SignalWithRBV, 'SpeedTableIndex')
    trigger_edge = C(SignalWithRBV, 'TriggerEdge')


class RoperDetectorCam(CamBase):
    _html_docs = ['RoperDoc.html']
    auto_data_type = C(SignalWithRBV, 'AutoDataType')
    comment1 = C(SignalWithRBV, 'Comment1')
    comment2 = C(SignalWithRBV, 'Comment2')
    comment3 = C(SignalWithRBV, 'Comment3')
    comment4 = C(SignalWithRBV, 'Comment4')
    comment5 = C(SignalWithRBV, 'Comment5')
    file_format = C(SignalWithRBV, 'FileFormat')
    num_acquisitions = C(SignalWithRBV, 'NumAcquisitions')
    num_acquisitions_counter = C(EpicsSignalRO, 'NumAcquisitionsCounter_RBV')
    roper_shutter_mode = C(SignalWithRBV, 'RoperShutterMode')


class URLDetectorCam(CamBase):
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

    url_select = C(EpicsSignal, 'URLSelect')
    url_seq = C(EpicsSignal, 'URLSeq')
    url = C(EpicsSignalRO, 'URL_RBV')
