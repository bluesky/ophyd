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
import numpy as np

import epics

from .signal import EpicsSignal
from .signal import SignalGroup


logger = logging.getLogger(__name__)


__all__ = ['AreaDetector',
           'ImagePlugin',
           'StatsPlugin',
           'ColorConvPlugin',
           'ProcessPlugin',
           'OverlayPlugin',
           'NexusPlugin',
           'ROIPlugin',
           'FilePlugin',
           'NetCDFPlugin',
           'TIFFPlugin',
           'JPEGPlugin',
           'HDF5Plugin',
           'MagickPlugin',
           'get_areadetector_plugin',
           ]


def ADSignalGroup(*props, **kwargs):
    # TODO use kwargs meaningfully

    def get_signals(self):
        return [prop.fget(self) for prop in props]

    def fget(self):
        return [signal.value for signal in get_signals(self)]

    def fset(self, values):
        for signal, value in zip(get_signals(self), values):
            # print('Setting', signal, '=', value)
            signal.value = value

    doc = kwargs.pop('doc', '')
    return property(fget, fset, doc=doc)


def ADSignal(pv, has_rbv=False, doc='', **kwargs):
    '''
    Don't create an EpicsSignal instance until it's
    accessed (i.e., lazy evaluation)
    '''

    def check_exists(self):
        try:
            return self._ad_signals[pv]
        except KeyError:
            read_ = write = ''.join([self._prefix, pv])
            if has_rbv:
                read_ += '_RBV'
            else:
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


class ADBase(SignalGroup):
    array_counter = ADSignal('ArrayCounter', has_rbv=True)
    array_rate = ADSignal('ArrayRate_RBV', rw=False)
    asyn_io = ADSignal('AsynIO')

    nd_attributes_file = ADSignal('NDAttributesFile')
    pool_alloc_buffers = ADSignal('PoolAllocBuffers')
    pool_free_buffers = ADSignal('PoolFreeBuffers')
    pool_max_buffers = ADSignal('PoolMaxBuffers')
    pool_max_mem = ADSignal('PoolMaxMem')
    pool_used_buffers = ADSignal('PoolUsedBuffers')
    pool_used_mem = ADSignal('PoolUsedMem')
    port_name = ADSignal('PortName_RBV', rw=False)

    def __init__(self, prefix, **kwargs):
        SignalGroup.__init__(self, **kwargs)

        self._prefix = prefix
        self._ad_signals = {}


class AreaDetector(ADBase):
    acquire = ADSignal('Acquire', has_rbv=True)
    acquire_period = ADSignal('AcquirePeriod', has_rbv=True)
    acquire_time = ADSignal('AcquireTime', has_rbv=True)

    array_callbacks = ADSignal('ArrayCallbacks', has_rbv=True)

    _array_size_x = ADSignal('ArraySizeX_RBV', rw=False)
    _array_size_y = ADSignal('ArraySizeY_RBV', rw=False)
    _array_size_z = ADSignal('ArraySizeZ_RBV', rw=False)
    array_size = ADSignalGroup(_array_size_x, _array_size_y, _array_size_z)

    array_size_bytes = ADSignal('ArraySize_RBV', rw=False)
    bin_x = ADSignal('BinX', has_rbv=True)
    bin_y = ADSignal('BinY', has_rbv=True)
    color_mode = ADSignal('ColorMode', has_rbv=True)
    data_type = ADSignal('DataType', has_rbv=True)
    detector_state = ADSignal('DetectorState_RBV', rw=False)
    frame_type = ADSignal('FrameType', has_rbv=True)
    gain = ADSignal('Gain', has_rbv=True)

    gain_blue = ADSignal('GainBlue', has_rbv=True)
    gain_green = ADSignal('GainGreen', has_rbv=True)
    gain_red = ADSignal('GainRed', has_rbv=True)
    gain_rgb = ADSignalGroup(gain_red, gain_green, gain_blue)

    _gain_x = ADSignal('GainX', has_rbv=True)
    _gain_y = ADSignal('GainY', has_rbv=True)
    gain_xy = ADSignalGroup(_gain_x, _gain_y)

    image_mode = ADSignal('ImageMode', has_rbv=True)
    manufacturer = ADSignal('Manufacturer_RBV', rw=False)

    _max_size_x = ADSignal('MaxSizeX_RBV', rw=False)
    _max_size_y = ADSignal('MaxSizeY_RBV', rw=False)
    max_size = ADSignalGroup(_max_size_x, _max_size_y)

    min_x = ADSignal('MinX', has_rbv=True)
    min_y = ADSignal('MinY', has_rbv=True)
    model = ADSignal('Model_RBV', rw=False)
    noise = ADSignal('Noise', has_rbv=True)
    num_exposures = ADSignal('NumExposures', has_rbv=True)
    num_exposures_counter = ADSignal('NumExposuresCounter_RBV', rw=False)
    num_images = ADSignal('NumImages', has_rbv=True)
    num_images_counter = ADSignal('NumImagesCounter_RBV', rw=False)

    _peak_num_x = ADSignal('PeakNumX', has_rbv=True)
    _peak_num_y = ADSignal('PeakNumY', has_rbv=True)
    peak_num = ADSignalGroup(_peak_num_x, _peak_num_y)

    _peak_start_x = ADSignal('PeakStartX', has_rbv=True)
    _peak_start_y = ADSignal('PeakStartY', has_rbv=True)
    peak_start = ADSignalGroup(_peak_start_x, _peak_start_y)

    _peak_step_x = ADSignal('PeakStepX', has_rbv=True)
    _peak_step_y = ADSignal('PeakStepY', has_rbv=True)
    peak_step = ADSignalGroup(_peak_step_x, _peak_step_y)

    peak_variation = ADSignal('PeakVariation', has_rbv=True)

    _peak_width_x = ADSignal('PeakWidthX', has_rbv=True)
    _peak_width_y = ADSignal('PeakWidthY', has_rbv=True)
    peak_width = ADSignalGroup(_peak_width_x, _peak_width_y)

    read_status = ADSignal('ReadStatus')
    reset = ADSignal('Reset', has_rbv=True)

    _reverse_x = ADSignal('ReverseX', has_rbv=True)
    _reverse_y = ADSignal('ReverseY', has_rbv=True)
    reverse = ADSignalGroup(_reverse_x, _reverse_y)

    shutter_close_delay = ADSignal('ShutterCloseDelay', has_rbv=True)
    shutter_close_epics = ADSignal('ShutterCloseEPICS')
    shutter_control = ADSignal('ShutterControl', has_rbv=True)
    shutter_control_epics = ADSignal('ShutterControlEPICS')
    shutter_fanout = ADSignal('ShutterFanout')
    shutter_mode = ADSignal('ShutterMode', has_rbv=True)
    shutter_open_delay = ADSignal('ShutterOpenDelay', has_rbv=True)
    shutter_open_epics = ADSignal('ShutterOpenEPICS')
    shutter_status_epics = ADSignal('ShutterStatusEPICS_RBV', rw=False)
    shutter_status = ADSignal('ShutterStatus_RBV', rw=False)
    sim_mode = ADSignal('SimMode', has_rbv=True)

    _size_x = ADSignal('SizeX', has_rbv=True)
    _size_y = ADSignal('SizeY', has_rbv=True)
    size = ADSignalGroup(_size_x, _size_y)

    status_message = ADSignal('StatusMessage_RBV', rw=False)
    string_from_server = ADSignal('StringFromServer_RBV', rw=False)
    string_to_server = ADSignal('StringToServer_RBV', rw=False)
    temperature = ADSignal('Temperature', has_rbv=True)
    temperature_actual = ADSignal('TemperatureActual')
    time_remaining = ADSignal('TimeRemaining_RBV', rw=False)
    trigger_mode = ADSignal('TriggerMode', has_rbv=True)

    def __init__(self, prefix, cam='cam1:', **kwargs):
        if cam and not prefix.endswith(cam):
            prefix = ''.join([prefix, cam])

        ADBase.__init__(self, prefix=prefix, **kwargs)


class PluginBase(ADBase):
    @property
    def array_pixels(self):
        array_size = self.array_size

        dimensions = self.ndimensions.value
        if dimensions == 0:
            return 0

        pixels = array_size[0]
        for dim in array_size[1:dimensions]:
            pixels *= dim

        return pixels

    _array_size0 = ADSignal('ArraySize0_RBV', rw=False)
    _array_size1 = ADSignal('ArraySize1_RBV', rw=False)
    _array_size2 = ADSignal('ArraySize2_RBV', rw=False)
    array_size = ADSignalGroup(_array_size0, _array_size1, _array_size2)

    bayer_pattern = ADSignal('BayerPattern_RBV', rw=False)
    blocking_callbacks = ADSignal('BlockingCallbacks', has_rbv=True)
    color_mode = ADSignal('ColorMode_RBV', rw=False)
    data_type = ADSignal('DataType_RBV', rw=False)

    dim0_sa = ADSignal('Dim0SA')
    dim1_sa = ADSignal('Dim1SA')
    dim2_sa = ADSignal('Dim2SA')
    dim_sa = ADSignalGroup(dim0_sa, dim1_sa, dim2_sa)

    dimensions = ADSignal('Dimensions_RBV', rw=False)
    dropped_arrays = ADSignal('DroppedArrays', has_rbv=True)
    enable_callbacks = ADSignal('EnableCallbacks', has_rbv=True)
    min_callback_time = ADSignal('MinCallbackTime', has_rbv=True)
    nd_array_address = ADSignal('NDArrayAddress', has_rbv=True)
    nd_array_port = ADSignal('NDArrayPort', has_rbv=True)
    ndimensions = ADSignal('NDimensions_RBV', rw=False)
    plugin_type = ADSignal('PluginType_RBV', rw=False)

    queue_free = ADSignal('QueueFree')
    queue_free_low = ADSignal('QueueFreeLow')
    queue_size = ADSignal('QueueSize')
    queue_use = ADSignal('QueueUse')
    queue_use_high = ADSignal('QueueUseHIGH')
    queue_use_hihi = ADSignal('QueueUseHIHI')
    time_stamp = ADSignal('TimeStamp_RBV', rw=False)
    unique_id = ADSignal('UniqueId_RBV', rw=False)

    def __init__(self, prefix, suffix=None, **kwargs):
        if suffix is None:
            suffix = self._default_suffix

        prefix = ''.join([prefix, suffix])

        ADBase.__init__(self, prefix=prefix, **kwargs)


class ImagePlugin(PluginBase):
    _default_suffix = 'image1:'

    array_data = ADSignal('ArrayData')

    @property
    def image(self):
        array_size = self.array_size
        if array_size == [0, 0, 0]:
            raise RuntimeError('Invalid image; ensure array_callbacks are on')

        if array_size[-1] == 0:
            array_size = array_size[:-1]

        pixel_count = self.array_pixels
        image = self.array_data._get_readback(count=pixel_count)
        return np.array(image).reshape(array_size)


class StatsPlugin(PluginBase):
    _default_suffix = 'Stats1:'

    bgd_width = ADSignal('BgdWidth', has_rbv=True)
    centroid_threshold = ADSignal('CentroidThreshold', has_rbv=True)

    _centroid_x = ADSignal('CentroidX_RBV', rw=False)
    _centroid_y = ADSignal('CentroidY_RBV', rw=False)
    centroid = ADSignalGroup(_centroid_x, _centroid_y)

    compute_centroid = ADSignal('ComputeCentroid', has_rbv=True)
    compute_histogram = ADSignal('ComputeHistogram', has_rbv=True)
    compute_profiles = ADSignal('ComputeProfiles', has_rbv=True)
    compute_statistics = ADSignal('ComputeStatistics', has_rbv=True)

    _cursor_x = ADSignal('CursorX', has_rbv=True)
    _cursor_y = ADSignal('CursorY', has_rbv=True)

    cursor = ADSignalGroup(_cursor_x, _cursor_y)

    hist_entropy = ADSignal('HistEntropy_RBV', rw=False)
    hist_max = ADSignal('HistMax', has_rbv=True)
    hist_min = ADSignal('HistMin', has_rbv=True)
    hist_size = ADSignal('HistSize', has_rbv=True)
    histogram = ADSignal('Histogram_RBV', rw=False)

    _max_size_x = ADSignal('MaxSizeX')
    _max_size_y = ADSignal('MaxSizeY')
    max_size = ADSignalGroup(_max_size_x, _max_size_y)

    max_value = ADSignal('MaxValue_RBV', rw=False)

    _max_x = ADSignal('MaxX_RBV', rw=False)
    _max_y = ADSignal('MaxY_RBV', rw=False)
    max_ = ADSignalGroup(_max_x, _max_y)

    mean_value = ADSignal('MeanValue_RBV', rw=False)
    min_value = ADSignal('MinValue_RBV', rw=False)

    _min_x = ADSignal('MinX_RBV', rw=False)
    _min_y = ADSignal('MinY_RBV', rw=False)
    min_ = ADSignalGroup(_min_x, _min_y)

    net = ADSignal('Net_RBV', rw=False)

    _profile_average_x = ADSignal('ProfileAverageX_RBV', rw=False)
    _profile_average_y = ADSignal('ProfileAverageY_RBV', rw=False)
    profile_average = ADSignalGroup(_profile_average_x, _profile_average_y)

    _profile_centroid_x = ADSignal('ProfileCentroidX_RBV', rw=False)
    _profile_centroid_y = ADSignal('ProfileCentroidY_RBV', rw=False)
    profile_centroid = ADSignalGroup(_profile_centroid_x, _profile_centroid_y)

    _profile_cursor_x = ADSignal('ProfileCursorX_RBV', rw=False)
    _profile_cursor_y = ADSignal('ProfileCursorY_RBV', rw=False)
    profile_cursor = ADSignalGroup(_profile_cursor_x, _profile_cursor_y)

    _profile_size_x = ADSignal('ProfileSizeX_RBV', rw=False)
    _profile_size_y = ADSignal('ProfileSizeY_RBV', rw=False)
    profile_size = ADSignalGroup(_profile_size_x, _profile_size_y)

    _profile_threshold_x = ADSignal('ProfileThresholdX_RBV', rw=False)
    _profile_threshold_y = ADSignal('ProfileThresholdY_RBV', rw=False)
    profile_threshold = ADSignalGroup(_profile_threshold_x, _profile_threshold_y)

    set_xhopr = ADSignal('SetXHOPR')
    set_yhopr = ADSignal('SetYHOPR')
    sigma_xy = ADSignal('SigmaXY_RBV', rw=False)
    sigma_x = ADSignal('SigmaX_RBV', rw=False)
    sigma_y = ADSignal('SigmaY_RBV', rw=False)
    sigma = ADSignal('Sigma_RBV', rw=False)
    ts_acquiring = ADSignal('TSAcquiring')

    _ts_centroid_x = ADSignal('TSCentroidX')
    _ts_centroid_y = ADSignal('TSCentroidY')
    ts_centroid = ADSignalGroup(_ts_centroid_x, _ts_centroid_y)

    ts_control = ADSignal('TSControl')
    ts_current_point = ADSignal('TSCurrentPoint')
    ts_max_value = ADSignal('TSMaxValue')

    _ts_max_x = ADSignal('TSMaxX')
    _ts_max_y = ADSignal('TSMaxY')
    ts_max = ADSignalGroup(_ts_max_x, _ts_max_y)

    ts_mean_value = ADSignal('TSMeanValue')
    ts_min_value = ADSignal('TSMinValue')

    _ts_min_x = ADSignal('TSMinX')
    _ts_min_y = ADSignal('TSMinY')
    ts_min = ADSignalGroup(_ts_min_x, _ts_min_y)

    ts_net = ADSignal('TSNet')
    ts_num_points = ADSignal('TSNumPoints')
    ts_read = ADSignal('TSRead')
    ts_sigma = ADSignal('TSSigma')
    ts_sigma_x = ADSignal('TSSigmaX')
    ts_sigma_xy = ADSignal('TSSigmaXY')
    ts_sigma_y = ADSignal('TSSigmaY')
    ts_total = ADSignal('TSTotal')
    total = ADSignal('Total_RBV', rw=False)


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

    _fc1 = ADSignal('FC1', has_rbv=True)
    _fc2 = ADSignal('FC2', has_rbv=True)
    _fc3 = ADSignal('FC3', has_rbv=True)
    _fc4 = ADSignal('FC4', has_rbv=True)
    fc = ADSignalGroup(_fc1, _fc2, _fc3, _fc4,
                       doc='Filter coefficients')

    foffset = ADSignal('FOffset', has_rbv=True)
    fscale = ADSignal('FScale', has_rbv=True)
    filter_callbacks = ADSignal('FilterCallbacks', has_rbv=True)
    filter_type = ADSignal('FilterType')
    filter_type_seq = ADSignal('FilterTypeSeq')
    high_clip = ADSignal('HighClip', has_rbv=True)
    low_clip = ADSignal('LowClip', has_rbv=True)
    num_filter = ADSignal('NumFilter', has_rbv=True)
    num_filter_recip = ADSignal('NumFilterRecip')
    num_filtered = ADSignal('NumFiltered_RBV', rw=False)

    _oc1 = ADSignal('OC1', has_rbv=True)
    _oc2 = ADSignal('OC2', has_rbv=True)
    _oc3 = ADSignal('OC3', has_rbv=True)
    _oc4 = ADSignal('OC4', has_rbv=True)
    oc = ADSignalGroup(_oc1, _oc2, _oc3, _oc4,
                       doc='Output coefficients')

    o_offset = ADSignal('OOffset', has_rbv=True)
    o_scale = ADSignal('OScale', has_rbv=True)
    offset = ADSignal('Offset', has_rbv=True)

    _rc1 = ADSignal('RC1', has_rbv=True)
    _rc2 = ADSignal('RC2', has_rbv=True)
    rc = ADSignalGroup(_rc1, _rc2,
                       doc='Filter coefficients')

    roffset = ADSignal('ROffset', has_rbv=True)
    recursive_ave_diff_seq = ADSignal('RecursiveAveDiffSeq')
    recursive_ave_seq = ADSignal('RecursiveAveSeq')
    reset_filter = ADSignal('ResetFilter', has_rbv=True)
    save_background = ADSignal('SaveBackground', has_rbv=True)
    save_flat_field = ADSignal('SaveFlatField', has_rbv=True)
    scale = ADSignal('Scale', has_rbv=True)
    scale_flat_field = ADSignal('ScaleFlatField', has_rbv=True)
    sum_seq = ADSignal('SumSeq')
    valid_background = ADSignal('ValidBackground_RBV', rw=False)
    valid_flat_field = ADSignal('ValidFlatField_RBV', rw=False)


class OverlayPlugin(PluginBase):
    _default_suffix = 'Over1:'

    # TODO a bit different from other plugins
    _max_size_x = ADSignal('MaxSizeX_RBV', rw=False)
    _max_size_y = ADSignal('MaxSizeY_RBV', rw=False)
    max_size = ADSignalGroup(_max_size_x, _max_size_y)


class ROIPlugin(PluginBase):
    _default_suffix = 'ROI1:'

    _auto_size_x = ADSignal('AutoSizeX', has_rbv=True)
    _auto_size_y = ADSignal('AutoSizeY', has_rbv=True)
    _auto_size_z = ADSignal('AutoSizeZ', has_rbv=True)
    auto_size = ADSignalGroup(_auto_size_x, _auto_size_y, _auto_size_z)

    _bin_x = ADSignal('BinX', has_rbv=True)
    _bin_y = ADSignal('BinY', has_rbv=True)
    _bin_z = ADSignal('BinZ', has_rbv=True)
    bin_ = ADSignalGroup(_bin_x, _bin_y, _bin_z)

    data_type_out = ADSignal('DataTypeOut', has_rbv=True)
    enable_scale = ADSignal('EnableScale', has_rbv=True)

    _enable_x = ADSignal('EnableX', has_rbv=True)
    _enable_y = ADSignal('EnableY', has_rbv=True)
    _enable_z = ADSignal('EnableZ', has_rbv=True)
    enable = ADSignalGroup(_enable_x, _enable_y, _enable_z)

    _max_x = ADSignal('MaxX')
    _max_y = ADSignal('MaxY')
    max_ = ADSignalGroup(_max_x, _max_y)

    _min_x = ADSignal('MinX', has_rbv=True)
    _min_y = ADSignal('MinY', has_rbv=True)
    _min_z = ADSignal('MinZ', has_rbv=True)
    min_ = ADSignalGroup(_min_x, _min_y, _min_z)

    name_ = ADSignal('Name', has_rbv=True,
                     doc='ROI name')

    _reverse_x = ADSignal('ReverseX', has_rbv=True)
    _reverse_y = ADSignal('ReverseY', has_rbv=True)
    _reverse_z = ADSignal('ReverseZ', has_rbv=True)
    reverse = ADSignalGroup(_reverse_x, _reverse_y, _reverse_z)

    scale = ADSignal('Scale', has_rbv=True)
    set_xhopr = ADSignal('SetXHOPR')
    set_yhopr = ADSignal('SetYHOPR')

    _size_x = ADSignal('SizeX', has_rbv=True)
    _size_y = ADSignal('SizeY', has_rbv=True)
    _size_z = ADSignal('SizeZ', has_rbv=True)
    size = ADSignalGroup(_size_x, _size_y, _size_z)

    _size_x_link = ADSignal('SizeXLink')
    _size_y_link = ADSignal('SizeYLink')

    size_link = ADSignalGroup(_size_x_link, _size_y_link)


class TransformPlugin(PluginBase):
    _default_suffix = 'Trans1:'

    name_ = ADSignal('Name')
    origin_location = ADSignal('OriginLocation', has_rbv=True)
    _t1_max_size0 = ADSignal('T1MaxSize0')
    _t1_max_size1 = ADSignal('T1MaxSize1')
    _t1_max_size2 = ADSignal('T1MaxSize2')
    t1_max_size = ADSignalGroup(_t1_max_size0, _t1_max_size1, _t1_max_size2)

    _t2_max_size0 = ADSignal('T2MaxSize0')
    _t2_max_size1 = ADSignal('T2MaxSize1')
    _t2_max_size2 = ADSignal('T2MaxSize2')
    t2_max_size = ADSignalGroup(_t2_max_size0, _t2_max_size1, _t2_max_size2)

    _t3_max_size0 = ADSignal('T3MaxSize0')
    _t3_max_size1 = ADSignal('T3MaxSize1')
    _t3_max_size2 = ADSignal('T3MaxSize2')
    t3_max_size = ADSignalGroup(_t3_max_size0, _t3_max_size1, _t3_max_size2)

    _t4_max_size0 = ADSignal('T4MaxSize0')
    _t4_max_size1 = ADSignal('T4MaxSize1')
    _t4_max_size2 = ADSignal('T4MaxSize2')
    t4_max_size = ADSignalGroup(_t4_max_size0, _t4_max_size1, _t4_max_size2)

    _type1 = ADSignal('Type1')
    _type2 = ADSignal('Type2')
    _type3 = ADSignal('Type3')
    _type4 = ADSignal('Type4')
    types = ADSignalGroup(_type1, _type2, _type3, _type4)


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
    file_path_exists = ADSignal('FilePathExists_RBV', rw=False)
    file_template = ADSignal('FileTemplate', has_rbv=True)
    file_write_mode = ADSignal('FileWriteMode', has_rbv=True)
    full_file_name = ADSignal('FullFileName_RBV', rw=False)
    num_capture = ADSignal('NumCapture', has_rbv=True)
    num_captured = ADSignal('NumCaptured_RBV', rw=False)
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

    extra_dim_name_n = ADSignal('ExtraDimNameN_RBV', rw=False)
    extra_dim_name_x = ADSignal('ExtraDimNameX_RBV', rw=False)
    extra_dim_name_y = ADSignal('ExtraDimNameY_RBV', rw=False)

    extra_dim_name = ADSignalGroup(extra_dim_name_x,
                                   extra_dim_name_y,
                                   extra_dim_name_n,
                                   )
    extra_dim_size_n = ADSignal('ExtraDimSizeN', has_rbv=True)
    extra_dim_size_x = ADSignal('ExtraDimSizeX', has_rbv=True)
    extra_dim_size_y = ADSignal('ExtraDimSizeY', has_rbv=True)
    extra_dim_size = ADSignalGroup(extra_dim_size_x,
                                   extra_dim_size_y,
                                   extra_dim_size_n,
                                   )

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

    class_ = type_map[type_]
    return class_(prefix, suffix=suffix, **kwargs)
