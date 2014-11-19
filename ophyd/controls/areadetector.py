# vi: ts=4 sw=4
'''
:mod:`ophyd.control.areadetector` - areaDetector
================================================

.. module:: ophyd.control.areadetector
 :synopsis:  `areaDetector`_ camera and plugin abstractions

.. _areaDetector: http://cars.uchicago.edu/software/epics/areaDetector.html

'''

from __future__ import print_function
import logging

import epics

from .signal import EpicsSignal
from .signal import SignalGroup


logger = logging.getLogger(__name__)


__all__ = ['AreaDetector',
           'PluginBase',
           'ImagePlugin',
           'StatsPlugin',
           'ColorConvPlugin',
           'ProcessPlugin',
           'OverlayPlugin',
           'ROIPlugin',
           'FilePlugin',
           'NetCDFPlugin',
           'TIFFPlugin',
           'JPEGPlugin',
           'HDF5Plugin',
           'MagickPlugin',
           'get_areadetector_plugin',
           ]


def ADSignal(pv, has_rbv=False, doc='', **kwargs):
    '''
    Don't create an EpicsSignal instance until it's
    accessed (i.e., lazy evaluation)
    '''

    def check_exists(self):
        try:
            return self._ad_signals[pv]
        except KeyError:
            if has_rbv:
                read_ = ''.join([self._prefix, pv, '_RBV'])
                write = ''.join([self._prefix, pv])
            else:
                read_ = pv
                write = None

            self._ad_signals[pv] = EpicsSignal(read_, write_pv=write,
                                               **kwargs)
            return self._ad_signals[pv]

    def fget(self):
        signal = check_exists(self)
        return signal

    def fset(self, value):
        signal = check_exists(self)
        signal.value = value

    return property(fget, fset, doc=doc)


class AreaDetector(SignalGroup):
    acquire = ADSignal('Acquire', has_rbv=True)
    acquire_period = ADSignal('AcquirePeriod', has_rbv=True)
    acquire_time = ADSignal('AcquireTime', has_rbv=True)
    array_callbacks = ADSignal('ArrayCallbacks', has_rbv=True)
    array_counter = ADSignal('ArrayCounter', has_rbv=True)
    asyn_io = ADSignal('AsynIO')
    bin_x = ADSignal('BinX', has_rbv=True)
    bin_y = ADSignal('BinY', has_rbv=True)
    color_mode = ADSignal('ColorMode', has_rbv=True)
    data_type = ADSignal('DataType', has_rbv=True)
    frame_type = ADSignal('FrameType', has_rbv=True)
    gain = ADSignal('Gain', has_rbv=True)
    gain_blue = ADSignal('GainBlue', has_rbv=True)
    gain_green = ADSignal('GainGreen', has_rbv=True)
    gain_red = ADSignal('GainRed', has_rbv=True)
    gain_x = ADSignal('GainX', has_rbv=True)
    gain_y = ADSignal('GainY', has_rbv=True)
    image_mode = ADSignal('ImageMode', has_rbv=True)
    min_x = ADSignal('MinX', has_rbv=True)
    min_y = ADSignal('MinY', has_rbv=True)
    nd_attributes_file = ADSignal('NDAttributesFile')
    noise = ADSignal('Noise', has_rbv=True)
    num_exposures = ADSignal('NumExposures', has_rbv=True)
    num_images = ADSignal('NumImages', has_rbv=True)
    peak_num_x = ADSignal('PeakNumX', has_rbv=True)
    peak_num_y = ADSignal('PeakNumY', has_rbv=True)
    peak_start_x = ADSignal('PeakStartX', has_rbv=True)
    peak_start_y = ADSignal('PeakStartY', has_rbv=True)
    peak_step_x = ADSignal('PeakStepX', has_rbv=True)
    peak_step_y = ADSignal('PeakStepY', has_rbv=True)
    peak_variation = ADSignal('PeakVariation', has_rbv=True)
    peak_width_x = ADSignal('PeakWidthX', has_rbv=True)
    peak_width_y = ADSignal('PeakWidthY', has_rbv=True)
    pool_alloc_buffers = ADSignal('PoolAllocBuffers')
    pool_free_buffers = ADSignal('PoolFreeBuffers')
    pool_max_buffers = ADSignal('PoolMaxBuffers')
    pool_max_mem = ADSignal('PoolMaxMem')
    pool_used_buffers = ADSignal('PoolUsedBuffers')
    pool_used_mem = ADSignal('PoolUsedMem')
    read_status = ADSignal('ReadStatus')
    reset = ADSignal('Reset', has_rbv=True)
    reverse_x = ADSignal('ReverseX', has_rbv=True)
    reverse_y = ADSignal('ReverseY', has_rbv=True)
    shutter_close_delay = ADSignal('ShutterCloseDelay', has_rbv=True)
    shutter_close_epics = ADSignal('ShutterCloseEPICS')
    shutter_control = ADSignal('ShutterControl', has_rbv=True)
    shutter_control_epics = ADSignal('ShutterControlEPICS')
    shutter_fanout = ADSignal('ShutterFanout')
    shutter_mode = ADSignal('ShutterMode', has_rbv=True)
    shutter_open_delay = ADSignal('ShutterOpenDelay', has_rbv=True)
    shutter_open_epics = ADSignal('ShutterOpenEPICS')
    sim_mode = ADSignal('SimMode', has_rbv=True)
    size_x = ADSignal('SizeX', has_rbv=True)
    size_y = ADSignal('SizeY', has_rbv=True)
    temperature = ADSignal('Temperature', has_rbv=True)
    temperature_actual = ADSignal('TemperatureActual')
    trigger_mode = ADSignal('TriggerMode', has_rbv=True)

    def __init__(self, prefix, cam='cam1:', **kwargs):
        SignalGroup.__init__(self, **kwargs)

        if not prefix.endswith(cam):
            prefix = ''.join([prefix, cam])

        self._prefix = prefix
        self._ad_signals = {}


class PluginBase(SignalGroup):
    _default_suffix = ''

    array_counter = ADSignal('ArrayCounter', has_rbv=True)
    asyn_io = ADSignal('AsynIO')
    blocking_callbacks = ADSignal('BlockingCallbacks', has_rbv=True)
    dim0_sa = ADSignal('Dim0SA')
    dim1_sa = ADSignal('Dim1SA')
    dim2_sa = ADSignal('Dim2SA')
    dropped_arrays = ADSignal('DroppedArrays', has_rbv=True)
    enable_callbacks = ADSignal('EnableCallbacks', has_rbv=True)
    min_callback_time = ADSignal('MinCallbackTime', has_rbv=True)
    nd_array_address = ADSignal('NDArrayAddress', has_rbv=True)
    nd_array_port = ADSignal('NDArrayPort', has_rbv=True)
    nd_attributes_file = ADSignal('NDAttributesFile')
    pool_alloc_buffers = ADSignal('PoolAllocBuffers')
    pool_free_buffers = ADSignal('PoolFreeBuffers')
    pool_max_buffers = ADSignal('PoolMaxBuffers')
    pool_max_mem = ADSignal('PoolMaxMem')
    pool_used_buffers = ADSignal('PoolUsedBuffers')
    pool_used_mem = ADSignal('PoolUsedMem')
    queue_free = ADSignal('QueueFree')
    queue_free_low = ADSignal('QueueFreeLow')
    queue_size = ADSignal('QueueSize')
    queue_use = ADSignal('QueueUse')
    queue_use_high = ADSignal('QueueUseHIGH')
    queue_use_hihi = ADSignal('QueueUseHIHI')

    def __init__(self, prefix, suffix=''):
        if not suffix:
            suffix = self._default_suffix
        self._prefix = str(prefix)
        self._ad_signals = {}


class ImagePlugin(PluginBase):
    _default_suffix = 'image1:'

    array_data = ADSignal('ArrayData')


class StatsPlugin(PluginBase):
    _default_suffix = 'Stats1:'

    bgd_width = ADSignal('BgdWidth', has_rbv=True)
    centroid_threshold = ADSignal('CentroidThreshold', has_rbv=True)
    compute_centroid = ADSignal('ComputeCentroid', has_rbv=True)
    compute_histogram = ADSignal('ComputeHistogram', has_rbv=True)
    compute_profiles = ADSignal('ComputeProfiles', has_rbv=True)
    compute_statistics = ADSignal('ComputeStatistics', has_rbv=True)
    cursor_x = ADSignal('CursorX', has_rbv=True)
    cursor_y = ADSignal('CursorY', has_rbv=True)
    hist_max = ADSignal('HistMax', has_rbv=True)
    hist_min = ADSignal('HistMin', has_rbv=True)
    hist_size = ADSignal('HistSize', has_rbv=True)
    max_size_x = ADSignal('MaxSizeX')
    max_size_y = ADSignal('MaxSizeY')
    set_xhopr = ADSignal('SetXHOPR')
    set_yhopr = ADSignal('SetYHOPR')
    ts_acquiring = ADSignal('TSAcquiring')
    ts_centroid_x = ADSignal('TSCentroidX')
    ts_centroid_y = ADSignal('TSCentroidY')
    ts_control = ADSignal('TSControl')
    ts_current_point = ADSignal('TSCurrentPoint')
    ts_max_value = ADSignal('TSMaxValue')
    ts_max_x = ADSignal('TSMaxX')
    ts_max_y = ADSignal('TSMaxY')
    ts_mean_value = ADSignal('TSMeanValue')
    ts_min_value = ADSignal('TSMinValue')
    ts_min_x = ADSignal('TSMinX')
    ts_min_y = ADSignal('TSMinY')
    ts_net = ADSignal('TSNet')
    ts_num_points = ADSignal('TSNumPoints')
    ts_read = ADSignal('TSRead')
    ts_sigma = ADSignal('TSSigma')
    ts_sigma_x = ADSignal('TSSigmaX')
    ts_sigma_xy = ADSignal('TSSigmaXY')
    ts_sigma_y = ADSignal('TSSigmaY')
    ts_total = ADSignal('TSTotal')


class ColorConvPlugin(PluginBase):
    _default_suffix = 'CC1:'

    color_mode_out = ADSignal('ColorModeOut', has_rbv=True)
    false_color = ADSignal('FalseColor', has_rbv=True)


class ProcessPlugin(PluginBase):
    _default_suffix = 'Proc1:'

    auto_offset_scale = ADSignal('AutoOffsetScale')
    auto_reset_filter = ADSignal('AutoResetFilter', has_rbv=True)
    average_seq = ADSignal('AverageSeq')
    copy_to_filter_seq = ADSignal('CopyToFilterSeq')
    data_type_out = ADSignal('DataTypeOut', has_rbv=True)
    difference_seq = ADSignal('DifferenceSeq')
    enable_background = ADSignal('EnableBackground', has_rbv=True)
    enable_filter = ADSignal('EnableFilter', has_rbv=True)
    enable_flat_field = ADSignal('EnableFlatField', has_rbv=True)
    enable_high_clip = ADSignal('EnableHighClip', has_rbv=True)
    enable_low_clip = ADSignal('EnableLowClip', has_rbv=True)
    enable_offset_scale = ADSignal('EnableOffsetScale', has_rbv=True)
    fc1 = ADSignal('FC1', has_rbv=True)
    fc2 = ADSignal('FC2', has_rbv=True)
    fc3 = ADSignal('FC3', has_rbv=True)
    fc4 = ADSignal('FC4', has_rbv=True)
    foffset = ADSignal('FOffset', has_rbv=True)
    fscale = ADSignal('FScale', has_rbv=True)
    filter_callbacks = ADSignal('FilterCallbacks', has_rbv=True)
    filter_type = ADSignal('FilterType')
    filter_type_seq = ADSignal('FilterTypeSeq')
    high_clip = ADSignal('HighClip', has_rbv=True)
    low_clip = ADSignal('LowClip', has_rbv=True)
    num_filter = ADSignal('NumFilter', has_rbv=True)
    num_filter_recip = ADSignal('NumFilterRecip')
    oc1 = ADSignal('OC1', has_rbv=True)
    oc2 = ADSignal('OC2', has_rbv=True)
    oc3 = ADSignal('OC3', has_rbv=True)
    oc4 = ADSignal('OC4', has_rbv=True)
    ooffset = ADSignal('OOffset', has_rbv=True)
    oscale = ADSignal('OScale', has_rbv=True)
    offset = ADSignal('Offset', has_rbv=True)
    rc1 = ADSignal('RC1', has_rbv=True)
    rc2 = ADSignal('RC2', has_rbv=True)
    roffset = ADSignal('ROffset', has_rbv=True)
    recursive_ave_diff_seq = ADSignal('RecursiveAveDiffSeq')
    recursive_ave_seq = ADSignal('RecursiveAveSeq')
    reset_filter = ADSignal('ResetFilter', has_rbv=True)
    save_background = ADSignal('SaveBackground', has_rbv=True)
    save_flat_field = ADSignal('SaveFlatField', has_rbv=True)
    scale = ADSignal('Scale', has_rbv=True)
    scale_flat_field = ADSignal('ScaleFlatField', has_rbv=True)
    sum_seq = ADSignal('SumSeq')


class OverlayPlugin(PluginBase):
    _default_suffix = 'Over1:'

    # TODO a bit different from other plugins


class ROIPlugin(PluginBase):
    _default_suffix = 'ROI1:'

    auto_size_x = ADSignal('AutoSizeX', has_rbv=True)
    auto_size_y = ADSignal('AutoSizeY', has_rbv=True)
    auto_size_z = ADSignal('AutoSizeZ', has_rbv=True)
    bin_x = ADSignal('BinX', has_rbv=True)
    bin_y = ADSignal('BinY', has_rbv=True)
    bin_z = ADSignal('BinZ', has_rbv=True)
    data_type_out = ADSignal('DataTypeOut', has_rbv=True)
    enable_scale = ADSignal('EnableScale', has_rbv=True)
    enable_x = ADSignal('EnableX', has_rbv=True)
    enable_y = ADSignal('EnableY', has_rbv=True)
    enable_z = ADSignal('EnableZ', has_rbv=True)
    max_x = ADSignal('MaxX')
    max_y = ADSignal('MaxY')
    min_x = ADSignal('MinX', has_rbv=True)
    min_y = ADSignal('MinY', has_rbv=True)
    min_z = ADSignal('MinZ', has_rbv=True)
    name = ADSignal('Name', has_rbv=True)
    reverse_x = ADSignal('ReverseX', has_rbv=True)
    reverse_y = ADSignal('ReverseY', has_rbv=True)
    reverse_z = ADSignal('ReverseZ', has_rbv=True)
    scale = ADSignal('Scale', has_rbv=True)
    set_xhopr = ADSignal('SetXHOPR')
    set_yhopr = ADSignal('SetYHOPR')
    size_x = ADSignal('SizeX', has_rbv=True)
    size_xl_ink = ADSignal('SizeXLink')
    size_y = ADSignal('SizeY', has_rbv=True)
    size_yl_ink = ADSignal('SizeYLink')
    size_z = ADSignal('SizeZ', has_rbv=True)


class FilePlugin(PluginBase):
    _default_suffix = ''

    auto_increment = ADSignal('AutoIncrement', has_rbv=True)
    auto_save = ADSignal('AutoSave', has_rbv=True)
    capture = ADSignal('Capture', has_rbv=True)
    delete_driver_file = ADSignal('DeleteDriverFile', has_rbv=True)
    file_format = ADSignal('FileFormat', has_rbv=True)
    file_name = ADSignal('FileName', has_rbv=True)
    file_number = ADSignal('FileNumber', has_rbv=True)
    file_number_sync = ADSignal('FileNumber_Sync')
    file_number_write = ADSignal('FileNumber_write')
    file_path = ADSignal('FilePath', has_rbv=True)
    file_template = ADSignal('FileTemplate', has_rbv=True)
    file_write_mode = ADSignal('FileWriteMode', has_rbv=True)
    num_capture = ADSignal('NumCapture', has_rbv=True)
    read_file = ADSignal('ReadFile', has_rbv=True)
    write_file = ADSignal('WriteFile', has_rbv=True)
    write_message = ADSignal('WriteMessage')
    write_status = ADSignal('WriteStatus')


class NetCDFPlugin(FilePlugin):
    _default_suffix = 'netCDF1:'


class TIFFPlugin(FilePlugin):
    _default_suffix = 'TIFF1:'


class JPEGPlugin(FilePlugin):
    _default_suffix = 'JPEG1:'

    jpeg_quality = ADSignal('JPEGQuality', has_rbv=True)


class NexusPlugin(FilePlugin):
    _default_suffix = 'Nexus1:'

    file_template_valid = ADSignal('FileTemplateValid')
    template_file_name = ADSignal('TemplateFileName', has_rbv=True)
    template_file_path = ADSignal('TemplateFilePath', has_rbv=True)


class HDF5Plugin(FilePlugin):
    _default_suffix = 'HDF1:'

    boundary_align = ADSignal('BoundaryAlign', has_rbv=True)
    boundary_threshold = ADSignal('BoundaryThreshold', has_rbv=True)
    compression = ADSignal('Compression', has_rbv=True)
    data_bits_offset = ADSignal('DataBitsOffset', has_rbv=True)
    extra_dim_size_n = ADSignal('ExtraDimSizeN', has_rbv=True)
    extra_dim_size_x = ADSignal('ExtraDimSizeX', has_rbv=True)
    extra_dim_size_y = ADSignal('ExtraDimSizeY', has_rbv=True)
    io_speed = ADSignal('IOSpeed')
    num_col_chunks = ADSignal('NumColChunks', has_rbv=True)
    num_data_bits = ADSignal('NumDataBits', has_rbv=True)
    num_extra_dims = ADSignal('NumExtraDims', has_rbv=True)
    num_frames_chunks = ADSignal('NumFramesChunks', has_rbv=True)
    num_frames_flush = ADSignal('NumFramesFlush', has_rbv=True)
    num_row_chunks = ADSignal('NumRowChunks', has_rbv=True)
    run_time = ADSignal('RunTime')
    szip_num_pixels = ADSignal('SZipNumPixels', has_rbv=True)
    store_attr = ADSignal('StoreAttr', has_rbv=True)
    store_perform = ADSignal('StorePerform', has_rbv=True)
    zlevel = ADSignal('ZLevel', has_rbv=True)


class MagickPlugin(FilePlugin):
    _default_suffix = 'Magick1:'

    bit_depth = ADSignal('BitDepth', has_rbv=True)
    compress_type = ADSignal('CompressType', has_rbv=True)
    quality = ADSignal('Quality', has_rbv=True)


type_map = {'NDPluginROI': ROIPlugin,
            'NDPluginStats': StatsPlugin,
            'NDPluginColorConvert': ColorConvPlugin,
            'NDPluginStdArrays': ImagePlugin,
            'NDFileNetCDF': NetCDFPlugin,
            'NDFileTIFF': TIFFPlugin,
            'NDFileJPEG': JPEGPlugin,
            'NDPluginFile': NexusPlugin,
            'NDFileHDF5': HDF5Plugin,
            'NDFileMagick': MagickPlugin,
            'NDPluginProcess': ProcessPlugin,
            }


def get_areadetector_plugin(prefix, suffix='', **kwargs):
    type_rbv = ''.join([prefix, suffix, 'PluginType_RBV'])
    type_ = epics.caget(type_rbv)

    # HDF5 includes version number, remove it
    type_ = type_.split(' ')[0]
    print(type_rbv, type_)

    class_ = type_map[type_]
    return class_(''.join([prefix, suffix]), **kwargs)
