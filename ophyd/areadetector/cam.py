# type: ignore

import logging

from ..device import DynamicDeviceComponent as DDC
from ..signal import EpicsSignal, EpicsSignalRO
from ..utils import enum
from .base import ADBase
from .base import ADComponent as ADCpt
from .base import EpicsSignalWithRBV as SignalWithRBV
from .base import ad_group

# Import FileBase class for cameras that use File PVs in their drivers
from .plugins import FileBase

logger = logging.getLogger(__name__)


__all__ = [
    "CamBase",
    "AdscDetectorCam",
    "Andor3DetectorCam",
    "AndorDetectorCam",
    "BrukerDetectorCam",
    "DexelaDetectorCam",
    "EmergentVisionDetectorCam",
    "EigerDetectorCam",
    "FirewireLinDetectorCam",
    "FirewireWinDetectorCam",
    "GreatEyesDetectorCam",
    "Lambda750kCam",
    "LightFieldDetectorCam",
    "Mar345DetectorCam",
    "MarCCDDetectorCam",
    "PSLDetectorCam",
    "PcoDetectorCam",
    "PcoDetectorIO",
    "PcoDetectorSimIO",
    "PerkinElmerDetectorCam",
    "PICamDetectorCam",
    "PilatusDetectorCam",
    "PixiradDetectorCam",
    "PointGreyDetectorCam",
    "ProsilicaDetectorCam",
    "PvaDetectorCam",
    "PvcamDetectorCam",
    "RoperDetectorCam",
    "SimDetectorCam",
    "URLDetectorCam",
    "UVCDetectorCam",
    "Xspress3DetectorCam",
]


class CamBase(ADBase):
    _default_configuration_attrs = ADBase._default_configuration_attrs + (
        "acquire_time",
        "acquire_period",
        "model",
        "num_exposures",
        "image_mode",
        "num_images",
        "manufacturer",
        "trigger_mode",
    )

    ImageMode = enum(SINGLE=0, MULTIPLE=1, CONTINUOUS=2)

    # Shared among all cams and plugins
    array_counter = ADCpt(SignalWithRBV, "ArrayCounter")
    array_rate = ADCpt(EpicsSignalRO, "ArrayRate_RBV")
    asyn_io = ADCpt(EpicsSignal, "AsynIO")

    nd_attributes_file = ADCpt(EpicsSignal, "NDAttributesFile", string=True)
    pool_alloc_buffers = ADCpt(EpicsSignalRO, "PoolAllocBuffers")
    pool_free_buffers = ADCpt(EpicsSignalRO, "PoolFreeBuffers")
    pool_max_buffers = ADCpt(EpicsSignalRO, "PoolMaxBuffers")
    pool_max_mem = ADCpt(EpicsSignalRO, "PoolMaxMem")
    pool_used_buffers = ADCpt(EpicsSignalRO, "PoolUsedBuffers")
    pool_used_mem = ADCpt(EpicsSignalRO, "PoolUsedMem")
    port_name = ADCpt(EpicsSignalRO, "PortName_RBV", string=True)

    # Cam-specific
    acquire = ADCpt(SignalWithRBV, "Acquire")
    acquire_period = ADCpt(SignalWithRBV, "AcquirePeriod")
    acquire_time = ADCpt(SignalWithRBV, "AcquireTime")

    array_callbacks = ADCpt(SignalWithRBV, "ArrayCallbacks")
    array_size = DDC(
        ad_group(
            EpicsSignalRO,
            (
                ("array_size_z", "ArraySizeZ_RBV"),
                ("array_size_y", "ArraySizeY_RBV"),
                ("array_size_x", "ArraySizeX_RBV"),
            ),
        ),
        doc="Size of the array in the XYZ dimensions",
    )

    array_size_bytes = ADCpt(EpicsSignalRO, "ArraySize_RBV")
    bin_x = ADCpt(SignalWithRBV, "BinX")
    bin_y = ADCpt(SignalWithRBV, "BinY")
    color_mode = ADCpt(SignalWithRBV, "ColorMode")
    data_type = ADCpt(SignalWithRBV, "DataType")
    detector_state = ADCpt(EpicsSignalRO, "DetectorState_RBV")
    frame_type = ADCpt(SignalWithRBV, "FrameType")
    gain = ADCpt(SignalWithRBV, "Gain")

    image_mode = ADCpt(SignalWithRBV, "ImageMode")
    manufacturer = ADCpt(EpicsSignalRO, "Manufacturer_RBV")

    max_size = DDC(
        ad_group(
            EpicsSignalRO,
            (("max_size_x", "MaxSizeX_RBV"), ("max_size_y", "MaxSizeY_RBV")),
        ),
        doc="Maximum sensor size in the XY directions",
    )

    min_x = ADCpt(SignalWithRBV, "MinX")
    min_y = ADCpt(SignalWithRBV, "MinY")
    model = ADCpt(EpicsSignalRO, "Model_RBV")

    num_exposures = ADCpt(SignalWithRBV, "NumExposures")
    num_exposures_counter = ADCpt(EpicsSignalRO, "NumExposuresCounter_RBV")
    num_images = ADCpt(SignalWithRBV, "NumImages")
    num_images_counter = ADCpt(EpicsSignalRO, "NumImagesCounter_RBV")

    read_status = ADCpt(EpicsSignal, "ReadStatus")
    reverse = DDC(
        ad_group(SignalWithRBV, (("reverse_x", "ReverseX"), ("reverse_y", "ReverseY")))
    )

    shutter_close_delay = ADCpt(SignalWithRBV, "ShutterCloseDelay")
    shutter_close_epics = ADCpt(EpicsSignal, "ShutterCloseEPICS")
    shutter_control = ADCpt(SignalWithRBV, "ShutterControl")
    shutter_control_epics = ADCpt(EpicsSignal, "ShutterControlEPICS")
    shutter_fanout = ADCpt(EpicsSignal, "ShutterFanout")
    shutter_mode = ADCpt(SignalWithRBV, "ShutterMode")
    shutter_open_delay = ADCpt(SignalWithRBV, "ShutterOpenDelay")
    shutter_open_epics = ADCpt(EpicsSignal, "ShutterOpenEPICS")
    shutter_status_epics = ADCpt(EpicsSignalRO, "ShutterStatusEPICS_RBV")
    shutter_status = ADCpt(EpicsSignalRO, "ShutterStatus_RBV")

    size = DDC(ad_group(SignalWithRBV, (("size_x", "SizeX"), ("size_y", "SizeY"))))

    status_message = ADCpt(EpicsSignalRO, "StatusMessage_RBV", string=True)
    string_from_server = ADCpt(EpicsSignalRO, "StringFromServer_RBV", string=True)
    string_to_server = ADCpt(EpicsSignalRO, "StringToServer_RBV", string=True)
    temperature = ADCpt(SignalWithRBV, "Temperature")
    temperature_actual = ADCpt(EpicsSignal, "TemperatureActual")
    time_remaining = ADCpt(EpicsSignalRO, "TimeRemaining_RBV")
    trigger_mode = ADCpt(SignalWithRBV, "TriggerMode")


class AreaDetectorCam(CamBase):
    pass


class SimDetectorCam(CamBase):
    _html_docs = ["simDetectorDoc.html"]
    gain_rgb = DDC(
        ad_group(
            SignalWithRBV,
            (
                ("gain_red", "GainRed"),
                ("gain_green", "GainGreen"),
                ("gain_blue", "GainBlue"),
            ),
        ),
        doc="Gain rgb components",
    )
    gain_xy = DDC(
        ad_group(SignalWithRBV, (("gain_x", "GainX"), ("gain_y", "GainY"))),
        doc="Gain in XY",
    )

    noise = ADCpt(SignalWithRBV, "Noise")
    peak_num = DDC(
        ad_group(
            SignalWithRBV, (("peak_num_x", "PeakNumX"), ("peak_num_y", "PeakNumY"))
        ),
        doc="Peak number in XY",
    )

    peak_start = DDC(
        ad_group(
            SignalWithRBV,
            (("peak_start_x", "PeakStartX"), ("peak_start_y", "PeakStartY")),
        ),
        doc="Peak start in XY",
    )

    peak_step = DDC(
        ad_group(
            SignalWithRBV, (("peak_step_x", "PeakStepX"), ("peak_step_y", "PeakStepY"))
        ),
        doc="Peak step in XY",
    )

    peak_variation = ADCpt(SignalWithRBV, "PeakVariation")
    peak_width = DDC(
        ad_group(
            SignalWithRBV,
            (("peak_width_x", "PeakWidthX"), ("peak_width_y", "PeakWidthY")),
        ),
        doc="Peak width in XY",
    )

    reset = ADCpt(SignalWithRBV, "Reset")
    sim_mode = ADCpt(SignalWithRBV, "SimMode")


class AdscDetectorCam(CamBase):
    _html_docs = ["adscDoc.html"]
    adsc_2theta = ADCpt(SignalWithRBV, "ADSC2Theta")
    adsc_adc = ADCpt(SignalWithRBV, "ADSCAdc")
    adsc_axis = ADCpt(SignalWithRBV, "ADSCAxis")
    adsc_beam_x = ADCpt(SignalWithRBV, "ADSCBeamX")
    adsc_beam_y = ADCpt(SignalWithRBV, "ADSCBeamY")
    adsc_dezingr = ADCpt(SignalWithRBV, "ADSCDezingr")
    adsc_distance = ADCpt(SignalWithRBV, "ADSCDistnce")
    adsc_im_width = ADCpt(SignalWithRBV, "ADSCImWidth")
    adsc_im_xform = ADCpt(SignalWithRBV, "ADSCImXform")
    adsc_kappa = ADCpt(SignalWithRBV, "ADSCKappa")
    adsc_last_error = ADCpt(EpicsSignal, "ADSCLastError")
    adsc_last_image = ADCpt(EpicsSignal, "ADSCLastImage")
    adsc_omega = ADCpt(SignalWithRBV, "ADSCOmega")
    adsc_phi = ADCpt(SignalWithRBV, "ADSCPhi")
    adsc_raw = ADCpt(SignalWithRBV, "ADSCRaw")
    adsc_read_conditn = ADCpt(EpicsSignal, "ADSCReadConditn")
    adsc_reus_drk = ADCpt(SignalWithRBV, "ADSCReusDrk")
    adsc_soft_reset = ADCpt(EpicsSignal, "ADSCSoftReset")
    adsc_state = ADCpt(EpicsSignal, "ADSCState")
    adsc_status = ADCpt(EpicsSignal, "ADSCStatus")
    adsc_stp_ex_retry_count = ADCpt(EpicsSignal, "ADSCStpExRtryCt")
    adsc_str_drks = ADCpt(SignalWithRBV, "ADSCStrDrks")
    adsc_wavelen = ADCpt(SignalWithRBV, "ADSCWavelen")

    bin_x_changed = ADCpt(EpicsSignal, "BinXChanged")
    bin_y_changed = ADCpt(EpicsSignal, "BinYChanged")
    ext_trig_ctl = ADCpt(EpicsSignal, "ExSwTrCtl")
    ext_trig_ctl_rsp = ADCpt(EpicsSignal, "ExSwTrCtlRsp")
    ext_trig_ok_to_exp = ADCpt(EpicsSignal, "ExSwTrOkToExp")


class AndorDetectorCam(CamBase):
    _html_docs = ["andorDoc.html"]
    andor_adc_speed = ADCpt(SignalWithRBV, "AndorADCSpeed")
    andor_accumulate_period = ADCpt(SignalWithRBV, "AndorAccumulatePeriod")
    andor_cooler = ADCpt(SignalWithRBV, "AndorCooler")
    andor_message = ADCpt(EpicsSignalRO, "AndorMessage_RBV")
    andor_pre_amp_gain = ADCpt(SignalWithRBV, "AndorPreAmpGain")
    andor_shutter_ex_ttl = ADCpt(EpicsSignal, "AndorShutterExTTL")
    andor_shutter_mode = ADCpt(EpicsSignal, "AndorShutterMode")
    andor_temp_status = ADCpt(EpicsSignalRO, "AndorTempStatus_RBV")
    file_format = ADCpt(SignalWithRBV, "FileFormat")
    pal_file_path = ADCpt(SignalWithRBV, "PALFilePath")


class Andor3DetectorCam(CamBase):
    _html_docs = ["andor3Doc.html"]
    a3_binning = ADCpt(SignalWithRBV, "A3Binning")
    a3_shutter_mode = ADCpt(SignalWithRBV, "A3ShutterMode")
    controller_id = ADCpt(EpicsSignal, "ControllerID")
    fan_speed = ADCpt(SignalWithRBV, "FanSpeed")
    firmware_version = ADCpt(EpicsSignal, "FirmwareVersion")
    frame_rate = ADCpt(SignalWithRBV, "FrameRate")
    full_aoic_ontrol = ADCpt(EpicsSignal, "FullAOIControl")
    noise_filter = ADCpt(SignalWithRBV, "NoiseFilter")
    overlap = ADCpt(SignalWithRBV, "Overlap")
    pixel_encoding = ADCpt(SignalWithRBV, "PixelEncoding")
    pre_amp_gain = ADCpt(SignalWithRBV, "PreAmpGain")
    readout_rate = ADCpt(SignalWithRBV, "ReadoutRate")
    readout_time = ADCpt(EpicsSignal, "ReadoutTime")
    sensor_cooling = ADCpt(SignalWithRBV, "SensorCooling")
    serial_number = ADCpt(EpicsSignal, "SerialNumber")
    software_trigger = ADCpt(EpicsSignal, "SoftwareTrigger")
    software_version = ADCpt(EpicsSignal, "SoftwareVersion")
    temp_control = ADCpt(SignalWithRBV, "TempControl")
    temp_status = ADCpt(EpicsSignalRO, "TempStatus_RBV")
    transfer_rate = ADCpt(EpicsSignal, "TransferRate")


class BrukerDetectorCam(CamBase):
    _html_docs = ["BrukerDoc.html"]
    bis_asyn = ADCpt(EpicsSignal, "BISAsyn")
    bis_status = ADCpt(EpicsSignal, "BISStatus")
    file_format = ADCpt(SignalWithRBV, "FileFormat")
    num_darks = ADCpt(SignalWithRBV, "NumDarks")
    read_sfrm_timeout = ADCpt(EpicsSignal, "ReadSFRMTimeout")


class DexelaDetectorCam(CamBase):
    acquire_gain = ADCpt(EpicsSignal, "DEXAcquireGain")
    acquire_offset = ADCpt(EpicsSignal, "DEXAcquireOffset")
    binning_mode = ADCpt(SignalWithRBV, "DEXBinningMode")
    corrections_dir = ADCpt(EpicsSignal, "DEXCorrectionsDir", string=True)
    current_gain_frame = ADCpt(EpicsSignal, "DEXCurrentGainFrame")
    current_offset_frame = ADCpt(EpicsSignal, "DEXCurrentOffsetFrame")
    defect_map_available = ADCpt(EpicsSignal, "DEXDefectMapAvailable")
    defect_map_file = ADCpt(EpicsSignal, "DEXDefectMapFile", string=True)
    full_well_mode = ADCpt(SignalWithRBV, "DEXFullWellMode")
    gain_available = ADCpt(EpicsSignal, "DEXGainAvailable")
    gain_file = ADCpt(EpicsSignal, "DEXGainFile", string=True)
    load_defect_map_file = ADCpt(EpicsSignal, "DEXLoadDefectMapFile")
    load_gain_file = ADCpt(EpicsSignal, "DEXLoadGainFile")
    load_offset_file = ADCpt(EpicsSignal, "DEXLoadOffsetFile")
    num_gain_frames = ADCpt(EpicsSignal, "DEXNumGainFrames")
    num_offset_frames = ADCpt(EpicsSignal, "DEXNumOffsetFrames")
    offset_available = ADCpt(EpicsSignal, "DEXOffsetAvailable")
    offset_constant = ADCpt(SignalWithRBV, "DEXOffsetConstant")
    offset_file = ADCpt(EpicsSignal, "DEXOffsetFile", string=True)
    save_gain_file = ADCpt(EpicsSignal, "DEXSaveGainFile")
    save_offset_file = ADCpt(EpicsSignal, "DEXSaveOffsetFile")
    serial_number = ADCpt(EpicsSignal, "DEXSerialNumber")
    software_trigger = ADCpt(EpicsSignal, "DEXSoftwareTrigger")
    use_defect_map = ADCpt(EpicsSignal, "DEXUseDefectMap")
    use_gain = ADCpt(EpicsSignal, "DEXUseGain")
    use_offset = ADCpt(EpicsSignal, "DEXUseOffset")


class EmergentVisionDetectorCam(CamBase):

    _html_docs = ["EVTDoc.html"]
    _default_configuration_attrs = CamBase._default_configuration_attrs + (
        "pixel_format",
        "auto_gain",
        "framerate",
    )

    pixel_format = ADCpt(SignalWithRBV, "EVTPixelFormat")
    framerate = ADCpt(SignalWithRBV, "EVTFramerate")
    offset_x = ADCpt(SignalWithRBV, "EVTOffsetX")
    offset_y = ADCpt(SignalWithRBV, "EVTOffsetY")
    buff_mode = ADCpt(SignalWithRBV, "EVTBuffMode")
    buff_num = ADCpt(SignalWithRBV, "EVTBuffNum")
    packet_size = ADCpt(SignalWithRBV, "EVTPacketSize")
    lut_enable = ADCpt(SignalWithRBV, "EVTLUTEnable")
    auto_gain = ADCpt(SignalWithRBV, "EVTAutoGain")


class EigerDetectorCam(CamBase, FileBase):

    _html_docs = ["EigerDoc.html"]
    _default_configuration_attrs = CamBase._default_configuration_attrs + (
        "shutter_mode",
        "num_triggers",
        "beam_center_x",
        "beam_center_y",
        "wavelength",
        "det_distance",
        "threshold_energy",
        "photon_energy",
        "manual_trigger",
        "special_trigger_button",
    )

    shutter_mode = ADCpt(SignalWithRBV, "ShutterMode")
    num_triggers = ADCpt(SignalWithRBV, "NumTriggers")
    beam_center_x = ADCpt(SignalWithRBV, "BeamX")
    beam_center_y = ADCpt(SignalWithRBV, "BeamY")
    wavelength = ADCpt(SignalWithRBV, "Wavelength")
    det_distance = ADCpt(SignalWithRBV, "DetDist")
    threshold_energy = ADCpt(SignalWithRBV, "ThresholdEnergy")
    photon_energy = ADCpt(SignalWithRBV, "PhotonEnergy")
    manual_trigger = ADCpt(SignalWithRBV, "ManualTrigger")  # the checkbox
    special_trigger_button = ADCpt(
        EpicsSignal, "Trigger"
    )  # the button next to 'Start' and 'Stop'
    trigger_exposure = ADCpt(SignalWithRBV, "TriggerExposure")
    data_source = ADCpt(SignalWithRBV, "DataSource")
    stream_decompress = ADCpt(SignalWithRBV, "StreamDecompress")
    fw_enable = ADCpt(SignalWithRBV, "FWEnable")
    fw_clear = ADCpt(EpicsSignal, "FWClear")
    fw_compression = ADCpt(SignalWithRBV, "FWCompression")
    fw_name_pattern = ADCpt(SignalWithRBV, "FWNamePattern", string=True)
    fw_num_images_per_file = ADCpt(SignalWithRBV, "FWNImagesPerFile")
    fw_autoremove = ADCpt(SignalWithRBV, "FWAutoRemove")
    fw_free = ADCpt(EpicsSignalRO, "FWFree_RBV")
    fw_state = ADCpt(EpicsSignalRO, "FWState_RBV")
    description = ADCpt(EpicsSignalRO, "Description_RBV", string=True)
    sensor_thickness = ADCpt(EpicsSignalRO, "SensorThickness_RBV")
    sensor_material = ADCpt(EpicsSignalRO, "SensorMaterial_RBV")
    count_cutoff = ADCpt(EpicsSignalRO, "CountCutoff_RBV")
    x_pixel_size = ADCpt(EpicsSignalRO, "XPixelSize_RBV")
    y_pixel_size = ADCpt(EpicsSignalRO, "YPixelSize_RBV")
    roi_mode = ADCpt(SignalWithRBV, "ROIMode")
    dead_time = ADCpt(EpicsSignalRO, "DeadTime_RBV")
    compression_algo = ADCpt(SignalWithRBV, "CompressionAlgo")
    stream_enable = ADCpt(SignalWithRBV, "StreamEnable")
    stream_dropped = ADCpt(EpicsSignalRO, "StreamDropped_RBV")
    stream_state = ADCpt(EpicsSignalRO, "StreamState_RBV")
    stream_hdr_detail = ADCpt(SignalWithRBV, "StreamHdrDetail")
    stream_hdr_appendix = ADCpt(EpicsSignal, "StreamHdrAppendix")
    stream_img_appendix = ADCpt(EpicsSignal, "StreamImgAppendix")
    save_files = ADCpt(SignalWithRBV, "SaveFiles")
    file_owner = ADCpt(SignalWithRBV, "FileOwner")
    file_owner_grp = ADCpt(SignalWithRBV, "FileOwnerGrp")
    file_perms = ADCpt(EpicsSignal, "FilePerms")
    flatfield_applied = ADCpt(SignalWithRBV, "FlatfieldApplied")
    sequence_id = ADCpt(EpicsSignal, "SequenceId")
    photon_energy = ADCpt(SignalWithRBV, "PhotonEnergy")
    armed = ADCpt(EpicsSignalRO, "Armed")
    chi_start = ADCpt(SignalWithRBV, "ChiStart")
    chi_incr = ADCpt(SignalWithRBV, "ChiIncr")
    kappa_start = ADCpt(SignalWithRBV, "KappaStart")
    kappa_incr = ADCpt(SignalWithRBV, "KappaIncr")
    omega_start = ADCpt(SignalWithRBV, "OmegaStart")
    omega_incr = ADCpt(SignalWithRBV, "OmegaIncr")
    phi_start = ADCpt(SignalWithRBV, "PhiStart")
    phi_incr = ADCpt(SignalWithRBV, "PhiIncr")
    two_theta_start = ADCpt(SignalWithRBV, "TwoThetaStart")
    two_theta_incr = ADCpt(SignalWithRBV, "TwoThetaIncr")
    monitor_enable = ADCpt(SignalWithRBV, "MonitorEnable")
    monitor_timeout = ADCpt(SignalWithRBV, "MonitorTimeout")
    monitor_state = ADCpt(EpicsSignalRO, "MonitorState_RBV")
    temp_0 = ADCpt(EpicsSignalRO, "Temp0_RBV")
    humid_0 = ADCpt(EpicsSignalRO, "Humid0_RBV")
    link_0 = ADCpt(EpicsSignalRO, "Link0_RBV")
    link_1 = ADCpt(EpicsSignalRO, "Link1_RBV")
    link_2 = ADCpt(EpicsSignalRO, "Link2_RBV")
    link_3 = ADCpt(EpicsSignalRO, "Link3_RBV")
    dcu_buff_free = ADCpt(EpicsSignalRO, "DCUBufferFree_RBV")


class FirewireLinDetectorCam(CamBase):
    _html_docs = []

    bandwidth = ADCpt(EpicsSignal, "BANDWIDTH")
    fanout_disable = ADCpt(EpicsSignal, "FanoutDis")
    framerate_max = ADCpt(SignalWithRBV, "FR")
    is_fixed_mode = ADCpt(EpicsSignal, "IsFixedMode")
    video_mode = ADCpt(EpicsSignal, "VIDEOMODE")


class FirewireWinDetectorCam(CamBase):
    _html_docs = ["FirewireWinDoc.html"]
    colorcode = ADCpt(SignalWithRBV, "COLORCODE")
    current_colorcode = ADCpt(EpicsSignal, "CURRENT_COLORCODE")
    current_format = ADCpt(EpicsSignal, "CURRENT_FORMAT")
    current_mode = ADCpt(EpicsSignal, "CURRENT_MODE")
    current_rate = ADCpt(EpicsSignal, "CURRENT_RATE")
    dropped_frames = ADCpt(SignalWithRBV, "DROPPED_FRAMES")
    format_ = ADCpt(SignalWithRBV, "FORMAT")
    frame_rate = ADCpt(SignalWithRBV, "FR")
    mode = ADCpt(SignalWithRBV, "MODE")
    readout_time = ADCpt(SignalWithRBV, "READOUT_TIME")


class GreatEyesDetectorCam(CamBase):
    _html_docs = []
    adc_speed = ADCpt(SignalWithRBV, "GreatEyesAdcSpeed")
    capacity = ADCpt(SignalWithRBV, "GreatEyesCapacity")
    enable_cooling = ADCpt(SignalWithRBV, "GreatEyesEnableCooling")
    gain = ADCpt(SignalWithRBV, "GreatEyesGain")
    hot_side_temp = ADCpt(EpicsSignal, "GreatEyesHotSideTemp")
    readout_dir = ADCpt(SignalWithRBV, "GreatEyesReadoutDir")
    sync = ADCpt(SignalWithRBV, "GreatEyesSync")


class Lambda750kCam(CamBase):
    """
    support for X-Spectrum Lambda 750K detector

    https://x-spectrum.de/products/lambda-350k750k/
    """

    _html_docs = ["Lambda750kCam.html"]

    config_file_path = ADCpt(EpicsSignal, "ConfigFilePath")
    firmware_version = ADCpt(EpicsSignalRO, "FirmwareVersion_RBV")
    operating_mode = ADCpt(SignalWithRBV, "OperatingMode")
    serial_number = ADCpt(EpicsSignalRO, "SerialNumber_RBV")
    temperature = ADCpt(SignalWithRBV, "Temperature")


class LightFieldDetectorCam(CamBase):
    _html_docs = ["LightFieldDoc.html"]

    aux_delay = ADCpt(SignalWithRBV, "LFAuxDelay")
    aux_width = ADCpt(SignalWithRBV, "LFAuxWidth")
    background_enable = ADCpt(SignalWithRBV, "LFBackgroundEnable")
    background_file = ADCpt(SignalWithRBV, "LFBackgroundFile")
    background_full_file = ADCpt(EpicsSignalRO, "LFBackgroundFullFile_RBV")
    background_path = ADCpt(SignalWithRBV, "LFBackgroundPath")
    entrance_width = ADCpt(SignalWithRBV, "LFEntranceWidth")
    exit_port = ADCpt(SignalWithRBV, "LFExitPort")
    experiment_name = ADCpt(SignalWithRBV, "LFExperimentName")
    file_name = ADCpt(EpicsSignalRO, "LFFileName_RBV")
    file_path = ADCpt(EpicsSignalRO, "LFFilePath_RBV")
    lf_gain = ADCpt(SignalWithRBV, "LFGain")
    gating_mode = ADCpt(SignalWithRBV, "LFGatingMode")
    grating = ADCpt(SignalWithRBV, "LFGrating")
    grating_wavelength = ADCpt(SignalWithRBV, "LFGratingWavelength")
    image_mode = ADCpt(SignalWithRBV, "ImageMode")
    intensifier_enable = ADCpt(SignalWithRBV, "LFIntensifierEnable")
    intensifier_gain = ADCpt(SignalWithRBV, "LFIntensifierGain")
    num_accumulations = ADCpt(SignalWithRBV, "NumAccumulations")
    ready_to_run = ADCpt(EpicsSignal, "LFReadyToRun")
    rep_gate_delay = ADCpt(SignalWithRBV, "LFRepGateDelay")
    rep_gate_width = ADCpt(SignalWithRBV, "LFRepGateWidth")
    seq_end_gate_delay = ADCpt(SignalWithRBV, "LFSeqEndGateDelay")
    seq_end_gate_width = ADCpt(SignalWithRBV, "LFSeqEndGateWidth")
    seq_start_gate_delay = ADCpt(SignalWithRBV, "LFSeqStartGateDelay")
    seq_start_gate_width = ADCpt(SignalWithRBV, "LFSeqStartGateWidth")
    lf_shutter_mode = ADCpt(SignalWithRBV, "LFShutterMode")
    sync_master2_delay = ADCpt(SignalWithRBV, "LFSyncMaster2Delay")
    sync_master_enable = ADCpt(SignalWithRBV, "LFSyncMasterEnable")
    trigger_frequency = ADCpt(SignalWithRBV, "LFTriggerFrequency")
    update_experiments = ADCpt(EpicsSignal, "LFUpdateExperiments")


class Mar345DetectorCam(CamBase):
    _html_docs = ["Mar345Doc.html"]
    abort = ADCpt(SignalWithRBV, "Abort")
    change_mode = ADCpt(SignalWithRBV, "ChangeMode")
    erase = ADCpt(SignalWithRBV, "Erase")
    erase_mode = ADCpt(SignalWithRBV, "EraseMode")
    file_format = ADCpt(SignalWithRBV, "FileFormat")
    num_erase = ADCpt(SignalWithRBV, "NumErase")
    num_erased = ADCpt(EpicsSignalRO, "NumErased_RBV")
    scan_resolution = ADCpt(SignalWithRBV, "ScanResolution")
    scan_size = ADCpt(SignalWithRBV, "ScanSize")
    mar_server_asyn = ADCpt(EpicsSignal, "marServerAsyn")


class MarCCDDetectorCam(CamBase):
    _html_docs = ["MarCCDDoc.html"]
    beam_x = ADCpt(EpicsSignal, "BeamX")
    beam_y = ADCpt(EpicsSignal, "BeamY")
    dataset_comments = ADCpt(EpicsSignal, "DatasetComments")
    detector_distance = ADCpt(EpicsSignal, "DetectorDistance")
    file_comments = ADCpt(EpicsSignal, "FileComments")
    file_format = ADCpt(SignalWithRBV, "FileFormat")
    frame_shift = ADCpt(SignalWithRBV, "FrameShift")
    mar_acquire_status = ADCpt(EpicsSignalRO, "MarAcquireStatus_RBV")
    mar_correct_status = ADCpt(EpicsSignalRO, "MarCorrectStatus_RBV")
    mar_dezinger_status = ADCpt(EpicsSignalRO, "MarDezingerStatus_RBV")
    mar_readout_status = ADCpt(EpicsSignalRO, "MarReadoutStatus_RBV")
    mar_state = ADCpt(EpicsSignalRO, "MarState_RBV")
    mar_status = ADCpt(EpicsSignalRO, "MarStatus_RBV")
    mar_writing_status = ADCpt(EpicsSignalRO, "MarWritingStatus_RBV")
    overlap_mode = ADCpt(SignalWithRBV, "OverlapMode")
    read_tiff_timeout = ADCpt(EpicsSignal, "ReadTiffTimeout")
    rotation_axis = ADCpt(EpicsSignal, "RotationAxis")
    rotation_range = ADCpt(EpicsSignal, "RotationRange")
    stability = ADCpt(SignalWithRBV, "Stability")
    start_phi = ADCpt(EpicsSignal, "StartPhi")
    two_theta = ADCpt(EpicsSignal, "TwoTheta")
    wavelength = ADCpt(EpicsSignal, "Wavelength")
    mar_server_asyn = ADCpt(EpicsSignal, "marServerAsyn")


class PcoDetectorCam(CamBase):
    _html_docs = [""]
    adc_mode = ADCpt(SignalWithRBV, "ADC_MODE")
    arm_mode = ADCpt(SignalWithRBV, "ARM_MODE")
    bit_alignment = ADCpt(SignalWithRBV, "BIT_ALIGNMENT")
    camera_setup = ADCpt(SignalWithRBV, "CAMERA_SETUP")
    cam_ram_use = ADCpt(EpicsSignalRO, "CAM_RAM_USE_RBV")
    delay_time = ADCpt(SignalWithRBV, "DELAY_TIME")
    elec_temp = ADCpt(EpicsSignalRO, "ELEC_TEMP_RBV")
    exposure_base = ADCpt(EpicsSignalRO, "EXPOSUREBASE_RBV")
    pco_acquire_mode = ADCpt(SignalWithRBV, "ACQUIRE_MODE")
    pco_image_number = ADCpt(EpicsSignalRO, "IMAGE_NUMBER_RBV")
    pix_rate = ADCpt(SignalWithRBV, "PIX_RATE")
    power_temp = ADCpt(EpicsSignalRO, "POWER_TEMP_RBV")
    recorder_mode = ADCpt(SignalWithRBV, "RECORDER_MODE")
    storage_mode = ADCpt(SignalWithRBV, "STORAGE_MODE")
    timestamp_mode = ADCpt(SignalWithRBV, "TIMESTAMP_MODE")


class PcoDetectorIO(ADBase):
    _html_docs = [""]
    busy = ADCpt(EpicsSignal, "DIO:BUSY")
    capture = ADCpt(EpicsSignal, "DIO:CAPTURE")
    exposing = ADCpt(EpicsSignal, "DIO:EXPOSING")
    ready = ADCpt(EpicsSignal, "DIO:READY")
    trig = ADCpt(EpicsSignal, "DIO:TRIG")
    trig_when_ready = ADCpt(EpicsSignal, "DIO:TrigWhenReady")


class PcoDetectorSimIO(ADBase):
    _html_docs = [""]
    busy = ADCpt(EpicsSignal, "SIM:BUSY")
    dfan = ADCpt(EpicsSignal, "SIM:Dfan")
    exposing = ADCpt(EpicsSignal, "SIM:EXPOSING")
    set_busy = ADCpt(EpicsSignal, "SIM:SetBusy")
    set_exp = ADCpt(EpicsSignal, "SIM:SetExp")
    set_state = ADCpt(EpicsSignal, "SIM:SetState")
    trig = ADCpt(EpicsSignal, "SIM:TRIG")


class PerkinElmerDetectorCam(CamBase):
    _html_docs = ["PerkinElmerDoc.html"]
    pe_acquire_gain = ADCpt(EpicsSignal, "PEAcquireGain")
    pe_acquire_offset = ADCpt(EpicsSignal, "PEAcquireOffset")
    pe_corrections_dir = ADCpt(EpicsSignal, "PECorrectionsDir")
    pe_current_gain_frame = ADCpt(EpicsSignal, "PECurrentGainFrame")
    pe_current_offset_frame = ADCpt(EpicsSignal, "PECurrentOffsetFrame")
    pe_dwell_time = ADCpt(SignalWithRBV, "PEDwellTime")
    pe_frame_buff_index = ADCpt(EpicsSignal, "PEFrameBuffIndex")
    pe_gain = ADCpt(SignalWithRBV, "PEGain")
    pe_gain_available = ADCpt(EpicsSignal, "PEGainAvailable")
    pe_gain_file = ADCpt(EpicsSignal, "PEGainFile")
    pe_image_number = ADCpt(EpicsSignal, "PEImageNumber")
    pe_initialize = ADCpt(EpicsSignal, "PEInitialize")
    pe_load_gain_file = ADCpt(EpicsSignal, "PELoadGainFile")
    pe_load_pixel_correction = ADCpt(EpicsSignal, "PELoadPixelCorrection")
    pe_num_frame_buffers = ADCpt(SignalWithRBV, "PENumFrameBuffers")
    pe_num_frames_to_skip = ADCpt(SignalWithRBV, "PENumFramesToSkip")
    pe_num_gain_frames = ADCpt(EpicsSignal, "PENumGainFrames")
    pe_num_offset_frames = ADCpt(EpicsSignal, "PENumOffsetFrames")
    pe_offset_available = ADCpt(EpicsSignal, "PEOffsetAvailable")
    pe_pixel_correction_available = ADCpt(EpicsSignal, "PEPixelCorrectionAvailable")
    pe_pixel_correction_file = ADCpt(EpicsSignal, "PEPixelCorrectionFile")
    pe_save_gain_file = ADCpt(EpicsSignal, "PESaveGainFile")
    pe_skip_frames = ADCpt(SignalWithRBV, "PESkipFrames")
    pe_sync_time = ADCpt(SignalWithRBV, "PESyncTime")
    pe_system_id = ADCpt(EpicsSignal, "PESystemID")
    pe_trigger = ADCpt(EpicsSignal, "PETrigger")
    pe_use_gain = ADCpt(EpicsSignal, "PEUseGain")
    pe_use_offset = ADCpt(EpicsSignal, "PEUseOffset")
    pe_use_pixel_correction = ADCpt(EpicsSignal, "PEUsePixelCorrection")


class PSLDetectorCam(CamBase):
    _html_docs = ["PSLDoc.html"]
    file_format = ADCpt(SignalWithRBV, "FileFormat")
    tiff_comment = ADCpt(SignalWithRBV, "TIFFComment")


class PICamDetectorCam(CamBase):
    _html_docs = ["PICamDoc.html"]
    _default_configuration_attrs = CamBase._default_configuration_attrs
    version_number = ADCpt(EpicsSignal, "VersionNumber")
    camera_interface = ADCpt(EpicsSignal, "CameraInterface")
    sensor_name = ADCpt(EpicsSignal, "SensorName")
    cam_serial_num = ADCpt(EpicsSignal, "CamSerialNum")
    firmware_revision = ADCpt(EpicsSignal, "FirmwareRevision")
    available_cameras = ADCpt(SignalWithRBV, "AvailableCameras")
    camera_interface_unavailable = ADCpt(EpicsSignal, "CameraInterfaceUnavailable")
    sensor_name_unavailable = ADCpt(EpicsSignal, "SensorNameUnavailable")
    cam_serial_num_unavailable = ADCpt(EpicsSignal, "CamSerialNumUnavailable")
    firmware_revision_unavailable = ADCpt(EpicsSignal, "FirmwareRevisionUnavailable")
    unavailable_cameras = ADCpt(SignalWithRBV, "UnavailableCameras")
    exposure_time_ex = ADCpt(EpicsSignal, "ExposureTime_EX")
    shutter_closing_delay_ex = ADCpt(EpicsSignal, "ShutterClosingDelay_EX")
    shutter_delay_resolution_ex = ADCpt(EpicsSignal, "ShutterDelayResolution_EX")
    shutter_open_delay_ex = ADCpt(EpicsSignal, "ShutterOpenDelay_EX")
    shutter_timing_mode_ex = ADCpt(EpicsSignal, "ShutterTimingMode_EX")
    bracket_gating_ex = ADCpt(EpicsSignal, "BracketGating_EX")
    custom_mod_seq_ex = ADCpt(EpicsSignal, "CustomModSeq_EX")
    dif_end_gate_ex = ADCpt(EpicsSignal, "DifEndGate_EX")
    dif_start_gate_ex = ADCpt(EpicsSignal, "DifStartGate_EX")
    emi_ccd_gain_ex = ADCpt(EpicsSignal, "EMIccdGain_EX")
    emi_ccd_gain_mode_ex = ADCpt(EpicsSignal, "EMIccdGainMode_EX")
    enable_intensifier_ex = ADCpt(EpicsSignal, "EnableIntensifier_EX")
    enable_modulation_ex = ADCpt(EpicsSignal, "EnableModulation_EX")
    gating_mode_ex = ADCpt(EpicsSignal, "GatingMode_EX")
    gating_speed_ex = ADCpt(EpicsSignal, "GatingSpeed_EX")
    intensifier_diameter_ex = ADCpt(EpicsSignal, "IntensifierDiameter_EX")
    intensifier_gain_ex = ADCpt(EpicsSignal, "IntensifierGain_EX")
    intensifier_options_ex = ADCpt(EpicsSignal, "IntensifierOptions_EX")
    intensifier_status_ex = ADCpt(EpicsSignal, "IntensifierStatus_EX")
    modulation_duration_ex = ADCpt(EpicsSignal, "ModulationDuration_EX")
    modulation_frequency_ex = ADCpt(EpicsSignal, "ModulationFrequency_EX")
    phosphor_decay_delay_ex = ADCpt(EpicsSignal, "PhosphorDecayDelay_EX")
    phosphor_decay_delay_resolution_ex = ADCpt(
        EpicsSignal, "PhosphorDecayDelayResolution_EX"
    )
    phosphor_type_ex = ADCpt(EpicsSignal, "PhosphorType_EX")
    photocathode_sensitivity_ex = ADCpt(EpicsSignal, "PhotocathodeSensitivity_EX")
    repetitive_gate_ex = ADCpt(EpicsSignal, "RepetitiveGate_EX")
    repetitive_modulation_ex = ADCpt(EpicsSignal, "RepetitiveModulation_EX")
    seq_start_mod_phase_ex = ADCpt(EpicsSignal, "SeqStartModPhase_EX")
    seq_end_mod_phase_ex = ADCpt(EpicsSignal, "SeqEndModPhase_EX")
    seq_end_gate_ex = ADCpt(EpicsSignal, "SeqEndGate_EX")
    seq_gate_step_count_ex = ADCpt(EpicsSignal, "SeqGateStepCount_EX")
    seq_gate_step_iters_ex = ADCpt(EpicsSignal, "SeqGateStepIters_EX")
    seq_start_gate_ex = ADCpt(EpicsSignal, "SeqStartGate_EX")
    adc_analog_gain_ex = ADCpt(EpicsSignal, "AdcAnalogGain_EX")
    adc_bit_depth_ex = ADCpt(EpicsSignal, "AdcBitDepth_EX")
    adc_e_m_gain_ex = ADCpt(EpicsSignal, "AdcEMGain_EX")
    adc_quality_ex = ADCpt(EpicsSignal, "AdcQuality_EX")
    adc_speed_ex = ADCpt(EpicsSignal, "AdcSpeed_EX")
    correct_pixel_bias_ex = ADCpt(EpicsSignal, "CorrectPixelBias_EX")
    aux_output_ex = ADCpt(EpicsSignal, "AuxOutput_EX")
    enable_modulation_out_sig_ex = ADCpt(EpicsSignal, "EnableModulationOutSig_EX")
    modulation_out_sig_freq_ex = ADCpt(EpicsSignal, "ModulationOutSigFreq_EX")
    modulation_out_sig_ampl_ex = ADCpt(EpicsSignal, "ModulationOutSigAmpl_EX")
    enable_sync_master_ex = ADCpt(EpicsSignal, "EnableSyncMaster_EX")
    invert_out_sig_ex = ADCpt(EpicsSignal, "InvertOutSig_EX")
    output_signal_ex = ADCpt(EpicsSignal, "OutputSignal_EX")
    sync_master2_delay_ex = ADCpt(EpicsSignal, "SyncMaster2Delay_EX")
    trigger_coupling_ex = ADCpt(EpicsSignal, "TriggerCoupling_EX")
    trigger_determination_ex = ADCpt(EpicsSignal, "TriggerDetermination_EX")
    trigger_frequency_ex = ADCpt(EpicsSignal, "TriggerFrequency_EX")
    trigger_response_ex = ADCpt(EpicsSignal, "TriggerResponse_EX")
    trigger_source_ex = ADCpt(EpicsSignal, "TriggerSource_EX")
    trigger_termination_ex = ADCpt(EpicsSignal, "TriggerTermination_EX")
    trigger_threshold_ex = ADCpt(EpicsSignal, "TriggerThreshold_EX")
    accumulations_ex = ADCpt(EpicsSignal, "Accumulations_EX")
    enable_nd_readout_ex = ADCpt(EpicsSignal, "EnableNDReadout_EX")
    kinetics_window_height_ex = ADCpt(EpicsSignal, "KineticsWindowHeight_EX")
    nd_readout_period_ex = ADCpt(EpicsSignal, "NDReadoutPeriod_EX")
    readout_ctl_mode_ex = ADCpt(EpicsSignal, "ReadoutCtlMode_EX")
    readout_orientation_ex = ADCpt(EpicsSignal, "ReadoutOrientation_EX")
    readout_port_count_ex = ADCpt(EpicsSignal, "ReadoutPortCount_EX")
    readout_time_calculation_ex = ADCpt(EpicsSignal, "ReadoutTimeCalculation_EX")
    vertical_shift_rate_ex = ADCpt(EpicsSignal, "VerticalShiftRate_EX")
    disable_data_format_ex = ADCpt(EpicsSignal, "DisableDataFormat_EX")
    exact_rdout_count_max_ex = ADCpt(EpicsSignal, "ExactRdoutCountMax_EX")
    frame_rate_calc_ex = ADCpt(EpicsSignal, "FrameRateCalc_EX")
    frame_size_ex = ADCpt(EpicsSignal, "FrameSize_EX")
    frames_per_readout_ex = ADCpt(EpicsSignal, "FramesPerReadout_EX")
    frame_stride_ex = ADCpt(EpicsSignal, "FrameStride_EX")
    frame_trk_bit_depth_ex = ADCpt(EpicsSignal, "FrameTrkBitDepth_EX")
    gate_tracking_ex = ADCpt(EpicsSignal, "GateTracking_EX")
    gate_trk_bit_depth_ex = ADCpt(EpicsSignal, "GateTrkBitDepth_EX")
    mod_tracking_ex = ADCpt(EpicsSignal, "ModTracking_EX")
    mod_trk_bit_depth_ex = ADCpt(EpicsSignal, "ModTrkBitDepth_EX")
    normalize_orientation_ex = ADCpt(EpicsSignal, "NormalizeOrientation_EX")
    online_readout_calc_ex = ADCpt(EpicsSignal, "OnlineReadoutCalc_EX")
    orientation_ex = ADCpt(EpicsSignal, "Orientation_EX")
    photon_detection_mode_ex = ADCpt(EpicsSignal, "PhotonDetectionMode_EX")
    photon_detection_threshold_ex = ADCpt(EpicsSignal, "PhotonDetectionThreshold_EX")
    pixel_bit_depth_ex = ADCpt(EpicsSignal, "PixelBitDepth_EX")
    pixel_format_ex = ADCpt(EpicsSignal, "PixelFormat_EX")
    readout_count_ex = ADCpt(EpicsSignal, "ReadoutCount_EX")
    readout_rate_calc_ex = ADCpt(EpicsSignal, "ReadoutRateCalc_EX")
    readout_stride_ex = ADCpt(EpicsSignal, "ReadoutStride_EX")
    rois_ex = ADCpt(EpicsSignal, "Rois_EX")
    time_stamp_bit_depth_ex = ADCpt(EpicsSignal, "TimeStampBitDepth_EX")
    time_stamp_res_ex = ADCpt(EpicsSignal, "TimeStampRes_EX")
    time_stamps_ex = ADCpt(EpicsSignal, "TimeStamps_EX")
    track_frames_ex = ADCpt(EpicsSignal, "TrackFrames_EX")
    ccd_characteristics_ex = ADCpt(EpicsSignal, "CcdCharacteristics_EX")
    pixel_gap_height_ex = ADCpt(EpicsSignal, "PixelGapHeight_EX")
    pixel_gap_width_ex = ADCpt(EpicsSignal, "PixelGapWidth_EX")
    pixel_height_ex = ADCpt(EpicsSignal, "PixelHeight_EX")
    pixel_width_ex = ADCpt(EpicsSignal, "PixelWidth_EX")
    sens_act_bottom_margin_ex = ADCpt(EpicsSignal, "SensActBottomMargin_EX")
    sens_act_height_ex = ADCpt(EpicsSignal, "SensActHeight_EX")
    sens_act_left_margin_ex = ADCpt(EpicsSignal, "SensActLeftMargin_EX")
    sens_act_right_margin_ex = ADCpt(EpicsSignal, "SensActRightMargin_EX")
    sens_act_top_margin_ex = ADCpt(EpicsSignal, "SensActTopMargin_EX")
    sens_act_width_ex = ADCpt(EpicsSignal, "SensActWidth_EX")
    sens_mask_bottom_margin_ex = ADCpt(EpicsSignal, "SensMaskBottomMargin_EX")
    sens_mask_height_ex = ADCpt(EpicsSignal, "SensMaskHeight_EX")
    sens_mask_top_margin_ex = ADCpt(EpicsSignal, "SensMaskTopMargin_EX")
    sensor_active_height2_ex = ADCpt(EpicsSignal, "SensorActiveHeight2_EX")
    sensor_mask_height2_ex = ADCpt(EpicsSignal, "SensorMaskHeight2_EX")
    sensor_type_ex = ADCpt(EpicsSignal, "SensorType_EX")
    active_bottom_margin_ex = ADCpt(EpicsSignal, "ActiveBottomMargin_EX")
    active_height_ex = ADCpt(EpicsSignal, "ActiveHeight_EX")
    active_left_margin_ex = ADCpt(EpicsSignal, "ActiveLeftMargin_EX")
    active_right_margin_ex = ADCpt(EpicsSignal, "ActiveRightMargin_EX")
    active_top_margin_ex = ADCpt(EpicsSignal, "ActiveTopMargin_EX")
    active_width_ex = ADCpt(EpicsSignal, "ActiveWidth_EX")
    mask_bottom_margin_ex = ADCpt(EpicsSignal, "MaskBottomMargin_EX")
    mask_height_ex = ADCpt(EpicsSignal, "MaskHeight_EX")
    mask_top_margin_ex = ADCpt(EpicsSignal, "MaskTopMargin_EX")
    active_height2_ex = ADCpt(EpicsSignal, "ActiveHeight2_EX")
    masked_height2_ex = ADCpt(EpicsSignal, "MaskedHeight2_EX")
    clean_before_exp_ex = ADCpt(EpicsSignal, "CleanBeforeExp_EX")
    clean_cycle_count_ex = ADCpt(EpicsSignal, "CleanCycleCount_EX")
    clean_cycle_height_ex = ADCpt(EpicsSignal, "CleanCycleHeight_EX")
    clean_section_final_height_ex = ADCpt(EpicsSignal, "CleanSectionFinalHeight_EX")
    clean_section_final_height_count_ex = ADCpt(
        EpicsSignal, "CleanSectionFinalHeightCount_EX"
    )
    clean_serial_register_ex = ADCpt(EpicsSignal, "CleanSerialRegister_EX")
    clean_until_trigger_ex = ADCpt(EpicsSignal, "CleanUntilTrigger_EX")
    disable_cooling_fan_ex = ADCpt(EpicsSignal, "DisableCoolingFan_EX")
    enable_window_htr_ex = ADCpt(EpicsSignal, "EnableWindowHtr_EX")
    sens_temp_reading_ex = ADCpt(EpicsSignal, "SensTempReading_EX")
    sens_temp_setpt_ex = ADCpt(EpicsSignal, "SensTempSetpt_EX")
    sens_temp_status_ex = ADCpt(EpicsSignal, "SensTempStatus_EX")
    exposure_time_pr = ADCpt(EpicsSignal, "ExposureTime_PR")
    shutter_closing_delay_pr = ADCpt(EpicsSignal, "ShutterClosingDelay_PR")
    shutter_delay_resolution_pr = ADCpt(EpicsSignal, "ShutterDelayResolution_PR")
    shutter_open_delay_pr = ADCpt(EpicsSignal, "ShutterOpenDelay_PR")
    shutter_timing_mode_pr = ADCpt(EpicsSignal, "ShutterTimingMode_PR")
    bracket_gating_pr = ADCpt(EpicsSignal, "BracketGating_PR")
    custom_mod_seq_pr = ADCpt(EpicsSignal, "CustomModSeq_PR")
    dif_end_gate_pr = ADCpt(EpicsSignal, "DifEndGate_PR")
    dif_start_gate_pr = ADCpt(EpicsSignal, "DifStartGate_PR")
    emi_ccd_gain_pr = ADCpt(EpicsSignal, "EMIccdGain_PR")
    emi_ccd_gain_mode_pr = ADCpt(EpicsSignal, "EMIccdGainMode_PR")
    enable_intensifier_pr = ADCpt(EpicsSignal, "EnableIntensifier_PR")
    enable_modulation_pr = ADCpt(EpicsSignal, "EnableModulation_PR")
    gating_mode_pr = ADCpt(EpicsSignal, "GatingMode_PR")
    gating_speed_pr = ADCpt(EpicsSignal, "GatingSpeed_PR")
    intensifier_diameter_pr = ADCpt(EpicsSignal, "IntensifierDiameter_PR")
    intensifier_gain_pr = ADCpt(EpicsSignal, "IntensifierGain_PR")
    intensifier_options_pr = ADCpt(EpicsSignal, "IntensifierOptions_PR")
    intensifier_status_pr = ADCpt(EpicsSignal, "IntensifierStatus_PR")
    modulation_duration_pr = ADCpt(EpicsSignal, "ModulationDuration_PR")
    modulation_frequency_pr = ADCpt(EpicsSignal, "ModulationFrequency_PR")
    phosphor_decay_delay_pr = ADCpt(EpicsSignal, "PhosphorDecayDelay_PR")
    phosphor_decay_delay_resolution_pr = ADCpt(
        EpicsSignal, "PhosphorDecayDelayResolution_PR"
    )
    phosphor_type_pr = ADCpt(EpicsSignal, "PhosphorType_PR")
    photocathode_sensitivity_pr = ADCpt(EpicsSignal, "PhotocathodeSensitivity_PR")
    repetitive_gate_pr = ADCpt(EpicsSignal, "RepetitiveGate_PR")
    repetitive_modulation_pr = ADCpt(EpicsSignal, "RepetitiveModulation_PR")
    seq_start_mod_phase_pr = ADCpt(EpicsSignal, "SeqStartModPhase_PR")
    seq_end_mod_phase_pr = ADCpt(EpicsSignal, "SeqEndModPhase_PR")
    seq_end_gate_pr = ADCpt(EpicsSignal, "SeqEndGate_PR")
    seq_gate_step_count_pr = ADCpt(EpicsSignal, "SeqGateStepCount_PR")
    seq_gate_step_iters_pr = ADCpt(EpicsSignal, "SeqGateStepIters_PR")
    seq_start_gate_pr = ADCpt(EpicsSignal, "SeqStartGate_PR")
    adc_analog_gain_pr = ADCpt(EpicsSignal, "AdcAnalogGain_PR")
    adc_bit_depth_pr = ADCpt(EpicsSignal, "AdcBitDepth_PR")
    adc_e_m_gain_pr = ADCpt(EpicsSignal, "AdcEMGain_PR")
    adc_quality_pr = ADCpt(EpicsSignal, "AdcQuality_PR")
    adc_speed_pr = ADCpt(EpicsSignal, "AdcSpeed_PR")
    correct_pixel_bias_pr = ADCpt(EpicsSignal, "CorrectPixelBias_PR")
    aux_output_pr = ADCpt(EpicsSignal, "AuxOutput_PR")
    enable_modulation_out_sig_pr = ADCpt(EpicsSignal, "EnableModulationOutSig_PR")
    modulation_out_sig_freq_pr = ADCpt(EpicsSignal, "ModulationOutSigFreq_PR")
    modulation_out_sig_ampl_pr = ADCpt(EpicsSignal, "ModulationOutSigAmpl_PR")
    enable_sync_master_pr = ADCpt(EpicsSignal, "EnableSyncMaster_PR")
    invert_out_sig_pr = ADCpt(EpicsSignal, "InvertOutSig_PR")
    output_signal_pr = ADCpt(EpicsSignal, "OutputSignal_PR")
    sync_master2_delay_pr = ADCpt(EpicsSignal, "SyncMaster2Delay_PR")
    trigger_coupling_pr = ADCpt(EpicsSignal, "TriggerCoupling_PR")
    trigger_determination_pr = ADCpt(EpicsSignal, "TriggerDetermination_PR")
    trigger_frequency_pr = ADCpt(EpicsSignal, "TriggerFrequency_PR")
    trigger_response_pr = ADCpt(EpicsSignal, "TriggerResponse_PR")
    trigger_source_pr = ADCpt(EpicsSignal, "TriggerSource_PR")
    trigger_termination_pr = ADCpt(EpicsSignal, "TriggerTermination_PR")
    trigger_threshold_pr = ADCpt(EpicsSignal, "TriggerThreshold_PR")
    accumulations_pr = ADCpt(EpicsSignal, "Accumulations_PR")
    enable_nd_readout_pr = ADCpt(EpicsSignal, "EnableNDReadout_PR")
    kinetics_window_height_pr = ADCpt(EpicsSignal, "KineticsWindowHeight_PR")
    nd_readout_period_pr = ADCpt(EpicsSignal, "NDReadoutPeriod_PR")
    readout_ctl_mode_pr = ADCpt(EpicsSignal, "ReadoutCtlMode_PR")
    readout_orientation_pr = ADCpt(EpicsSignal, "ReadoutOrientation_PR")
    readout_port_count_pr = ADCpt(EpicsSignal, "ReadoutPortCount_PR")
    readout_time_calculation_pr = ADCpt(EpicsSignal, "ReadoutTimeCalculation_PR")
    vertical_shift_rate_pr = ADCpt(EpicsSignal, "VerticalShiftRate_PR")
    disable_data_format_pr = ADCpt(EpicsSignal, "DisableDataFormat_PR")
    exact_rdout_count_max_pr = ADCpt(EpicsSignal, "ExactRdoutCountMax_PR")
    frame_rate_calc_pr = ADCpt(EpicsSignal, "FrameRateCalc_PR")
    frame_size_pr = ADCpt(EpicsSignal, "FrameSize_PR")
    frames_per_readout_pr = ADCpt(EpicsSignal, "FramesPerReadout_PR")
    frame_stride_pr = ADCpt(EpicsSignal, "FrameStride_PR")
    frame_trk_bit_depth_pr = ADCpt(EpicsSignal, "FrameTrkBitDepth_PR")
    gate_tracking_pr = ADCpt(EpicsSignal, "GateTracking_PR")
    gate_trk_bit_depth_pr = ADCpt(EpicsSignal, "GateTrkBitDepth_PR")
    mod_tracking_pr = ADCpt(EpicsSignal, "ModTracking_PR")
    mod_trk_bit_depth_pr = ADCpt(EpicsSignal, "ModTrkBitDepth_PR")
    normalize_orientation_pr = ADCpt(EpicsSignal, "NormalizeOrientation_PR")
    online_readout_calc_pr = ADCpt(EpicsSignal, "OnlineReadoutCalc_PR")
    orientation_pr = ADCpt(EpicsSignal, "Orientation_PR")
    photon_detection_mode_pr = ADCpt(EpicsSignal, "PhotonDetectionMode_PR")
    photon_detection_threshold_pr = ADCpt(EpicsSignal, "PhotonDetectionThreshold_PR")
    pixel_bit_depth_pr = ADCpt(EpicsSignal, "PixelBitDepth_PR")
    pixel_format_pr = ADCpt(EpicsSignal, "PixelFormat_PR")
    readout_count_pr = ADCpt(EpicsSignal, "ReadoutCount_PR")
    readout_rate_calc_pr = ADCpt(EpicsSignal, "ReadoutRateCalc_PR")
    readout_stride_pr = ADCpt(EpicsSignal, "ReadoutStride_PR")
    rois_pr = ADCpt(EpicsSignal, "Rois_PR")
    time_stamp_bit_depth_pr = ADCpt(EpicsSignal, "TimeStampBitDepth_PR")
    time_stamp_res_pr = ADCpt(EpicsSignal, "TimeStampRes_PR")
    time_stamps_pr = ADCpt(EpicsSignal, "TimeStamps_PR")
    track_frames_pr = ADCpt(EpicsSignal, "TrackFrames_PR")
    ccd_characteristics_pr = ADCpt(EpicsSignal, "CcdCharacteristics_PR")
    pixel_gap_height_pr = ADCpt(EpicsSignal, "PixelGapHeight_PR")
    pixel_gap_width_pr = ADCpt(EpicsSignal, "PixelGapWidth_PR")
    pixel_height_pr = ADCpt(EpicsSignal, "PixelHeight_PR")
    pixel_width_pr = ADCpt(EpicsSignal, "PixelWidth_PR")
    sens_act_bottom_margin_pr = ADCpt(EpicsSignal, "SensActBottomMargin_PR")
    sens_act_height_pr = ADCpt(EpicsSignal, "SensActHeight_PR")
    sens_act_left_margin_pr = ADCpt(EpicsSignal, "SensActLeftMargin_PR")
    sens_act_right_margin_pr = ADCpt(EpicsSignal, "SensActRightMargin_PR")
    sens_act_top_margin_pr = ADCpt(EpicsSignal, "SensActTopMargin_PR")
    sens_act_width_pr = ADCpt(EpicsSignal, "SensActWidth_PR")
    sens_mask_bottom_margin_pr = ADCpt(EpicsSignal, "SensMaskBottomMargin_PR")
    sens_mask_height_pr = ADCpt(EpicsSignal, "SensMaskHeight_PR")
    sens_mask_top_margin_pr = ADCpt(EpicsSignal, "SensMaskTopMargin_PR")
    sensor_active_height2_pr = ADCpt(EpicsSignal, "SensorActiveHeight2_PR")
    sensor_mask_height2_pr = ADCpt(EpicsSignal, "SensorMaskHeight2_PR")
    sensor_type_pr = ADCpt(EpicsSignal, "SensorType_PR")
    active_bottom_margin_pr = ADCpt(EpicsSignal, "ActiveBottomMargin_PR")
    active_height_pr = ADCpt(EpicsSignal, "ActiveHeight_PR")
    active_left_margin_pr = ADCpt(EpicsSignal, "ActiveLeftMargin_PR")
    active_right_margin_pr = ADCpt(EpicsSignal, "ActiveRightMargin_PR")
    active_top_margin_pr = ADCpt(EpicsSignal, "ActiveTopMargin_PR")
    active_width_pr = ADCpt(EpicsSignal, "ActiveWidth_PR")
    mask_bottom_margin_pr = ADCpt(EpicsSignal, "MaskBottomMargin_PR")
    mask_height_pr = ADCpt(EpicsSignal, "MaskHeight_PR")
    mask_top_margin_pr = ADCpt(EpicsSignal, "MaskTopMargin_PR")
    active_height2_pr = ADCpt(EpicsSignal, "ActiveHeight2_PR")
    masked_height2_pr = ADCpt(EpicsSignal, "MaskedHeight2_PR")
    clean_before_exp_pr = ADCpt(EpicsSignal, "CleanBeforeExp_PR")
    clean_cycle_count_pr = ADCpt(EpicsSignal, "CleanCycleCount_PR")
    clean_cycle_height_pr = ADCpt(EpicsSignal, "CleanCycleHeight_PR")
    clean_section_final_height_pr = ADCpt(EpicsSignal, "CleanSectionFinalHeight_PR")
    clean_section_final_height_count_pr = ADCpt(
        EpicsSignal, "CleanSectionFinalHeightCount_PR"
    )
    clean_serial_register_pr = ADCpt(EpicsSignal, "CleanSerialRegister_PR")
    clean_until_trigger_pr = ADCpt(EpicsSignal, "CleanUntilTrigger_PR")
    disable_cooling_fan_pr = ADCpt(EpicsSignal, "DisableCoolingFan_PR")
    enable_window_htr_pr = ADCpt(EpicsSignal, "EnableWindowHtr_PR")
    sens_temp_reading_pr = ADCpt(EpicsSignal, "SensTempReading_PR")
    sens_temp_setpt_pr = ADCpt(EpicsSignal, "SensTempSetpt_PR")
    sens_temp_status_pr = ADCpt(EpicsSignal, "SensTempStatus_PR")
    shutter_delay_resolution = ADCpt(SignalWithRBV, "ShutterDelayResolution")
    shutter_timing_mode = ADCpt(SignalWithRBV, "ShutterTimingMode")
    bracket_gating = ADCpt(SignalWithRBV, "BracketGating")
    emi_ccd_gain = ADCpt(SignalWithRBV, "EMIccdGain")
    emi_ccd_gain_control_mode = ADCpt(SignalWithRBV, "EMIccdGainControlMode")
    enable_intensifier = ADCpt(SignalWithRBV, "EnableIntensifier")
    enable_modulation = ADCpt(SignalWithRBV, "EnableModulation")
    gating_mode = ADCpt(SignalWithRBV, "GatingMode")
    gating_speed = ADCpt(EpicsSignal, "GatingSpeed")
    intensifier_diameter = ADCpt(EpicsSignal, "IntensifierDiameter")
    intensifier_gain = ADCpt(SignalWithRBV, "IntensifierGain")
    modulation_duration = ADCpt(SignalWithRBV, "ModulationDuration")
    modulation_frequency = ADCpt(SignalWithRBV, "ModulationFrequency")
    phosphor_decay_delay = ADCpt(SignalWithRBV, "PhosphorDecayDelay")
    phosphor_decay_delay_resolution = ADCpt(
        SignalWithRBV, "PhosphorDecayDelayResolution"
    )
    adc_analog_gain = ADCpt(SignalWithRBV, "AdcAnalogGain")
    adc_bit_depth = ADCpt(SignalWithRBV, "AdcBitDepth")
    adc_quality = ADCpt(SignalWithRBV, "AdcQuality")
    adc_speed = ADCpt(SignalWithRBV, "AdcSpeed")
    correct_pixel_bias = ADCpt(SignalWithRBV, "CorrectPixelBias")
    enable_modulation_output_signal = ADCpt(
        SignalWithRBV, "EnableModulationOutputSignal"
    )
    modulation_output_signal_frequency = ADCpt(
        SignalWithRBV, "ModulationOutputSignalFrequency"
    )
    modulation_output_signal_amplitude = ADCpt(
        SignalWithRBV, "ModulationOutputSignalAmplitude"
    )
    enable_sync_master = ADCpt(SignalWithRBV, "EnableSyncMaster")
    invert_output_signal = ADCpt(SignalWithRBV, "InvertOutputSignal")
    output_signal = ADCpt(SignalWithRBV, "OutputSignal")
    sync_master2_delay = ADCpt(SignalWithRBV, "SyncMaster2Delay")
    trigger_coupling = ADCpt(SignalWithRBV, "TriggerCoupling")
    trigger_determination = ADCpt(SignalWithRBV, "TriggerDetermination")
    trigger_frequency = ADCpt(SignalWithRBV, "TriggerFrequency")
    trigger_source = ADCpt(SignalWithRBV, "TriggerSource")
    trigger_termination = ADCpt(SignalWithRBV, "TriggerTermination")
    trigger_threshold = ADCpt(SignalWithRBV, "TriggerThreshold")
    accumulations = ADCpt(SignalWithRBV, "Accumulations")
    enable_non_destructive_readout = ADCpt(SignalWithRBV, "EnableNondestructiveReadout")
    kinetics_window_height = ADCpt(SignalWithRBV, "KineticsWindowHeight")
    nondestructive_readout_period = ADCpt(SignalWithRBV, "NondestructiveReadoutPeriod")
    readout_control_mode = ADCpt(SignalWithRBV, "ReadoutControlMode")
    readout_orientation = ADCpt(EpicsSignal, "ReadoutOrientation")
    readout_port_count = ADCpt(SignalWithRBV, "ReadoutPortCount")
    readout_time_calc = ADCpt(EpicsSignal, "ReadoutTimeCalc")
    vertical_shift_rate = ADCpt(SignalWithRBV, "VerticalShiftRate")
    disable_data_formatting = ADCpt(SignalWithRBV, "DisableDataFormatting")
    exact_readout_count_max = ADCpt(EpicsSignal, "ExactReadoutCountMax")
    frame_rate_calc = ADCpt(EpicsSignal, "FrameRateCalc")
    frames_per_readout = ADCpt(EpicsSignal, "FramesPerReadout")
    frame_stride = ADCpt(EpicsSignal, "FrameStride")
    frame_tracking_bit_depth = ADCpt(SignalWithRBV, "FrameTrackingBitDepth")
    gate_tracking = ADCpt(SignalWithRBV, "GateTracking")
    gate_tracking_bit_depth = ADCpt(SignalWithRBV, "GateTrackingBitDepth")
    modulation_tracking = ADCpt(SignalWithRBV, "ModulationTracking")
    modulation_tracking_bit_depth = ADCpt(SignalWithRBV, "ModulationTrackingBitDepth")
    normalize_orientation = ADCpt(SignalWithRBV, "NormalizeOrientation")
    online_readout_rate_calc = ADCpt(EpicsSignal, "OnlineReadoutRateCalc")
    orientation = ADCpt(EpicsSignal, "Orientation")
    photon_detection_mode = ADCpt(SignalWithRBV, "PhotonDetectionMode")
    photon_detection_threshold = ADCpt(SignalWithRBV, "PhotonDetectionThreshold")
    pixel_bit_depth = ADCpt(EpicsSignal, "PixelBitDepth")
    pixel_format = ADCpt(SignalWithRBV, "PixelFormat")
    readout_count = ADCpt(SignalWithRBV, "ReadoutCount")
    readout_rate_calc = ADCpt(EpicsSignal, "ReadoutRateCalc")
    readout_stride = ADCpt(EpicsSignal, "ReadoutStride")
    time_stamp_bit_depth = ADCpt(SignalWithRBV, "TimeStampBitDepth")
    time_stamp_resolution = ADCpt(SignalWithRBV, "TimeStampResolution")
    time_stamps = ADCpt(SignalWithRBV, "TimeStamps")
    track_frames = ADCpt(SignalWithRBV, "TrackFrames")
    ccd_characteristics = ADCpt(EpicsSignal, "CcdCharacteristics")
    pixel_gap_height = ADCpt(EpicsSignal, "PixelGapHeight")
    pixel_gap_width = ADCpt(EpicsSignal, "PixelGapWidth")
    pixel_height = ADCpt(EpicsSignal, "PixelHeight")
    pixel_width = ADCpt(EpicsSignal, "PixelWidth")
    sensor_active_bottom_margin = ADCpt(EpicsSignal, "SensorActiveBottomMargin")
    sensor_active_left_margin = ADCpt(EpicsSignal, "SensorActiveLeftMargin")
    sensor_active_right_margin = ADCpt(EpicsSignal, "SensorActiveRightMargin")
    sensor_active_top_margin = ADCpt(EpicsSignal, "SensorActiveTopMargin")
    sensor_masked_bottom_margin = ADCpt(EpicsSignal, "SensorMaskedBottomMargin")
    sensor_masked_height = ADCpt(EpicsSignal, "SensorMaskedHeight")
    sensor_masked_top_margin = ADCpt(EpicsSignal, "SensorMaskedTopMargin")
    sensor_secondary_active_height = ADCpt(EpicsSignal, "SensorSecondaryActiveHeight")
    sensor_secondary_masked_height = ADCpt(EpicsSignal, "SensorSecondaryMaskedHeight")
    sensor_type = ADCpt(EpicsSignal, "SensorType")
    active_bottom_margin = ADCpt(SignalWithRBV, "ActiveBottomMargin")
    active_height = ADCpt(SignalWithRBV, "ActiveHeight")
    active_left_margin = ADCpt(SignalWithRBV, "ActiveLeftMargin")
    active_right_margin = ADCpt(SignalWithRBV, "ActiveRightMargin")
    active_top_margin = ADCpt(SignalWithRBV, "ActiveTopMargin")
    active_width = ADCpt(SignalWithRBV, "ActiveWidth")
    masked_bottom_margin = ADCpt(SignalWithRBV, "MaskedBottomMargin")
    masked_height = ADCpt(SignalWithRBV, "MaskedHeight")
    masked_top_margin = ADCpt(SignalWithRBV, "MaskedTopMargin")
    secondary_active_height = ADCpt(SignalWithRBV, "SecondaryActiveHeight")
    secondary_masked_height = ADCpt(SignalWithRBV, "SecondaryMaskedHeight")
    clean_before_exposure = ADCpt(SignalWithRBV, "CleanBeforeExposure")
    clean_cycle_count = ADCpt(SignalWithRBV, "CleanCycleCount")
    clean_cycle_height = ADCpt(SignalWithRBV, "CleanCycleHeight")
    clean_section_final_height = ADCpt(SignalWithRBV, "CleanSectionFinalHeight")
    clean_section_final_height_count = ADCpt(
        SignalWithRBV, "CleanSectionFinalHeightCount"
    )
    clean_serial_register = ADCpt(SignalWithRBV, "CleanSerialRegister")
    clean_until_trigger = ADCpt(SignalWithRBV, "CleanUntilTrigger")
    disable_cooling_fan = ADCpt(SignalWithRBV, "DisableCoolingFan")
    enable_sensor_window_heater = ADCpt(SignalWithRBV, "EnableSensorWindowHeater")
    sensor_temperature_status = ADCpt(EpicsSignal, "SensorTemperatureStatus")
    enable_roi_min_x_input = ADCpt(EpicsSignal, "EnableROIMinXInput")
    enable_roi_size_x_input = ADCpt(EpicsSignal, "EnableROISizeXInput")
    enable_roi_min_y_input = ADCpt(EpicsSignal, "EnableROIMinYInput")
    enable_roi_size_y_input = ADCpt(EpicsSignal, "EnableROISizeYInput")


class PilatusDetectorCam(CamBase):
    _html_docs = ["pilatusDoc.html"]
    alpha = ADCpt(EpicsSignal, "Alpha")
    angle_incr = ADCpt(EpicsSignal, "AngleIncr")
    armed = ADCpt(EpicsSignal, "Armed")
    bad_pixel_file = ADCpt(EpicsSignal, "BadPixelFile")
    beam_x = ADCpt(EpicsSignal, "BeamX")
    beam_y = ADCpt(EpicsSignal, "BeamY")
    camserver_asyn = ADCpt(EpicsSignal, "CamserverAsyn")
    cbf_template_file = ADCpt(EpicsSignal, "CbfTemplateFile")
    chi = ADCpt(EpicsSignal, "Chi")
    delay_time = ADCpt(SignalWithRBV, "DelayTime")
    det_2theta = ADCpt(EpicsSignal, "Det2theta")
    det_dist = ADCpt(EpicsSignal, "DetDist")
    det_v_offset = ADCpt(EpicsSignal, "DetVOffset")
    energy_high = ADCpt(EpicsSignal, "EnergyHigh")
    energy_low = ADCpt(EpicsSignal, "EnergyLow")
    file_format = ADCpt(SignalWithRBV, "FileFormat")
    filter_transm = ADCpt(EpicsSignal, "FilterTransm")
    flat_field_file = ADCpt(EpicsSignal, "FlatFieldFile")
    flat_field_valid = ADCpt(EpicsSignal, "FlatFieldValid")
    flux = ADCpt(EpicsSignal, "Flux")
    gain_menu = ADCpt(EpicsSignal, "GainMenu")
    gap_fill = ADCpt(SignalWithRBV, "GapFill")
    header_string = ADCpt(EpicsSignal, "HeaderString")
    humid0 = ADCpt(EpicsSignalRO, "Humid0_RBV")
    humid1 = ADCpt(EpicsSignalRO, "Humid1_RBV")
    humid2 = ADCpt(EpicsSignalRO, "Humid2_RBV")
    image_file_tmot = ADCpt(EpicsSignal, "ImageFileTmot")
    kappa = ADCpt(EpicsSignal, "Kappa")
    min_flat_field = ADCpt(SignalWithRBV, "MinFlatField")
    num_bad_pixels = ADCpt(EpicsSignal, "NumBadPixels")
    num_oscill = ADCpt(EpicsSignal, "NumOscill")
    oscill_axis = ADCpt(EpicsSignal, "OscillAxis")
    phi = ADCpt(EpicsSignal, "Phi")
    pixel_cut_off = ADCpt(EpicsSignalRO, "PixelCutOff_RBV")
    polarization = ADCpt(EpicsSignal, "Polarization")
    start_angle = ADCpt(EpicsSignal, "StartAngle")
    tvx_version = ADCpt(EpicsSignalRO, "TVXVersion_RBV")
    temp0 = ADCpt(EpicsSignalRO, "Temp0_RBV")
    temp1 = ADCpt(EpicsSignalRO, "Temp1_RBV")
    temp2 = ADCpt(EpicsSignalRO, "Temp2_RBV")
    threshold_apply = ADCpt(EpicsSignal, "ThresholdApply")
    threshold_auto_apply = ADCpt(SignalWithRBV, "ThresholdAutoApply")
    threshold_energy = ADCpt(SignalWithRBV, "ThresholdEnergy")
    wavelength = ADCpt(EpicsSignal, "Wavelength")


class PixiradDetectorCam(CamBase):
    _html_docs = ["PixiradDoc.html"]

    auto_calibrate = ADCpt(EpicsSignal, "AutoCalibrate")
    humidity_box = ADCpt(EpicsSignalRO, "BoxHumidity_RBV")
    colors_collected = ADCpt(EpicsSignalRO, "ColorsCollected_RBV")
    cooling_state = ADCpt(SignalWithRBV, "CoolingState")
    cooling_status = ADCpt(EpicsSignalRO, "CoolingStatus_RBV")
    dew_point = ADCpt(EpicsSignalRO, "DewPoint_RBV")
    frame_type = ADCpt(SignalWithRBV, "FrameType")
    hv_actual = ADCpt(EpicsSignalRO, "HVActual_RBV")
    hv_current = ADCpt(EpicsSignalRO, "HVCurrent_RBV")
    hv_mode = ADCpt(SignalWithRBV, "HVMode")
    hv_state = ADCpt(SignalWithRBV, "HVState")
    hv_value = ADCpt(SignalWithRBV, "HVValue")
    peltier_power = ADCpt(EpicsSignalRO, "PeltierPower_RBV")
    sync_in_polarity = ADCpt(SignalWithRBV, "SyncInPolarity")
    sync_out_function = ADCpt(SignalWithRBV, "SyncOutFunction")
    sync_out_polarity = ADCpt(SignalWithRBV, "SyncOutPolarity")
    system_reset = ADCpt(EpicsSignal, "SystemReset")

    temperature = ADCpt(SignalWithRBV, "Temperature")
    temperature_actual = ADCpt(EpicsSignal, "TemperatureActual")
    temperature_box = ADCpt(EpicsSignalRO, "BoxTemperature_RBV")
    temperature_hot = ADCpt(EpicsSignalRO, "HotTemperature_RBV")

    threshold_1_actual = ADCpt(EpicsSignalRO, "ThresholdActual1_RBV")
    threshold_2_actual = ADCpt(EpicsSignalRO, "ThresholdActual2_RBV")
    threshold_3_actual = ADCpt(EpicsSignalRO, "ThresholdActual3_RBV")
    threshold_4_actual = ADCpt(EpicsSignalRO, "ThresholdActual4_RBV")
    thresholds_actual = DDC(
        ad_group(
            EpicsSignalRO,
            (
                ("threshold_1", "ThresholdActual1_RBV"),
                ("threshold_2", "ThresholdActual2_RBV"),
                ("threshold_3", "ThresholdActual3_RBV"),
                ("threshold_4", "ThresholdActual4_RBV"),
            ),
        ),
        doc="Actual thresholds",
    )

    threshold_1 = ADCpt(SignalWithRBV, "Threshold1")
    threshold_2 = ADCpt(SignalWithRBV, "Threshold2")
    threshold_3 = ADCpt(SignalWithRBV, "Threshold3")
    threshold_4 = ADCpt(SignalWithRBV, "Threshold4")
    thresholds = DDC(
        ad_group(
            SignalWithRBV,
            (
                ("threshold_1", "Threshold1"),
                ("threshold_2", "Threshold2"),
                ("threshold_3", "Threshold3"),
                ("threshold_4", "Threshold4"),
            ),
        ),
        doc="Thresholds",
    )

    udp_buffers_free = ADCpt(EpicsSignalRO, "UDPBuffersFree_RBV")
    udp_buffers_max = ADCpt(EpicsSignalRO, "UDPBuffersMax_RBV")
    udp_buffers_read = ADCpt(EpicsSignalRO, "UDPBuffersRead_RBV")
    udp_speed = ADCpt(EpicsSignalRO, "UDPSpeed_RBV")


class PointGreyDetectorCam(CamBase):
    _html_docs = ["PointGreyDoc.html"]

    bandwidth = ADCpt(EpicsSignal, "Bandwidth")
    binning_mode = ADCpt(SignalWithRBV, "BinningMode")
    convert_pixel_format = ADCpt(SignalWithRBV, "ConvertPixelFormat")
    corrupt_frames = ADCpt(EpicsSignalRO, "CorruptFrames_RBV")
    driver_dropped = ADCpt(EpicsSignalRO, "DriverDropped_RBV")
    dropped_frames = ADCpt(EpicsSignalRO, "DroppedFrames_RBV")
    firmware_version = ADCpt(EpicsSignal, "FirmwareVersion")
    format7_mode = ADCpt(SignalWithRBV, "Format7Mode")
    frame_rate = ADCpt(SignalWithRBV, "FrameRate")
    max_packet_size = ADCpt(EpicsSignal, "MaxPacketSize")
    packet_delay_actual = ADCpt(EpicsSignal, "PacketDelayActual")
    packet_delay = ADCpt(SignalWithRBV, "PacketDelay")
    packet_size_actual = ADCpt(EpicsSignal, "PacketSizeActual")
    packet_size = ADCpt(SignalWithRBV, "PacketSize")
    pixel_format = ADCpt(SignalWithRBV, "PixelFormat")
    read_status = ADCpt(EpicsSignal, "ReadStatus")
    serial_number = ADCpt(EpicsSignal, "SerialNumber")
    skip_frames = ADCpt(SignalWithRBV, "SkipFrames")
    software_trigger = ADCpt(EpicsSignal, "SoftwareTrigger")
    software_version = ADCpt(EpicsSignal, "SoftwareVersion")
    strobe_delay = ADCpt(SignalWithRBV, "StrobeDelay")
    strobe_duration = ADCpt(SignalWithRBV, "StrobeDuration")
    strobe_enable = ADCpt(SignalWithRBV, "StrobeEnable")
    strobe_polarity = ADCpt(SignalWithRBV, "StrobePolarity")
    strobe_source = ADCpt(SignalWithRBV, "StrobeSource")
    time_stamp_mode = ADCpt(SignalWithRBV, "TimeStampMode")
    transmit_failed = ADCpt(EpicsSignalRO, "TransmitFailed_RBV")
    trigger_polarity = ADCpt(SignalWithRBV, "TriggerPolarity")
    trigger_source = ADCpt(SignalWithRBV, "TriggerSource")
    video_mode = ADCpt(SignalWithRBV, "VideoMode")


class ProsilicaDetectorCam(CamBase):
    _html_docs = ["prosilicaDoc.html"]
    ps_bad_frame_counter = ADCpt(EpicsSignalRO, "PSBadFrameCounter_RBV")
    ps_byte_rate = ADCpt(SignalWithRBV, "PSByteRate")
    ps_driver_type = ADCpt(EpicsSignalRO, "PSDriverType_RBV")
    ps_filter_version = ADCpt(EpicsSignalRO, "PSFilterVersion_RBV")
    ps_frame_rate = ADCpt(EpicsSignalRO, "PSFrameRate_RBV")
    ps_frames_completed = ADCpt(EpicsSignalRO, "PSFramesCompleted_RBV")
    ps_frames_dropped = ADCpt(EpicsSignalRO, "PSFramesDropped_RBV")
    ps_packet_size = ADCpt(EpicsSignalRO, "PSPacketSize_RBV")
    ps_packets_erroneous = ADCpt(EpicsSignalRO, "PSPacketsErroneous_RBV")
    ps_packets_missed = ADCpt(EpicsSignalRO, "PSPacketsMissed_RBV")
    ps_packets_received = ADCpt(EpicsSignalRO, "PSPacketsReceived_RBV")
    ps_packets_requested = ADCpt(EpicsSignalRO, "PSPacketsRequested_RBV")
    ps_packets_resent = ADCpt(EpicsSignalRO, "PSPacketsResent_RBV")
    ps_read_statistics = ADCpt(EpicsSignal, "PSReadStatistics")
    ps_reset_timer = ADCpt(EpicsSignal, "PSResetTimer")
    ps_timestamp_type = ADCpt(SignalWithRBV, "PSTimestampType")
    strobe1_ctl_duration = ADCpt(SignalWithRBV, "Strobe1CtlDuration")
    strobe1_delay = ADCpt(SignalWithRBV, "Strobe1Delay")
    strobe1_duration = ADCpt(SignalWithRBV, "Strobe1Duration")
    strobe1_mode = ADCpt(SignalWithRBV, "Strobe1Mode")
    sync_in1_level = ADCpt(EpicsSignalRO, "SyncIn1Level_RBV")
    sync_in2_level = ADCpt(EpicsSignalRO, "SyncIn2Level_RBV")
    sync_out1_invert = ADCpt(SignalWithRBV, "SyncOut1Invert")
    sync_out1_level = ADCpt(SignalWithRBV, "SyncOut1Level")
    sync_out1_mode = ADCpt(SignalWithRBV, "SyncOut1Mode")
    sync_out2_invert = ADCpt(SignalWithRBV, "SyncOut2Invert")
    sync_out2_level = ADCpt(SignalWithRBV, "SyncOut2Level")
    sync_out2_mode = ADCpt(SignalWithRBV, "SyncOut2Mode")
    sync_out3_invert = ADCpt(SignalWithRBV, "SyncOut3Invert")
    sync_out3_level = ADCpt(SignalWithRBV, "SyncOut3Level")
    sync_out3_mode = ADCpt(SignalWithRBV, "SyncOut3Mode")
    trigger_delay = ADCpt(SignalWithRBV, "TriggerDelay")
    trigger_event = ADCpt(SignalWithRBV, "TriggerEvent")
    trigger_overlap = ADCpt(SignalWithRBV, "TriggerOverlap")
    trigger_software = ADCpt(EpicsSignal, "TriggerSoftware")


class PvaDetectorCam(CamBase):
    """PvaDriver pulls new image frames via PVAccess."""

    _html_docs = ["pvaDoc.html"]

    input_pv = ADCpt(SignalWithRBV, "PvName", string=True)
    input_connection = ADCpt(EpicsSignalRO, "PvConnection_RBV", string=True)
    overrun_counter = ADCpt(SignalWithRBV, "OverrunCounter")


class PvcamDetectorCam(CamBase):
    _html_docs = ["pvcamDoc.html"]
    bit_depth = ADCpt(EpicsSignalRO, "BitDepth_RBV")
    camera_firmware_vers = ADCpt(EpicsSignalRO, "CameraFirmwareVers_RBV")
    chip_height = ADCpt(EpicsSignalRO, "ChipHeight_RBV")
    chip_name = ADCpt(EpicsSignalRO, "ChipName_RBV")
    chip_width = ADCpt(EpicsSignalRO, "ChipWidth_RBV")
    close_delay = ADCpt(SignalWithRBV, "CloseDelay")
    detector_mode = ADCpt(SignalWithRBV, "DetectorMode")
    detector_selected = ADCpt(SignalWithRBV, "DetectorSelected")
    dev_drv_vers = ADCpt(EpicsSignalRO, "DevDrvVers_RBV")
    frame_transfer_capable = ADCpt(EpicsSignalRO, "FrameTransferCapable_RBV")
    full_well_capacity = ADCpt(EpicsSignalRO, "FullWellCapacity_RBV")
    gain_index = ADCpt(SignalWithRBV, "GainIndex")
    head_ser_num = ADCpt(EpicsSignalRO, "HeadSerNum_RBV")
    initialize = ADCpt(SignalWithRBV, "Initialize")
    max_gain_index = ADCpt(EpicsSignalRO, "MaxGainIndex_RBV")
    max_set_temperature = ADCpt(EpicsSignal, "MaxSetTemperature")
    max_shutter_close_delay = ADCpt(EpicsSignalRO, "MaxShutterCloseDelay_RBV")
    max_shutter_open_delay = ADCpt(EpicsSignalRO, "MaxShutterOpenDelay_RBV")
    measured_temperature = ADCpt(EpicsSignalRO, "MeasuredTemperature_RBV")
    min_set_temperature = ADCpt(EpicsSignal, "MinSetTemperature")
    min_shutter_close_delay = ADCpt(EpicsSignalRO, "MinShutterCloseDelay_RBV")
    min_shutter_open_delay = ADCpt(EpicsSignalRO, "MinShutterOpenDelay_RBV")
    num_parallel_pixels = ADCpt(EpicsSignalRO, "NumParallelPixels_RBV")
    num_ports = ADCpt(EpicsSignalRO, "NumPorts_RBV")
    num_serial_pixels = ADCpt(EpicsSignalRO, "NumSerialPixels_RBV")
    num_speed_table_entries = ADCpt(EpicsSignalRO, "NumSpeedTableEntries_RBV")
    open_delay = ADCpt(SignalWithRBV, "OpenDelay")
    pcifw_vers = ADCpt(EpicsSignalRO, "PCIFWVers_RBV")
    pv_cam_vers = ADCpt(EpicsSignalRO, "PVCamVers_RBV")
    pixel_parallel_dist = ADCpt(EpicsSignalRO, "PixelParallelDist_RBV")
    pixel_parallel_size = ADCpt(EpicsSignalRO, "PixelParallelSize_RBV")
    pixel_serial_dist = ADCpt(EpicsSignalRO, "PixelSerialDist_RBV")
    pixel_serial_size = ADCpt(EpicsSignalRO, "PixelSerialSize_RBV")
    pixel_time = ADCpt(EpicsSignalRO, "PixelTime_RBV")
    post_mask = ADCpt(EpicsSignalRO, "PostMask_RBV")
    post_scan = ADCpt(EpicsSignalRO, "PostScan_RBV")
    pre_mask = ADCpt(EpicsSignalRO, "PreMask_RBV")
    pre_scan = ADCpt(EpicsSignalRO, "PreScan_RBV")
    serial_num = ADCpt(EpicsSignalRO, "SerialNum_RBV")
    set_temperature = ADCpt(SignalWithRBV, "SetTemperature")
    slot1_cam = ADCpt(EpicsSignalRO, "Slot1Cam_RBV")
    slot2_cam = ADCpt(EpicsSignalRO, "Slot2Cam_RBV")
    slot3_cam = ADCpt(EpicsSignalRO, "Slot3Cam_RBV")
    speed_table_index = ADCpt(SignalWithRBV, "SpeedTableIndex")
    trigger_edge = ADCpt(SignalWithRBV, "TriggerEdge")


class RoperDetectorCam(CamBase):
    _html_docs = ["RoperDoc.html"]
    auto_data_type = ADCpt(SignalWithRBV, "AutoDataType")
    comment1 = ADCpt(SignalWithRBV, "Comment1")
    comment2 = ADCpt(SignalWithRBV, "Comment2")
    comment3 = ADCpt(SignalWithRBV, "Comment3")
    comment4 = ADCpt(SignalWithRBV, "Comment4")
    comment5 = ADCpt(SignalWithRBV, "Comment5")
    file_format = ADCpt(SignalWithRBV, "FileFormat")
    num_acquisitions = ADCpt(SignalWithRBV, "NumAcquisitions")
    num_acquisitions_counter = ADCpt(EpicsSignalRO, "NumAcquisitionsCounter_RBV")
    roper_shutter_mode = ADCpt(SignalWithRBV, "RoperShutterMode")


class URLDetectorCam(CamBase):
    _html_docs = ["URLDoc.html"]
    urls = DDC(
        ad_group(
            EpicsSignal,
            (
                ("url_1", "URL1"),
                ("url_2", "URL2"),
                ("url_3", "URL3"),
                ("url_4", "URL4"),
                ("url_5", "URL5"),
                ("url_6", "URL6"),
                ("url_7", "URL7"),
                ("url_8", "URL8"),
                ("url_9", "URL9"),
                ("url_10", "URL10"),
            ),
        ),
        doc="URLs",
    )

    url_select = ADCpt(EpicsSignal, "URLSelect")
    url_seq = ADCpt(EpicsSignal, "URLSeq")
    url = ADCpt(EpicsSignalRO, "URL_RBV")


class UVCDetectorCam(CamBase):
    _html_docs = ["UVCDoc.html"]
    _default_configuration_attrs = CamBase._default_configuration_attrs
    uvc_framerate = ADCpt(SignalWithRBV, "UVCFramerate")
    uvc_compliance_level = ADCpt(SignalWithRBV, "UVCComplianceLevel")
    uvc_reference_count = ADCpt(SignalWithRBV, "UVCReferenceCount")
    uvc_image_format = ADCpt(SignalWithRBV, "UVCImageFormat")
    uvc_camera_format = ADCpt(SignalWithRBV, "UVCCameraFormat")
    uvc_format_description = ADCpt(EpicsSignalRO, "UVCFormatDescription_RBV")
    uvc_apply_format = ADCpt(SignalWithRBV, "UVCApplyFormat")
    uvc_auto_adjust = ADCpt(SignalWithRBV, "UVCAutoAdjust")
    uvc_gamma = ADCpt(SignalWithRBV, "UVCGamma")
    uvc_backlight_compensation = ADCpt(SignalWithRBV, "UVCBacklightCompensation")
    uvc_brightness = ADCpt(SignalWithRBV, "UVCBrightness")
    uvc_contrast = ADCpt(SignalWithRBV, "UVCContrast")
    uvc_power_line = ADCpt(SignalWithRBV, "UVCPowerLine")
    uvc_hue = ADCpt(SignalWithRBV, "UVCHue")
    uvc_saturation = ADCpt(SignalWithRBV, "UVCSaturation")
    uvc_sharpness = ADCpt(SignalWithRBV, "UVCSharpness")
    uvc_pan_left = ADCpt(EpicsSignal, "UVCPanLeft")
    uvc_pan_right = ADCpt(EpicsSignal, "UVCPanRight")
    uvc_pan_speed = ADCpt(SignalWithRBV, "UVCPanSpeed")
    uvc_tilt_up = ADCpt(EpicsSignal, "UVCTiltUp")
    uvc_tilt_down = ADCpt(EpicsSignal, "UVCTiltDown")
    uvc_tilt_speed = ADCpt(SignalWithRBV, "UVCTiltSpeed")
    uvc_pan_tilt_step = ADCpt(SignalWithRBV, "UVCPanTiltStep")
    uvc_zoom_in = ADCpt(EpicsSignal, "UVCZoomIn")
    uvc_zoom_out = ADCpt(EpicsSignal, "UVCZoomOut")


class Xspress3DetectorCam(CamBase):
    _html_docs = ["Xspress3Doc.html"]

    def __init__(self, prefix, *, read_attrs=None, configuration_attrs=None, **kwargs):
        if read_attrs is None:
            read_attrs = []
        if configuration_attrs is None:
            configuration_attrs = ["config_path", "config_save_path"]

        super().__init__(
            prefix,
            read_attrs=read_attrs,
            configuration_attrs=configuration_attrs,
            **kwargs
        )

    config_path = ADCpt(
        SignalWithRBV, "CONFIG_PATH", string=True, doc="configuration file path"
    )
    config_save_path = ADCpt(
        SignalWithRBV,
        "CONFIG_SAVE_PATH",
        string=True,
        doc="path to save configuration file",
    )
    connect = ADCpt(EpicsSignal, "CONNECT", doc="connect to the Xspress3")
    connected = ADCpt(EpicsSignal, "CONNECTED", doc="show the connected status")
    ctrl_dtc = ADCpt(
        SignalWithRBV,
        "CTRL_DTC",
        doc="enable or disable DTC calculations: 0='Disable' 1='Enable'",
    )

    debounce = ADCpt(
        SignalWithRBV, "DEBOUNCE", doc="set trigger debounce time in 80 MHz cycles"
    )
    disconnect = ADCpt(EpicsSignal, "DISCONNECT", doc="disconnect from the Xspress3")
    erase = ADCpt(
        EpicsSignal, "ERASE", kind="omitted", doc="erase MCA data: 0='Done' 1='Erase'"
    )
    frame_count = ADCpt(
        EpicsSignalRO,
        "FRAME_COUNT_RBV",
        doc="read number of frames acquired in an acquisition",
    )
    invert_f0 = ADCpt(
        SignalWithRBV, "INVERT_F0", doc="invert F0 in modes LVDS_BOTH and TTL_BOTH"
    )
    invert_veto = ADCpt(
        SignalWithRBV,
        "INVERT_VETO",
        doc="invert VETO in modes LVDS, LVDS_BOTH, TTL, and TTL_BOTH",
    )
    max_frames = ADCpt(EpicsSignalRO, "MAX_FRAMES_RBV", doc="maximum number of frames")
    max_frames_driver = ADCpt(
        EpicsSignalRO,
        "MAX_FRAMES_DRIVER_RBV",
        doc="maximum number of frames for a single acquisition",
    )
    max_num_channels = ADCpt(
        EpicsSignalRO,
        "MAX_NUM_CHANNELS_RBV",
        doc="maximum number of channels supported",
    )
    max_spectra = ADCpt(
        SignalWithRBV, "MAX_SPECTRA", doc="maximum number of elements in a spectrum"
    )
    xsp_name = ADCpt(EpicsSignal, "NAME", doc="detector name")
    num_cards = ADCpt(
        EpicsSignalRO, "NUM_CARDS_RBV", doc="number of xspress3 cards to set up"
    )
    num_channels = ADCpt(
        SignalWithRBV, "NUM_CHANNELS", doc="number of channels to read out"
    )
    num_frames_config = ADCpt(
        SignalWithRBV,
        "NUM_FRAMES_CONFIG",
        doc="number of frames to configure the system with",
    )
    reset = ADCpt(EpicsSignal, "RESET", doc="reset the device")
    restore_settings = ADCpt(
        EpicsSignal, "RESTORE_SETTINGS", doc="restore settings from a file"
    )
    run_flags = ADCpt(
        SignalWithRBV, "RUN_FLAGS", doc="set the run flags, only at connect time"
    )
    save_settings = ADCpt(
        EpicsSignal, "SAVE_SETTINGS", doc="save current settings to a file"
    )
    trigger_signal = ADCpt(EpicsSignal, "TRIGGER", doc="0='Do Nothing', 1='Trigger'")

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
