import logging

from ..utils import enum
from .base import (ADBase, ADComponent as ADCpt, ad_group,
                   EpicsSignalWithRBV as SignalWithRBV)
from ..signal import (EpicsSignalRO, EpicsSignal)
from ..device import DynamicDeviceComponent as DDC

# Import FileBase class for cameras that use File PVs in their drivers
from .plugins import FileBase

logger = logging.getLogger(__name__)


__all__ = ['CamBase',
           'AdscDetectorCam',
           'Andor3DetectorCam',
           'AndorDetectorCam',
           'BrukerDetectorCam',
           'DexelaDetectorCam',
           'EmergentVisionDetectorCam',
           'EigerDetectorCam',
           'FirewireLinDetectorCam',
           'FirewireWinDetectorCam',
           'GreatEyesDetectorCam',
           'Lambda750kCam',
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
           'Xspress3DetectorCam'
           ]


class CamBase(ADBase):
    _default_configuration_attrs = (ADBase._default_configuration_attrs +
                                    ('acquire_time', 'acquire_period',
                                     'model', 'num_exposures', 'image_mode',
                                     'num_images',
                                     'manufacturer', 'trigger_mode'))

    ImageMode = enum(SINGLE=0, MULTIPLE=1, CONTINUOUS=2)

    # Shared among all cams and plugins
    array_counter = ADCpt(SignalWithRBV, 'ArrayCounter')
    array_rate = ADCpt(EpicsSignalRO, 'ArrayRate_RBV')
    asyn_io = ADCpt(EpicsSignal, 'AsynIO')

    nd_attributes_file = ADCpt(EpicsSignal, 'NDAttributesFile', string=True)
    pool_alloc_buffers = ADCpt(EpicsSignalRO, 'PoolAllocBuffers')
    pool_free_buffers = ADCpt(EpicsSignalRO, 'PoolFreeBuffers')
    pool_max_buffers = ADCpt(EpicsSignalRO, 'PoolMaxBuffers')
    pool_max_mem = ADCpt(EpicsSignalRO, 'PoolMaxMem')
    pool_used_buffers = ADCpt(EpicsSignalRO, 'PoolUsedBuffers')
    pool_used_mem = ADCpt(EpicsSignalRO, 'PoolUsedMem')
    port_name = ADCpt(EpicsSignalRO, 'PortName_RBV', string=True)

    # Cam-specific
    acquire = ADCpt(SignalWithRBV, 'Acquire')
    acquire_period = ADCpt(SignalWithRBV, 'AcquirePeriod')
    acquire_time = ADCpt(SignalWithRBV, 'AcquireTime')

    array_callbacks = ADCpt(SignalWithRBV, 'ArrayCallbacks')
    array_size = DDC(ad_group(EpicsSignalRO,
                              (('array_size_z', 'ArraySizeZ_RBV'),
                               ('array_size_y', 'ArraySizeY_RBV'),
                               ('array_size_x', 'ArraySizeX_RBV'))),
                     doc='Size of the array in the XYZ dimensions')

    array_size_bytes = ADCpt(EpicsSignalRO, 'ArraySize_RBV')
    bin_x = ADCpt(SignalWithRBV, 'BinX')
    bin_y = ADCpt(SignalWithRBV, 'BinY')
    color_mode = ADCpt(SignalWithRBV, 'ColorMode')
    data_type = ADCpt(SignalWithRBV, 'DataType')
    detector_state = ADCpt(EpicsSignalRO, 'DetectorState_RBV')
    frame_type = ADCpt(SignalWithRBV, 'FrameType')
    gain = ADCpt(SignalWithRBV, 'Gain')

    image_mode = ADCpt(SignalWithRBV, 'ImageMode')
    manufacturer = ADCpt(EpicsSignalRO, 'Manufacturer_RBV')

    max_size = DDC(ad_group(EpicsSignalRO,
                            (('max_size_x', 'MaxSizeX_RBV'),
                             ('max_size_y', 'MaxSizeY_RBV'))),
                   doc='Maximum sensor size in the XY directions')

    min_x = ADCpt(SignalWithRBV, 'MinX')
    min_y = ADCpt(SignalWithRBV, 'MinY')
    model = ADCpt(EpicsSignalRO, 'Model_RBV')

    num_exposures = ADCpt(SignalWithRBV, 'NumExposures')
    num_exposures_counter = ADCpt(EpicsSignalRO, 'NumExposuresCounter_RBV')
    num_images = ADCpt(SignalWithRBV, 'NumImages')
    num_images_counter = ADCpt(EpicsSignalRO, 'NumImagesCounter_RBV')

    read_status = ADCpt(EpicsSignal, 'ReadStatus')
    reverse = DDC(ad_group(SignalWithRBV,
                           (('reverse_x', 'ReverseX'),
                            ('reverse_y', 'ReverseY'))
                           ))

    shutter_close_delay = ADCpt(SignalWithRBV, 'ShutterCloseDelay')
    shutter_close_epics = ADCpt(EpicsSignal, 'ShutterCloseEPICS')
    shutter_control = ADCpt(SignalWithRBV, 'ShutterControl')
    shutter_control_epics = ADCpt(EpicsSignal, 'ShutterControlEPICS')
    shutter_fanout = ADCpt(EpicsSignal, 'ShutterFanout')
    shutter_mode = ADCpt(SignalWithRBV, 'ShutterMode')
    shutter_open_delay = ADCpt(SignalWithRBV, 'ShutterOpenDelay')
    shutter_open_epics = ADCpt(EpicsSignal, 'ShutterOpenEPICS')
    shutter_status_epics = ADCpt(EpicsSignalRO, 'ShutterStatusEPICS_RBV')
    shutter_status = ADCpt(EpicsSignalRO, 'ShutterStatus_RBV')

    size = DDC(ad_group(SignalWithRBV,
                        (('size_x', 'SizeX'),
                         ('size_y', 'SizeY'))
                        ))

    status_message = ADCpt(EpicsSignalRO, 'StatusMessage_RBV', string=True)
    string_from_server = ADCpt(EpicsSignalRO, 'StringFromServer_RBV', string=True)
    string_to_server = ADCpt(EpicsSignalRO, 'StringToServer_RBV', string=True)
    temperature = ADCpt(SignalWithRBV, 'Temperature')
    temperature_actual = ADCpt(EpicsSignal, 'TemperatureActual')
    time_remaining = ADCpt(EpicsSignalRO, 'TimeRemaining_RBV')
    trigger_mode = ADCpt(SignalWithRBV, 'TriggerMode')


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

    noise = ADCpt(SignalWithRBV, 'Noise')
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

    peak_variation = ADCpt(SignalWithRBV, 'PeakVariation')
    peak_width = DDC(ad_group(SignalWithRBV,
                              (('peak_width_x', 'PeakWidthX'),
                               ('peak_width_y', 'PeakWidthY'))),
                     doc='Peak width in XY')

    reset = ADCpt(SignalWithRBV, 'Reset')
    sim_mode = ADCpt(SignalWithRBV, 'SimMode')


class AdscDetectorCam(CamBase):
    _html_docs = ['adscDoc.html']
    adsc_2theta = ADCpt(SignalWithRBV, 'ADSC2Theta')
    adsc_adc = ADCpt(SignalWithRBV, 'ADSCAdc')
    adsc_axis = ADCpt(SignalWithRBV, 'ADSCAxis')
    adsc_beam_x = ADCpt(SignalWithRBV, 'ADSCBeamX')
    adsc_beam_y = ADCpt(SignalWithRBV, 'ADSCBeamY')
    adsc_dezingr = ADCpt(SignalWithRBV, 'ADSCDezingr')
    adsc_distance = ADCpt(SignalWithRBV, 'ADSCDistnce')
    adsc_im_width = ADCpt(SignalWithRBV, 'ADSCImWidth')
    adsc_im_xform = ADCpt(SignalWithRBV, 'ADSCImXform')
    adsc_kappa = ADCpt(SignalWithRBV, 'ADSCKappa')
    adsc_last_error = ADCpt(EpicsSignal, 'ADSCLastError')
    adsc_last_image = ADCpt(EpicsSignal, 'ADSCLastImage')
    adsc_omega = ADCpt(SignalWithRBV, 'ADSCOmega')
    adsc_phi = ADCpt(SignalWithRBV, 'ADSCPhi')
    adsc_raw = ADCpt(SignalWithRBV, 'ADSCRaw')
    adsc_read_conditn = ADCpt(EpicsSignal, 'ADSCReadConditn')
    adsc_reus_drk = ADCpt(SignalWithRBV, 'ADSCReusDrk')
    adsc_soft_reset = ADCpt(EpicsSignal, 'ADSCSoftReset')
    adsc_state = ADCpt(EpicsSignal, 'ADSCState')
    adsc_status = ADCpt(EpicsSignal, 'ADSCStatus')
    adsc_stp_ex_retry_count = ADCpt(EpicsSignal, 'ADSCStpExRtryCt')
    adsc_str_drks = ADCpt(SignalWithRBV, 'ADSCStrDrks')
    adsc_wavelen = ADCpt(SignalWithRBV, 'ADSCWavelen')

    bin_x_changed = ADCpt(EpicsSignal, 'BinXChanged')
    bin_y_changed = ADCpt(EpicsSignal, 'BinYChanged')
    ext_trig_ctl = ADCpt(EpicsSignal, 'ExSwTrCtl')
    ext_trig_ctl_rsp = ADCpt(EpicsSignal, 'ExSwTrCtlRsp')
    ext_trig_ok_to_exp = ADCpt(EpicsSignal, 'ExSwTrOkToExp')


class AndorDetectorCam(CamBase):
    _html_docs = ['andorDoc.html']
    andor_adc_speed = ADCpt(SignalWithRBV, 'AndorADCSpeed')
    andor_accumulate_period = ADCpt(SignalWithRBV, 'AndorAccumulatePeriod')
    andor_cooler = ADCpt(SignalWithRBV, 'AndorCooler')
    andor_message = ADCpt(EpicsSignalRO, 'AndorMessage_RBV')
    andor_pre_amp_gain = ADCpt(SignalWithRBV, 'AndorPreAmpGain')
    andor_shutter_ex_ttl = ADCpt(EpicsSignal, 'AndorShutterExTTL')
    andor_shutter_mode = ADCpt(EpicsSignal, 'AndorShutterMode')
    andor_temp_status = ADCpt(EpicsSignalRO, 'AndorTempStatus_RBV')
    file_format = ADCpt(SignalWithRBV, 'FileFormat')
    pal_file_path = ADCpt(SignalWithRBV, 'PALFilePath')


class Andor3DetectorCam(CamBase):
    _html_docs = ['andor3Doc.html']
    a3_binning = ADCpt(SignalWithRBV, 'A3Binning')
    a3_shutter_mode = ADCpt(SignalWithRBV, 'A3ShutterMode')
    controller_id = ADCpt(EpicsSignal, 'ControllerID')
    fan_speed = ADCpt(SignalWithRBV, 'FanSpeed')
    firmware_version = ADCpt(EpicsSignal, 'FirmwareVersion')
    frame_rate = ADCpt(SignalWithRBV, 'FrameRate')
    full_aoic_ontrol = ADCpt(EpicsSignal, 'FullAOIControl')
    noise_filter = ADCpt(SignalWithRBV, 'NoiseFilter')
    overlap = ADCpt(SignalWithRBV, 'Overlap')
    pixel_encoding = ADCpt(SignalWithRBV, 'PixelEncoding')
    pre_amp_gain = ADCpt(SignalWithRBV, 'PreAmpGain')
    readout_rate = ADCpt(SignalWithRBV, 'ReadoutRate')
    readout_time = ADCpt(EpicsSignal, 'ReadoutTime')
    sensor_cooling = ADCpt(SignalWithRBV, 'SensorCooling')
    serial_number = ADCpt(EpicsSignal, 'SerialNumber')
    software_trigger = ADCpt(EpicsSignal, 'SoftwareTrigger')
    software_version = ADCpt(EpicsSignal, 'SoftwareVersion')
    temp_control = ADCpt(SignalWithRBV, 'TempControl')
    temp_status = ADCpt(EpicsSignalRO, 'TempStatus_RBV')
    transfer_rate = ADCpt(EpicsSignal, 'TransferRate')


class BrukerDetectorCam(CamBase):
    _html_docs = ['BrukerDoc.html']
    bis_asyn = ADCpt(EpicsSignal, 'BISAsyn')
    bis_status = ADCpt(EpicsSignal, 'BISStatus')
    file_format = ADCpt(SignalWithRBV, 'FileFormat')
    num_darks = ADCpt(SignalWithRBV, 'NumDarks')
    read_sfrm_timeout = ADCpt(EpicsSignal, 'ReadSFRMTimeout')


class DexelaDetectorCam(CamBase):
    acquire_gain = ADCpt(EpicsSignal, 'DEXAcquireGain')
    acquire_offset = ADCpt(EpicsSignal, 'DEXAcquireOffset')
    binning_mode = ADCpt(SignalWithRBV, 'DEXBinningMode')
    corrections_dir = ADCpt(EpicsSignal, 'DEXCorrectionsDir', string=True)
    current_gain_frame = ADCpt(EpicsSignal, 'DEXCurrentGainFrame')
    current_offset_frame = ADCpt(EpicsSignal, 'DEXCurrentOffsetFrame')
    defect_map_available = ADCpt(EpicsSignal, 'DEXDefectMapAvailable')
    defect_map_file = ADCpt(EpicsSignal, 'DEXDefectMapFile', string=True)
    full_well_mode = ADCpt(SignalWithRBV, 'DEXFullWellMode')
    gain_available = ADCpt(EpicsSignal, 'DEXGainAvailable')
    gain_file = ADCpt(EpicsSignal, 'DEXGainFile', string=True)
    load_defect_map_file = ADCpt(EpicsSignal, 'DEXLoadDefectMapFile')
    load_gain_file = ADCpt(EpicsSignal, 'DEXLoadGainFile')
    load_offset_file = ADCpt(EpicsSignal, 'DEXLoadOffsetFile')
    num_gain_frames = ADCpt(EpicsSignal, 'DEXNumGainFrames')
    num_offset_frames = ADCpt(EpicsSignal, 'DEXNumOffsetFrames')
    offset_available = ADCpt(EpicsSignal, 'DEXOffsetAvailable')
    offset_constant = ADCpt(SignalWithRBV, 'DEXOffsetConstant')
    offset_file = ADCpt(EpicsSignal, 'DEXOffsetFile', string=True)
    save_gain_file = ADCpt(EpicsSignal, 'DEXSaveGainFile')
    save_offset_file = ADCpt(EpicsSignal, 'DEXSaveOffsetFile')
    serial_number = ADCpt(EpicsSignal, 'DEXSerialNumber')
    software_trigger = ADCpt(EpicsSignal, 'DEXSoftwareTrigger')
    use_defect_map = ADCpt(EpicsSignal, 'DEXUseDefectMap')
    use_gain = ADCpt(EpicsSignal, 'DEXUseGain')
    use_offset = ADCpt(EpicsSignal, 'DEXUseOffset')


class EmergentVisionDetectorCam(CamBase):

    _html_docs = ['EVTDoc.html']
    _default_configuration_attrs = (CamBase._default_configuration_attrs +
                                    ('pixel_format', 'auto_gain', 'framerate'))

    pixel_format = ADCpt(SignalWithRBV, 'EVTPixelFormat')
    framerate = ADCpt(SignalWithRBV, 'EVTFramerate')
    offset_x = ADCpt(SignalWithRBV, 'EVTOffsetX')
    offset_y = ADCpt(SignalWithRBV, 'EVTOffsetY')
    buff_mode = ADCpt(SignalWithRBV, 'EVTBuffMode')
    buff_num = ADCpt(SignalWithRBV, 'EVTBuffNum')
    packet_size = ADCpt(SignalWithRBV, 'EVTPacketSize')
    lut_enable = ADCpt(SignalWithRBV, 'EVTLUTEnable')
    auto_gain = ADCpt(SignalWithRBV, 'EVTAutoGain')


class EigerDetectorCam(CamBase, FileBase):

    _html_docs = ['EigerDoc.html']
    _default_configuration_attrs = (
        CamBase._default_configuration_attrs +
        ('shutter_mode', 'num_triggers', 'beam_center_x', 'beam_center_y',
         'wavelength', 'det_distance', 'threshold_energy', 'photon_energy', 'manual_trigger',
         'special_trigger_button'))

    shutter_mode = ADCpt(SignalWithRBV, 'ShutterMode')
    num_triggers = ADCpt(SignalWithRBV, 'NumTriggers')
    beam_center_x = ADCpt(SignalWithRBV, 'BeamX')
    beam_center_y = ADCpt(SignalWithRBV, 'BeamY')
    wavelength = ADCpt(SignalWithRBV, 'Wavelength')
    det_distance = ADCpt(SignalWithRBV, 'DetDist')
    threshold_energy = ADCpt(SignalWithRBV, 'ThresholdEnergy')
    photon_energy = ADCpt(SignalWithRBV, 'PhotonEnergy')
    manual_trigger = ADCpt(SignalWithRBV, 'ManualTrigger')  # the checkbox
    special_trigger_button = ADCpt(EpicsSignal, 'Trigger')  # the button next to 'Start' and 'Stop'
    trigger_exposure = ADCpt(SignalWithRBV, 'TriggerExposure')
    data_source = ADCpt(SignalWithRBV, 'DataSource')
    stream_decompress = ADCpt(SignalWithRBV, 'StreamDecompress')
    fw_enable = ADCpt(SignalWithRBV, 'FWEnable')
    fw_clear = ADCpt(EpicsSignal, 'FWClear')
    fw_compression = ADCpt(SignalWithRBV, 'FWCompression')
    fw_name_pattern = ADCpt(SignalWithRBV, 'FWNamePattern', string=True)
    fw_num_images_per_file = ADCpt(SignalWithRBV, 'FWNImagesPerFile')
    fw_autoremove = ADCpt(SignalWithRBV, 'FWAutoRemove')
    fw_free = ADCpt(EpicsSignalRO, 'FWFree_RBV')
    fw_state = ADCpt(EpicsSignalRO, 'FWState_RBV')
    description = ADCpt(EpicsSignalRO, 'Description_RBV', string=True)
    sensor_thickness = ADCpt(EpicsSignalRO, 'SensorThickness_RBV')
    sensor_material = ADCpt(EpicsSignalRO, 'SensorMaterial_RBV')
    count_cutoff = ADCpt(EpicsSignalRO, 'CountCutoff_RBV')
    x_pixel_size = ADCpt(EpicsSignalRO, 'XPixelSize_RBV')
    y_pixel_size = ADCpt(EpicsSignalRO, 'YPixelSize_RBV')
    roi_mode = ADCpt(SignalWithRBV, 'ROIMode')
    dead_time = ADCpt(EpicsSignalRO, 'DeadTime_RBV')
    compression_algo = ADCpt(SignalWithRBV, 'CompressionAlgo')
    stream_enable = ADCpt(SignalWithRBV, 'StreamEnable')
    stream_dropped = ADCpt(EpicsSignalRO, 'StreamDropped_RBV')
    stream_state = ADCpt(EpicsSignalRO, 'StreamState_RBV')
    stream_hdr_detail = ADCpt(SignalWithRBV, 'StreamHdrDetail')
    stream_hdr_appendix = ADCpt(EpicsSignal, 'StreamHdrAppendix')
    stream_img_appendix = ADCpt(EpicsSignal, 'StreamImgAppendix')
    save_files = ADCpt(SignalWithRBV, 'SaveFiles')
    file_owner = ADCpt(SignalWithRBV, 'FileOwner')
    file_owner_grp = ADCpt(SignalWithRBV, 'FileOwnerGrp')
    file_perms = ADCpt(EpicsSignal, 'FilePerms')
    flatfield_applied = ADCpt(SignalWithRBV, 'FlatfieldApplied')
    sequence_id = ADCpt(EpicsSignalRO, 'SequenceId')
    photon_energy = ADCpt(SignalWithRBV, 'PhotonEnergy')
    armed = ADCpt(EpicsSignalRO, 'Armed')
    chi_start = ADCpt(SignalWithRBV, 'ChiStart')
    chi_incr = ADCpt(SignalWithRBV, 'ChiIncr')
    kappa_start = ADCpt(SignalWithRBV, 'KappaStart')
    kappa_incr = ADCpt(SignalWithRBV, 'KappaIncr')
    omega_start = ADCpt(SignalWithRBV, 'OmegaStart')
    omega_incr = ADCpt(SignalWithRBV, 'OmegaIncr')
    phi_start = ADCpt(SignalWithRBV, 'PhiStart')
    phi_incr = ADCpt(SignalWithRBV, 'PhiIncr')
    two_theta_start = ADCpt(SignalWithRBV, 'TwoThetaStart')
    two_theta_incr = ADCpt(SignalWithRBV, 'TwoThetaIncr')
    monitor_enable = ADCpt(SignalWithRBV, 'MonitorEnable')
    monitor_timeout = ADCpt(SignalWithRBV, 'MonitorTimeout')
    monitor_state = ADCpt(EpicsSignalRO, 'MonitorState_RBV')
    temp_0 = ADCpt(EpicsSignalRO, 'Temp0_RBV')
    humid_0 = ADCpt(EpicsSignalRO, 'Humid0_RBV')
    link_0 = ADCpt(EpicsSignalRO, 'Link0_RBV')
    link_1 = ADCpt(EpicsSignalRO, 'Link1_RBV')
    link_2 = ADCpt(EpicsSignalRO, 'Link2_RBV')
    link_3 = ADCpt(EpicsSignalRO, 'Link3_RBV')
    dcu_buff_free = ADCpt(EpicsSignalRO, 'DCUBufferFree_RBV')


class FirewireLinDetectorCam(CamBase):
    _html_docs = []

    bandwidth = ADCpt(EpicsSignal, 'BANDWIDTH')
    fanout_disable = ADCpt(EpicsSignal, 'FanoutDis')
    framerate_max = ADCpt(SignalWithRBV, 'FR')
    is_fixed_mode = ADCpt(EpicsSignal, 'IsFixedMode')
    video_mode = ADCpt(EpicsSignal, 'VIDEOMODE')


class FirewireWinDetectorCam(CamBase):
    _html_docs = ['FirewireWinDoc.html']
    colorcode = ADCpt(SignalWithRBV, 'COLORCODE')
    current_colorcode = ADCpt(EpicsSignal, 'CURRENT_COLORCODE')
    current_format = ADCpt(EpicsSignal, 'CURRENT_FORMAT')
    current_mode = ADCpt(EpicsSignal, 'CURRENT_MODE')
    current_rate = ADCpt(EpicsSignal, 'CURRENT_RATE')
    dropped_frames = ADCpt(SignalWithRBV, 'DROPPED_FRAMES')
    format_ = ADCpt(SignalWithRBV, 'FORMAT')
    frame_rate = ADCpt(SignalWithRBV, 'FR')
    mode = ADCpt(SignalWithRBV, 'MODE')
    readout_time = ADCpt(SignalWithRBV, 'READOUT_TIME')


class GreatEyesDetectorCam(CamBase):
    _html_docs = []
    adc_speed = ADCpt(SignalWithRBV, 'GreatEyesAdcSpeed')
    capacity = ADCpt(SignalWithRBV, 'GreatEyesCapacity')
    enable_cooling = ADCpt(SignalWithRBV, 'GreatEyesEnableCooling')
    gain = ADCpt(SignalWithRBV, 'GreatEyesGain')
    hot_side_temp = ADCpt(EpicsSignal, 'GreatEyesHotSideTemp')
    readout_dir = ADCpt(SignalWithRBV, 'GreatEyesReadoutDir')
    sync = ADCpt(SignalWithRBV, 'GreatEyesSync')


class Lambda750kCam(CamBase):
    """
    support for X-Spectrum Lambda 750K detector

    https://x-spectrum.de/products/lambda-350k750k/
    """
    _html_docs = ['Lambda750kCam.html']

    config_file_path = ADCpt(EpicsSignal, 'ConfigFilePath')
    firmware_version = ADCpt(EpicsSignalRO, 'FirmwareVersion_RBV')
    operating_mode = ADCpt(SignalWithRBV, 'OperatingMode')
    serial_number = ADCpt(EpicsSignalRO, 'SerialNumber_RBV')
    temperature = ADCpt(SignalWithRBV, 'Temperature')


class LightFieldDetectorCam(CamBase):
    _html_docs = ['LightFieldDoc.html']

    aux_delay = ADCpt(SignalWithRBV, 'LFAuxDelay')
    aux_width = ADCpt(SignalWithRBV, 'LFAuxWidth')
    background_enable = ADCpt(SignalWithRBV, 'LFBackgroundEnable')
    background_file = ADCpt(SignalWithRBV, 'LFBackgroundFile')
    background_full_file = ADCpt(EpicsSignalRO, 'LFBackgroundFullFile_RBV')
    background_path = ADCpt(SignalWithRBV, 'LFBackgroundPath')
    entrance_width = ADCpt(SignalWithRBV, 'LFEntranceWidth')
    exit_port = ADCpt(SignalWithRBV, 'LFExitPort')
    experiment_name = ADCpt(SignalWithRBV, 'LFExperimentName')
    file_name = ADCpt(EpicsSignalRO, 'LFFileName_RBV')
    file_path = ADCpt(EpicsSignalRO, 'LFFilePath_RBV')
    lf_gain = ADCpt(SignalWithRBV, 'LFGain')
    gating_mode = ADCpt(SignalWithRBV, 'LFGatingMode')
    grating = ADCpt(SignalWithRBV, 'LFGrating')
    grating_wavelength = ADCpt(SignalWithRBV, 'LFGratingWavelength')
    image_mode = ADCpt(SignalWithRBV, 'ImageMode')
    intensifier_enable = ADCpt(SignalWithRBV, 'LFIntensifierEnable')
    intensifier_gain = ADCpt(SignalWithRBV, 'LFIntensifierGain')
    num_accumulations = ADCpt(SignalWithRBV, 'NumAccumulations')
    ready_to_run = ADCpt(EpicsSignal, 'LFReadyToRun')
    rep_gate_delay = ADCpt(SignalWithRBV, 'LFRepGateDelay')
    rep_gate_width = ADCpt(SignalWithRBV, 'LFRepGateWidth')
    seq_end_gate_delay = ADCpt(SignalWithRBV, 'LFSeqEndGateDelay')
    seq_end_gate_width = ADCpt(SignalWithRBV, 'LFSeqEndGateWidth')
    seq_start_gate_delay = ADCpt(SignalWithRBV, 'LFSeqStartGateDelay')
    seq_start_gate_width = ADCpt(SignalWithRBV, 'LFSeqStartGateWidth')
    lf_shutter_mode = ADCpt(SignalWithRBV, 'LFShutterMode')
    sync_master2_delay = ADCpt(SignalWithRBV, 'LFSyncMaster2Delay')
    sync_master_enable = ADCpt(SignalWithRBV, 'LFSyncMasterEnable')
    trigger_frequency = ADCpt(SignalWithRBV, 'LFTriggerFrequency')
    update_experiments = ADCpt(EpicsSignal, 'LFUpdateExperiments')


class Mar345DetectorCam(CamBase):
    _html_docs = ['Mar345Doc.html']
    abort = ADCpt(SignalWithRBV, 'Abort')
    change_mode = ADCpt(SignalWithRBV, 'ChangeMode')
    erase = ADCpt(SignalWithRBV, 'Erase')
    erase_mode = ADCpt(SignalWithRBV, 'EraseMode')
    file_format = ADCpt(SignalWithRBV, 'FileFormat')
    num_erase = ADCpt(SignalWithRBV, 'NumErase')
    num_erased = ADCpt(EpicsSignalRO, 'NumErased_RBV')
    scan_resolution = ADCpt(SignalWithRBV, 'ScanResolution')
    scan_size = ADCpt(SignalWithRBV, 'ScanSize')
    mar_server_asyn = ADCpt(EpicsSignal, 'marServerAsyn')


class MarCCDDetectorCam(CamBase):
    _html_docs = ['MarCCDDoc.html']
    beam_x = ADCpt(EpicsSignal, 'BeamX')
    beam_y = ADCpt(EpicsSignal, 'BeamY')
    dataset_comments = ADCpt(EpicsSignal, 'DatasetComments')
    detector_distance = ADCpt(EpicsSignal, 'DetectorDistance')
    file_comments = ADCpt(EpicsSignal, 'FileComments')
    file_format = ADCpt(SignalWithRBV, 'FileFormat')
    frame_shift = ADCpt(SignalWithRBV, 'FrameShift')
    mar_acquire_status = ADCpt(EpicsSignalRO, 'MarAcquireStatus_RBV')
    mar_correct_status = ADCpt(EpicsSignalRO, 'MarCorrectStatus_RBV')
    mar_dezinger_status = ADCpt(EpicsSignalRO, 'MarDezingerStatus_RBV')
    mar_readout_status = ADCpt(EpicsSignalRO, 'MarReadoutStatus_RBV')
    mar_state = ADCpt(EpicsSignalRO, 'MarState_RBV')
    mar_status = ADCpt(EpicsSignalRO, 'MarStatus_RBV')
    mar_writing_status = ADCpt(EpicsSignalRO, 'MarWritingStatus_RBV')
    overlap_mode = ADCpt(SignalWithRBV, 'OverlapMode')
    read_tiff_timeout = ADCpt(EpicsSignal, 'ReadTiffTimeout')
    rotation_axis = ADCpt(EpicsSignal, 'RotationAxis')
    rotation_range = ADCpt(EpicsSignal, 'RotationRange')
    stability = ADCpt(SignalWithRBV, 'Stability')
    start_phi = ADCpt(EpicsSignal, 'StartPhi')
    two_theta = ADCpt(EpicsSignal, 'TwoTheta')
    wavelength = ADCpt(EpicsSignal, 'Wavelength')
    mar_server_asyn = ADCpt(EpicsSignal, 'marServerAsyn')


class PcoDetectorCam(CamBase):
    _html_docs = ['']
    adc_mode = ADCpt(SignalWithRBV, 'ADC_MODE')
    arm_mode = ADCpt(SignalWithRBV, 'ARM_MODE')
    bit_alignment = ADCpt(SignalWithRBV, 'BIT_ALIGNMENT')
    camera_setup = ADCpt(SignalWithRBV, 'CAMERA_SETUP')
    cam_ram_use = ADCpt(EpicsSignalRO, 'CAM_RAM_USE_RBV')
    delay_time = ADCpt(SignalWithRBV, 'DELAY_TIME')
    elec_temp = ADCpt(EpicsSignalRO, 'ELEC_TEMP_RBV')
    exposure_base = ADCpt(EpicsSignalRO, 'EXPOSUREBASE_RBV')
    pco_acquire_mode = ADCpt(SignalWithRBV, 'ACQUIRE_MODE')
    pco_image_number = ADCpt(EpicsSignalRO, 'IMAGE_NUMBER_RBV')
    pix_rate = ADCpt(SignalWithRBV, 'PIX_RATE')
    power_temp = ADCpt(EpicsSignalRO, 'POWER_TEMP_RBV')
    recorder_mode = ADCpt(SignalWithRBV, 'RECORDER_MODE')
    storage_mode = ADCpt(SignalWithRBV, 'STORAGE_MODE')
    timestamp_mode = ADCpt(SignalWithRBV, 'TIMESTAMP_MODE')


class PcoDetectorIO(ADBase):
    _html_docs = ['']
    busy = ADCpt(EpicsSignal, 'DIO:BUSY')
    capture = ADCpt(EpicsSignal, 'DIO:CAPTURE')
    exposing = ADCpt(EpicsSignal, 'DIO:EXPOSING')
    ready = ADCpt(EpicsSignal, 'DIO:READY')
    trig = ADCpt(EpicsSignal, 'DIO:TRIG')
    trig_when_ready = ADCpt(EpicsSignal, 'DIO:TrigWhenReady')


class PcoDetectorSimIO(ADBase):
    _html_docs = ['']
    busy = ADCpt(EpicsSignal, 'SIM:BUSY')
    dfan = ADCpt(EpicsSignal, 'SIM:Dfan')
    exposing = ADCpt(EpicsSignal, 'SIM:EXPOSING')
    set_busy = ADCpt(EpicsSignal, 'SIM:SetBusy')
    set_exp = ADCpt(EpicsSignal, 'SIM:SetExp')
    set_state = ADCpt(EpicsSignal, 'SIM:SetState')
    trig = ADCpt(EpicsSignal, 'SIM:TRIG')


class PerkinElmerDetectorCam(CamBase):
    _html_docs = ['PerkinElmerDoc.html']
    pe_acquire_gain = ADCpt(EpicsSignal, 'PEAcquireGain')
    pe_acquire_offset = ADCpt(EpicsSignal, 'PEAcquireOffset')
    pe_corrections_dir = ADCpt(EpicsSignal, 'PECorrectionsDir')
    pe_current_gain_frame = ADCpt(EpicsSignal, 'PECurrentGainFrame')
    pe_current_offset_frame = ADCpt(EpicsSignal, 'PECurrentOffsetFrame')
    pe_dwell_time = ADCpt(SignalWithRBV, 'PEDwellTime')
    pe_frame_buff_index = ADCpt(EpicsSignal, 'PEFrameBuffIndex')
    pe_gain = ADCpt(SignalWithRBV, 'PEGain')
    pe_gain_available = ADCpt(EpicsSignal, 'PEGainAvailable')
    pe_gain_file = ADCpt(EpicsSignal, 'PEGainFile')
    pe_image_number = ADCpt(EpicsSignal, 'PEImageNumber')
    pe_initialize = ADCpt(EpicsSignal, 'PEInitialize')
    pe_load_gain_file = ADCpt(EpicsSignal, 'PELoadGainFile')
    pe_load_pixel_correction = ADCpt(EpicsSignal, 'PELoadPixelCorrection')
    pe_num_frame_buffers = ADCpt(SignalWithRBV, 'PENumFrameBuffers')
    pe_num_frames_to_skip = ADCpt(SignalWithRBV, 'PENumFramesToSkip')
    pe_num_gain_frames = ADCpt(EpicsSignal, 'PENumGainFrames')
    pe_num_offset_frames = ADCpt(EpicsSignal, 'PENumOffsetFrames')
    pe_offset_available = ADCpt(EpicsSignal, 'PEOffsetAvailable')
    pe_pixel_correction_available = ADCpt(EpicsSignal,
                                          'PEPixelCorrectionAvailable')
    pe_pixel_correction_file = ADCpt(EpicsSignal, 'PEPixelCorrectionFile')
    pe_save_gain_file = ADCpt(EpicsSignal, 'PESaveGainFile')
    pe_skip_frames = ADCpt(SignalWithRBV, 'PESkipFrames')
    pe_sync_time = ADCpt(SignalWithRBV, 'PESyncTime')
    pe_system_id = ADCpt(EpicsSignal, 'PESystemID')
    pe_trigger = ADCpt(EpicsSignal, 'PETrigger')
    pe_use_gain = ADCpt(EpicsSignal, 'PEUseGain')
    pe_use_offset = ADCpt(EpicsSignal, 'PEUseOffset')
    pe_use_pixel_correction = ADCpt(EpicsSignal, 'PEUsePixelCorrection')


class PSLDetectorCam(CamBase):
    _html_docs = ['PSLDoc.html']
    file_format = ADCpt(SignalWithRBV, 'FileFormat')
    tiff_comment = ADCpt(SignalWithRBV, 'TIFFComment')


class PilatusDetectorCam(CamBase):
    _html_docs = ['pilatusDoc.html']
    alpha = ADCpt(EpicsSignal, 'Alpha')
    angle_incr = ADCpt(EpicsSignal, 'AngleIncr')
    armed = ADCpt(EpicsSignal, 'Armed')
    bad_pixel_file = ADCpt(EpicsSignal, 'BadPixelFile')
    beam_x = ADCpt(EpicsSignal, 'BeamX')
    beam_y = ADCpt(EpicsSignal, 'BeamY')
    camserver_asyn = ADCpt(EpicsSignal, 'CamserverAsyn')
    cbf_template_file = ADCpt(EpicsSignal, 'CbfTemplateFile')
    chi = ADCpt(EpicsSignal, 'Chi')
    delay_time = ADCpt(SignalWithRBV, 'DelayTime')
    det_2theta = ADCpt(EpicsSignal, 'Det2theta')
    det_dist = ADCpt(EpicsSignal, 'DetDist')
    det_v_offset = ADCpt(EpicsSignal, 'DetVOffset')
    energy_high = ADCpt(EpicsSignal, 'EnergyHigh')
    energy_low = ADCpt(EpicsSignal, 'EnergyLow')
    file_format = ADCpt(SignalWithRBV, 'FileFormat')
    filter_transm = ADCpt(EpicsSignal, 'FilterTransm')
    flat_field_file = ADCpt(EpicsSignal, 'FlatFieldFile')
    flat_field_valid = ADCpt(EpicsSignal, 'FlatFieldValid')
    flux = ADCpt(EpicsSignal, 'Flux')
    gain_menu = ADCpt(EpicsSignal, 'GainMenu')
    gap_fill = ADCpt(SignalWithRBV, 'GapFill')
    header_string = ADCpt(EpicsSignal, 'HeaderString')
    humid0 = ADCpt(EpicsSignalRO, 'Humid0_RBV')
    humid1 = ADCpt(EpicsSignalRO, 'Humid1_RBV')
    humid2 = ADCpt(EpicsSignalRO, 'Humid2_RBV')
    image_file_tmot = ADCpt(EpicsSignal, 'ImageFileTmot')
    kappa = ADCpt(EpicsSignal, 'Kappa')
    min_flat_field = ADCpt(SignalWithRBV, 'MinFlatField')
    num_bad_pixels = ADCpt(EpicsSignal, 'NumBadPixels')
    num_oscill = ADCpt(EpicsSignal, 'NumOscill')
    oscill_axis = ADCpt(EpicsSignal, 'OscillAxis')
    phi = ADCpt(EpicsSignal, 'Phi')
    pixel_cut_off = ADCpt(EpicsSignalRO, 'PixelCutOff_RBV')
    polarization = ADCpt(EpicsSignal, 'Polarization')
    start_angle = ADCpt(EpicsSignal, 'StartAngle')
    tvx_version = ADCpt(EpicsSignalRO, 'TVXVersion_RBV')
    temp0 = ADCpt(EpicsSignalRO, 'Temp0_RBV')
    temp1 = ADCpt(EpicsSignalRO, 'Temp1_RBV')
    temp2 = ADCpt(EpicsSignalRO, 'Temp2_RBV')
    threshold_apply = ADCpt(EpicsSignal, 'ThresholdApply')
    threshold_auto_apply = ADCpt(SignalWithRBV, 'ThresholdAutoApply')
    threshold_energy = ADCpt(SignalWithRBV, 'ThresholdEnergy')
    wavelength = ADCpt(EpicsSignal, 'Wavelength')


class PixiradDetectorCam(CamBase):
    _html_docs = ['PixiradDoc.html']

    auto_calibrate = ADCpt(EpicsSignal, 'AutoCalibrate')
    humidity_box = ADCpt(EpicsSignalRO, 'BoxHumidity_RBV')
    colors_collected = ADCpt(EpicsSignalRO, 'ColorsCollected_RBV')
    cooling_state = ADCpt(SignalWithRBV, 'CoolingState')
    cooling_status = ADCpt(EpicsSignalRO, 'CoolingStatus_RBV')
    dew_point = ADCpt(EpicsSignalRO, 'DewPoint_RBV')
    frame_type = ADCpt(SignalWithRBV, 'FrameType')
    hv_actual = ADCpt(EpicsSignalRO, 'HVActual_RBV')
    hv_current = ADCpt(EpicsSignalRO, 'HVCurrent_RBV')
    hv_mode = ADCpt(SignalWithRBV, 'HVMode')
    hv_state = ADCpt(SignalWithRBV, 'HVState')
    hv_value = ADCpt(SignalWithRBV, 'HVValue')
    peltier_power = ADCpt(EpicsSignalRO, 'PeltierPower_RBV')
    sync_in_polarity = ADCpt(SignalWithRBV, 'SyncInPolarity')
    sync_out_function = ADCpt(SignalWithRBV, 'SyncOutFunction')
    sync_out_polarity = ADCpt(SignalWithRBV, 'SyncOutPolarity')
    system_reset = ADCpt(EpicsSignal, 'SystemReset')

    temperature = ADCpt(SignalWithRBV, 'Temperature')
    temperature_actual = ADCpt(EpicsSignal, 'TemperatureActual')
    temperature_box = ADCpt(EpicsSignalRO, 'BoxTemperature_RBV')
    temperature_hot = ADCpt(EpicsSignalRO, 'HotTemperature_RBV')

    threshold_1_actual = ADCpt(EpicsSignalRO, 'ThresholdActual1_RBV')
    threshold_2_actual = ADCpt(EpicsSignalRO, 'ThresholdActual2_RBV')
    threshold_3_actual = ADCpt(EpicsSignalRO, 'ThresholdActual3_RBV')
    threshold_4_actual = ADCpt(EpicsSignalRO, 'ThresholdActual4_RBV')
    thresholds_actual = DDC(ad_group(EpicsSignalRO,
                                     (('threshold_1', 'ThresholdActual1_RBV'),
                                      ('threshold_2', 'ThresholdActual2_RBV'),
                                      ('threshold_3', 'ThresholdActual3_RBV'),
                                      ('threshold_4', 'ThresholdActual4_RBV'),
                                      )),
                            doc='Actual thresholds')

    threshold_1 = ADCpt(SignalWithRBV, 'Threshold1')
    threshold_2 = ADCpt(SignalWithRBV, 'Threshold2')
    threshold_3 = ADCpt(SignalWithRBV, 'Threshold3')
    threshold_4 = ADCpt(SignalWithRBV, 'Threshold4')
    thresholds = DDC(ad_group(SignalWithRBV,
                              (('threshold_1', 'Threshold1'),
                               ('threshold_2', 'Threshold2'),
                               ('threshold_3', 'Threshold3'),
                               ('threshold_4', 'Threshold4'),
                               )),
                     doc='Thresholds')

    udp_buffers_free = ADCpt(EpicsSignalRO, 'UDPBuffersFree_RBV')
    udp_buffers_max = ADCpt(EpicsSignalRO, 'UDPBuffersMax_RBV')
    udp_buffers_read = ADCpt(EpicsSignalRO, 'UDPBuffersRead_RBV')
    udp_speed = ADCpt(EpicsSignalRO, 'UDPSpeed_RBV')


class PointGreyDetectorCam(CamBase):
    _html_docs = ['PointGreyDoc.html']

    bandwidth = ADCpt(EpicsSignal, 'Bandwidth')
    binning_mode = ADCpt(SignalWithRBV, 'BinningMode')
    convert_pixel_format = ADCpt(SignalWithRBV, 'ConvertPixelFormat')
    corrupt_frames = ADCpt(EpicsSignalRO, 'CorruptFrames_RBV')
    driver_dropped = ADCpt(EpicsSignalRO, 'DriverDropped_RBV')
    dropped_frames = ADCpt(EpicsSignalRO, 'DroppedFrames_RBV')
    firmware_version = ADCpt(EpicsSignal, 'FirmwareVersion')
    format7_mode = ADCpt(SignalWithRBV, 'Format7Mode')
    frame_rate = ADCpt(SignalWithRBV, 'FrameRate')
    max_packet_size = ADCpt(EpicsSignal, 'MaxPacketSize')
    packet_delay_actual = ADCpt(EpicsSignal, 'PacketDelayActual')
    packet_delay = ADCpt(SignalWithRBV, 'PacketDelay')
    packet_size_actual = ADCpt(EpicsSignal, 'PacketSizeActual')
    packet_size = ADCpt(SignalWithRBV, 'PacketSize')
    pixel_format = ADCpt(SignalWithRBV, 'PixelFormat')
    read_status = ADCpt(EpicsSignal, 'ReadStatus')
    serial_number = ADCpt(EpicsSignal, 'SerialNumber')
    skip_frames = ADCpt(SignalWithRBV, 'SkipFrames')
    software_trigger = ADCpt(EpicsSignal, 'SoftwareTrigger')
    software_version = ADCpt(EpicsSignal, 'SoftwareVersion')
    strobe_delay = ADCpt(SignalWithRBV, 'StrobeDelay')
    strobe_duration = ADCpt(SignalWithRBV, 'StrobeDuration')
    strobe_enable = ADCpt(SignalWithRBV, 'StrobeEnable')
    strobe_polarity = ADCpt(SignalWithRBV, 'StrobePolarity')
    strobe_source = ADCpt(SignalWithRBV, 'StrobeSource')
    time_stamp_mode = ADCpt(SignalWithRBV, 'TimeStampMode')
    transmit_failed = ADCpt(EpicsSignalRO, 'TransmitFailed_RBV')
    trigger_polarity = ADCpt(SignalWithRBV, 'TriggerPolarity')
    trigger_source = ADCpt(SignalWithRBV, 'TriggerSource')
    video_mode = ADCpt(SignalWithRBV, 'VideoMode')


class ProsilicaDetectorCam(CamBase):
    _html_docs = ['prosilicaDoc.html']
    ps_bad_frame_counter = ADCpt(EpicsSignalRO, 'PSBadFrameCounter_RBV')
    ps_byte_rate = ADCpt(SignalWithRBV, 'PSByteRate')
    ps_driver_type = ADCpt(EpicsSignalRO, 'PSDriverType_RBV')
    ps_filter_version = ADCpt(EpicsSignalRO, 'PSFilterVersion_RBV')
    ps_frame_rate = ADCpt(EpicsSignalRO, 'PSFrameRate_RBV')
    ps_frames_completed = ADCpt(EpicsSignalRO, 'PSFramesCompleted_RBV')
    ps_frames_dropped = ADCpt(EpicsSignalRO, 'PSFramesDropped_RBV')
    ps_packet_size = ADCpt(EpicsSignalRO, 'PSPacketSize_RBV')
    ps_packets_erroneous = ADCpt(EpicsSignalRO, 'PSPacketsErroneous_RBV')
    ps_packets_missed = ADCpt(EpicsSignalRO, 'PSPacketsMissed_RBV')
    ps_packets_received = ADCpt(EpicsSignalRO, 'PSPacketsReceived_RBV')
    ps_packets_requested = ADCpt(EpicsSignalRO, 'PSPacketsRequested_RBV')
    ps_packets_resent = ADCpt(EpicsSignalRO, 'PSPacketsResent_RBV')
    ps_read_statistics = ADCpt(EpicsSignal, 'PSReadStatistics')
    ps_reset_timer = ADCpt(EpicsSignal, 'PSResetTimer')
    ps_timestamp_type = ADCpt(SignalWithRBV, 'PSTimestampType')
    strobe1_ctl_duration = ADCpt(SignalWithRBV, 'Strobe1CtlDuration')
    strobe1_delay = ADCpt(SignalWithRBV, 'Strobe1Delay')
    strobe1_duration = ADCpt(SignalWithRBV, 'Strobe1Duration')
    strobe1_mode = ADCpt(SignalWithRBV, 'Strobe1Mode')
    sync_in1_level = ADCpt(EpicsSignalRO, 'SyncIn1Level_RBV')
    sync_in2_level = ADCpt(EpicsSignalRO, 'SyncIn2Level_RBV')
    sync_out1_invert = ADCpt(SignalWithRBV, 'SyncOut1Invert')
    sync_out1_level = ADCpt(SignalWithRBV, 'SyncOut1Level')
    sync_out1_mode = ADCpt(SignalWithRBV, 'SyncOut1Mode')
    sync_out2_invert = ADCpt(SignalWithRBV, 'SyncOut2Invert')
    sync_out2_level = ADCpt(SignalWithRBV, 'SyncOut2Level')
    sync_out2_mode = ADCpt(SignalWithRBV, 'SyncOut2Mode')
    sync_out3_invert = ADCpt(SignalWithRBV, 'SyncOut3Invert')
    sync_out3_level = ADCpt(SignalWithRBV, 'SyncOut3Level')
    sync_out3_mode = ADCpt(SignalWithRBV, 'SyncOut3Mode')
    trigger_delay = ADCpt(SignalWithRBV, 'TriggerDelay')
    trigger_event = ADCpt(SignalWithRBV, 'TriggerEvent')
    trigger_overlap = ADCpt(SignalWithRBV, 'TriggerOverlap')
    trigger_software = ADCpt(EpicsSignal, 'TriggerSoftware')


class PvcamDetectorCam(CamBase):
    _html_docs = ['pvcamDoc.html']
    bit_depth = ADCpt(EpicsSignalRO, 'BitDepth_RBV')
    camera_firmware_vers = ADCpt(EpicsSignalRO, 'CameraFirmwareVers_RBV')
    chip_height = ADCpt(EpicsSignalRO, 'ChipHeight_RBV')
    chip_name = ADCpt(EpicsSignalRO, 'ChipName_RBV')
    chip_width = ADCpt(EpicsSignalRO, 'ChipWidth_RBV')
    close_delay = ADCpt(SignalWithRBV, 'CloseDelay')
    detector_mode = ADCpt(SignalWithRBV, 'DetectorMode')
    detector_selected = ADCpt(SignalWithRBV, 'DetectorSelected')
    dev_drv_vers = ADCpt(EpicsSignalRO, 'DevDrvVers_RBV')
    frame_transfer_capable = ADCpt(EpicsSignalRO, 'FrameTransferCapable_RBV')
    full_well_capacity = ADCpt(EpicsSignalRO, 'FullWellCapacity_RBV')
    gain_index = ADCpt(SignalWithRBV, 'GainIndex')
    head_ser_num = ADCpt(EpicsSignalRO, 'HeadSerNum_RBV')
    initialize = ADCpt(SignalWithRBV, 'Initialize')
    max_gain_index = ADCpt(EpicsSignalRO, 'MaxGainIndex_RBV')
    max_set_temperature = ADCpt(EpicsSignal, 'MaxSetTemperature')
    max_shutter_close_delay = ADCpt(EpicsSignalRO, 'MaxShutterCloseDelay_RBV')
    max_shutter_open_delay = ADCpt(EpicsSignalRO, 'MaxShutterOpenDelay_RBV')
    measured_temperature = ADCpt(EpicsSignalRO, 'MeasuredTemperature_RBV')
    min_set_temperature = ADCpt(EpicsSignal, 'MinSetTemperature')
    min_shutter_close_delay = ADCpt(EpicsSignalRO, 'MinShutterCloseDelay_RBV')
    min_shutter_open_delay = ADCpt(EpicsSignalRO, 'MinShutterOpenDelay_RBV')
    num_parallel_pixels = ADCpt(EpicsSignalRO, 'NumParallelPixels_RBV')
    num_ports = ADCpt(EpicsSignalRO, 'NumPorts_RBV')
    num_serial_pixels = ADCpt(EpicsSignalRO, 'NumSerialPixels_RBV')
    num_speed_table_entries = ADCpt(EpicsSignalRO, 'NumSpeedTableEntries_RBV')
    open_delay = ADCpt(SignalWithRBV, 'OpenDelay')
    pcifw_vers = ADCpt(EpicsSignalRO, 'PCIFWVers_RBV')
    pv_cam_vers = ADCpt(EpicsSignalRO, 'PVCamVers_RBV')
    pixel_parallel_dist = ADCpt(EpicsSignalRO, 'PixelParallelDist_RBV')
    pixel_parallel_size = ADCpt(EpicsSignalRO, 'PixelParallelSize_RBV')
    pixel_serial_dist = ADCpt(EpicsSignalRO, 'PixelSerialDist_RBV')
    pixel_serial_size = ADCpt(EpicsSignalRO, 'PixelSerialSize_RBV')
    pixel_time = ADCpt(EpicsSignalRO, 'PixelTime_RBV')
    post_mask = ADCpt(EpicsSignalRO, 'PostMask_RBV')
    post_scan = ADCpt(EpicsSignalRO, 'PostScan_RBV')
    pre_mask = ADCpt(EpicsSignalRO, 'PreMask_RBV')
    pre_scan = ADCpt(EpicsSignalRO, 'PreScan_RBV')
    serial_num = ADCpt(EpicsSignalRO, 'SerialNum_RBV')
    set_temperature = ADCpt(SignalWithRBV, 'SetTemperature')
    slot1_cam = ADCpt(EpicsSignalRO, 'Slot1Cam_RBV')
    slot2_cam = ADCpt(EpicsSignalRO, 'Slot2Cam_RBV')
    slot3_cam = ADCpt(EpicsSignalRO, 'Slot3Cam_RBV')
    speed_table_index = ADCpt(SignalWithRBV, 'SpeedTableIndex')
    trigger_edge = ADCpt(SignalWithRBV, 'TriggerEdge')


class RoperDetectorCam(CamBase):
    _html_docs = ['RoperDoc.html']
    auto_data_type = ADCpt(SignalWithRBV, 'AutoDataType')
    comment1 = ADCpt(SignalWithRBV, 'Comment1')
    comment2 = ADCpt(SignalWithRBV, 'Comment2')
    comment3 = ADCpt(SignalWithRBV, 'Comment3')
    comment4 = ADCpt(SignalWithRBV, 'Comment4')
    comment5 = ADCpt(SignalWithRBV, 'Comment5')
    file_format = ADCpt(SignalWithRBV, 'FileFormat')
    num_acquisitions = ADCpt(SignalWithRBV, 'NumAcquisitions')
    num_acquisitions_counter = ADCpt(EpicsSignalRO, 'NumAcquisitionsCounter_RBV')
    roper_shutter_mode = ADCpt(SignalWithRBV, 'RoperShutterMode')


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

    url_select = ADCpt(EpicsSignal, 'URLSelect')
    url_seq = ADCpt(EpicsSignal, 'URLSeq')
    url = ADCpt(EpicsSignalRO, 'URL_RBV')


class Xspress3DetectorCam(CamBase):
    _html_docs = ['Xspress3Doc.html']

    def __init__(self, prefix, *, read_attrs=None, configuration_attrs=None,
                 **kwargs):
        if read_attrs is None:
            read_attrs = []
        if configuration_attrs is None:
            configuration_attrs = ['config_path', 'config_save_path']

        super().__init__(
            prefix,
            read_attrs=read_attrs,
            configuration_attrs=configuration_attrs,
            **kwargs
        )

    config_path = ADCpt(SignalWithRBV, 'CONFIG_PATH', string=True, doc="configuration file path")
    config_save_path = ADCpt(
        SignalWithRBV, 'CONFIG_SAVE_PATH', string=True, doc="path to save configuration file"
    )
    connect = ADCpt(EpicsSignal, 'CONNECT', doc="connect to the Xspress3")
    connected = ADCpt(EpicsSignal, 'CONNECTED', doc="show the connected status")
    ctrl_dtc = ADCpt(
        SignalWithRBV,
        'CTRL_DTC',
        doc="enable or disable DTC calculations: 0='Disable' 1='Enable'"
    )

    debounce = ADCpt(SignalWithRBV, 'DEBOUNCE', doc="set trigger debounce time in 80 MHz cycles")
    disconnect = ADCpt(EpicsSignal, 'DISCONNECT', doc="disconnect from the Xspress3")
    erase = ADCpt(EpicsSignal, "ERASE", kind="omitted", doc="erase MCA data: 0='Done' 1='Erase'")
    frame_count = ADCpt(
        EpicsSignalRO, 'FRAME_COUNT_RBV', doc="read number of frames acquired in an acquisition"
    )
    invert_f0 = ADCpt(SignalWithRBV, 'INVERT_F0', doc="invert F0 in modes LVDS_BOTH and TTL_BOTH")
    invert_veto = ADCpt(
        SignalWithRBV, 'INVERT_VETO', doc="invert VETO in modes LVDS, LVDS_BOTH, TTL, and TTL_BOTH"
    )
    max_frames = ADCpt(EpicsSignalRO, 'MAX_FRAMES_RBV', doc="maximum number of frames")
    max_frames_driver = ADCpt(
        EpicsSignalRO,
        'MAX_FRAMES_DRIVER_RBV',
        doc="maximum number of frames for a single acquisition"
    )
    max_num_channels = ADCpt(
        EpicsSignalRO,
        'MAX_NUM_CHANNELS_RBV',
        doc="maximum number of channels supported"
    )
    max_spectra = ADCpt(SignalWithRBV, 'MAX_SPECTRA', doc="maximum number of elements in a spectrum")
    xsp_name = ADCpt(EpicsSignal, 'NAME', doc="detector name")
    num_cards = ADCpt(EpicsSignalRO, 'NUM_CARDS_RBV', doc="number of xspress3 cards to set up")
    num_channels = ADCpt(SignalWithRBV, 'NUM_CHANNELS', doc="number of channels to read out")
    num_frames_config = ADCpt(
        SignalWithRBV, 'NUM_FRAMES_CONFIG', doc="number of frames to configure the system with"
    )
    reset = ADCpt(EpicsSignal, 'RESET', doc="reset the device")
    restore_settings = ADCpt(EpicsSignal, 'RESTORE_SETTINGS', doc="restore settings from a file")
    run_flags = ADCpt(SignalWithRBV, 'RUN_FLAGS', doc="set the run flags, only at connect time")
    save_settings = ADCpt(EpicsSignal, 'SAVE_SETTINGS', doc="save current settings to a file")
    trigger_signal = ADCpt(EpicsSignal, 'TRIGGER', doc="0='Do Nothing', 1='Trigger'")

    # these CamBase PVs are disabled by the xspress3 IOC
    bin_x = None
    bin_y = None
    color_mode = None
    data_type = None
    gain = None
    min_x = None
    min_y = None
    reverse = None
    size = None
