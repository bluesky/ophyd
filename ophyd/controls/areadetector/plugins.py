# vi: ts=4 sw=4
'''
:mod:`ophyd.control.areadetector.plugins` - areaDetector plugins
======================================================

.. module:: ophyd.control.areadetector.plugins
 :synopsis:  `areaDetector`_ plugin abstractions

.. _areaDetector: http://cars.uchicago.edu/software/epics/areaDetector.html
'''

from __future__ import print_function
import re
import logging
import numpy as np

import epics

from .base import (ADBase, update_docstrings, ADSignal, ADSignalGroup,
                   NDArrayDriver)
from ...utils import enum


logger = logging.getLogger(__name__)
__all__ = ['ColorConvPlugin',
           'FilePlugin',
           'HDF5Plugin',
           'ImagePlugin',
           'JPEGPlugin',
           'MagickPlugin',
           'NetCDFPlugin',
           'NexusPlugin',
           'OverlayPlugin',
           'ProcessPlugin',
           'ROIPlugin',
           'StatsPlugin',
           'TIFFPlugin',
           'TransformPlugin',

           'get_areadetector_plugin',
           'plugin_from_pvname',
           ]


class PluginBase(NDArrayDriver):
    '''AreaDetector plugin base class'''
    _html_docs = ['pluginDoc.html']

    @property
    def array_pixels(self):
        array_size = self.array_size.value

        dimensions = self.ndimensions.value
        if dimensions == 0:
            return 0

        pixels = array_size[0]
        for dim in array_size[1:dimensions]:
            pixels *= dim

        return pixels

    width = ADSignal('ArraySize0_RBV', rw=False)
    height = ADSignal('ArraySize1_RBV', rw=False)
    depth = ADSignal('ArraySize2_RBV', rw=False)
    array_size = ADSignalGroup(height, width, depth)

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
    enable = ADSignal('EnableCallbacks', has_rbv=True)
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

    def _get_detector(self, detector=None):
        if detector is not None:
            return detector

        if self._detector is not None:
            return self._detector

        raise ValueError('Must specify detector')

    def __init__(self, prefix, suffix=None, detector=None, **kwargs):
        if suffix is None:
            suffix = self._default_suffix

        prefix = ''.join([prefix, suffix])

        ADBase.__init__(self, prefix, **kwargs)

        self._detector = detector

    @property
    def detector(self):
        '''The default detector associated with the plugin'''
        return self._detector


class ImagePlugin(PluginBase):
    _default_suffix = 'image1:'
    _suffix_re = 'image\d:'
    _html_docs = ['NDPluginStdArrays.html']

    array_data = ADSignal('ArrayData')

    @property
    def image(self):
        array_size = self.array_size.value
        if array_size == [0, 0, 0]:
            raise RuntimeError('Invalid image; ensure array_callbacks are on')

        if array_size[-1] == 0:
            array_size = array_size[:-1]

        pixel_count = self.array_pixels
        image = self.array_data.get(count=pixel_count)
        return np.array(image).reshape(array_size)


class StatsPlugin(PluginBase):
    _default_suffix = 'Stats1:'
    _suffix_re = 'Stats\d:'
    _html_docs = ['NDPluginStats.html']

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
    _suffix_re = 'CC\d:'
    _html_docs = ['NDPluginColorConvert.html']

    color_mode_out = ADSignal('ColorModeOut', has_rbv=True)
    false_color = ADSignal('FalseColor', has_rbv=True)


class ProcessPlugin(PluginBase):
    _default_suffix = 'Proc1:'
    _suffix_re = 'Proc\d:'
    _html_docs = ['NDPluginProcess.html']

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


class Overlay(ADBase):
    _html_docs = ['NDPluginOverlay.html']

    blue = ADSignal('Blue', has_rbv=True)
    draw_mode = ADSignal('DrawMode', has_rbv=True)
    green = ADSignal('Green', has_rbv=True)
    max_size_x = ADSignal('MaxSizeX')
    max_size_y = ADSignal('MaxSizeY')
    overlay_portname = ADSignal('Name', has_rbv=True)

    position_x = ADSignal('PositionX', has_rbv=True)
    position_y = ADSignal('PositionY', has_rbv=True)

    position_xlink = ADSignal('PositionXLink')
    position_ylink = ADSignal('PositionYLink')

    red = ADSignal('Red', has_rbv=True)
    set_xhopr = ADSignal('SetXHOPR')
    set_yhopr = ADSignal('SetYHOPR')
    shape = ADSignal('Shape', has_rbv=True)

    size_x = ADSignal('SizeX', has_rbv=True)
    size_y = ADSignal('SizeY', has_rbv=True)

    size_xlink = ADSignal('SizeXLink')
    size_ylink = ADSignal('SizeYLink')
    use = ADSignal('Use', has_rbv=True)


class OverlayPlugin(PluginBase):
    '''Plugin which adds graphics overlays to an NDArray image

    Keyword arguments are passed to the base class, PluginBase

    Parameters
    ----------
    prefix : str
        The areaDetector plugin prefix
    count : int, optional
        number of overlays (commonPlugin default is 8)
    first_overlay : int, optional
        number of first overlay [default: 1]

    Attributes
    ----------
    overlays : list of Overlay
    '''
    _default_suffix = 'Over1:'
    _suffix_re = 'Over\d:'
    _html_docs = ['NDPluginOverlay.html']

    _max_size_x = ADSignal('MaxSizeX_RBV', rw=False)
    _max_size_y = ADSignal('MaxSizeY_RBV', rw=False)
    max_size = ADSignalGroup(_max_size_x, _max_size_y,
                             doc='Maximum size')

    def __init__(self, prefix, count=8, first_overlay=1,
                 **kwargs):
        PluginBase.__init__(self, prefix, **kwargs)

        self.overlays = []

        if count is not None:
            n_overlays = range(first_overlay, first_overlay + count)
            self.overlays = [Overlay('%s%d:' % (self._prefix, n))
                             for n in n_overlays]


class ROIPlugin(PluginBase):
    _default_suffix = 'ROI1:'
    _suffix_re = 'ROI\d:'
    _html_docs = ['NDPluginROI.html']

    _array_size_x = ADSignal('ArraySizeX_RBV', rw=False)
    _array_size_y = ADSignal('ArraySizeY_RBV', rw=False)
    _array_size_z = ADSignal('ArraySizeZ_RBV', rw=False)
    array_size = ADSignalGroup(_array_size_x, _array_size_y, _array_size_z,
                               doc='Size of the ROI data in the X, Y, Z dimensions')

    _auto_size_x = ADSignal('AutoSizeX', has_rbv=True)
    _auto_size_y = ADSignal('AutoSizeY', has_rbv=True)
    _auto_size_z = ADSignal('AutoSizeZ', has_rbv=True)
    auto_size = ADSignalGroup(_auto_size_x, _auto_size_y, _auto_size_z,
                              doc='Automatically set SizeXYZ to the input array size minus MinXYZ')

    _bin_x = ADSignal('BinX', has_rbv=True)
    _bin_y = ADSignal('BinY', has_rbv=True)
    _bin_z = ADSignal('BinZ', has_rbv=True)
    bin_ = ADSignalGroup(_bin_x, _bin_y, _bin_z,
                         doc='Binning in the X, Y, and Z dimensions')

    data_type_out = ADSignal('DataTypeOut', has_rbv=True)
    enable_scale = ADSignal('EnableScale', has_rbv=True)

    _enable_x = ADSignal('EnableX', has_rbv=True)
    _enable_y = ADSignal('EnableY', has_rbv=True)
    _enable_z = ADSignal('EnableZ', has_rbv=True)
    enable = ADSignalGroup(_enable_x, _enable_y, _enable_z,
                           doc='''Enable ROI calculations in the X, Y, Z dimensions.
                           If not enabled then the start, size, binning, and reverse operations
                           are disabled in the X/Y/Z dimension, and the values from the input array
                           are used.''')

    _max_x = ADSignal('MaxX')
    _max_y = ADSignal('MaxY')
    max_ = ADSignalGroup(_max_x, _max_y)

    _max_size_x = ADSignal('MaxSizeX_RBV', rw=False)
    _max_size_y = ADSignal('MaxSizeY_RBV', rw=False)
    _max_size_z = ADSignal('MaxSizeZ_RBV', rw=False)
    max_size = ADSignalGroup(_max_size_x, _max_size_y, _max_size_z,
                             doc='Maximum size of the ROI in the X, Y, and Z dimensions')

    min_x = ADSignal('MinX', has_rbv=True)
    min_y = ADSignal('MinY', has_rbv=True)
    min_z = ADSignal('MinZ', has_rbv=True)
    min_ = ADSignalGroup(min_x, min_y, min_z,
                         doc='Minimum size of the ROI in the X, Y, and Z dimensions')

    name_ = ADSignal('Name', has_rbv=True,
                     doc='ROI name')

    reverse_x = ADSignal('ReverseX', has_rbv=True)
    reverse_y = ADSignal('ReverseY', has_rbv=True)
    reverse_z = ADSignal('ReverseZ', has_rbv=True)
    reverse = ADSignalGroup(reverse_x, reverse_y, reverse_z,
                            doc='Reverse ROI in the X, Y, Z dimensions. (0=No, 1=Yes)')

    scale = ADSignal('Scale', has_rbv=True)
    set_xhopr = ADSignal('SetXHOPR')
    set_yhopr = ADSignal('SetYHOPR')

    _size_x = ADSignal('SizeX', has_rbv=True)
    _size_y = ADSignal('SizeY', has_rbv=True)
    _size_z = ADSignal('SizeZ', has_rbv=True)
    size = ADSignalGroup(_size_x, _size_y, _size_z,
                         doc='Size of the ROI in the X, Y, Z dimensions')

    _size_xlink = ADSignal('SizeXLink')
    _size_ylink = ADSignal('SizeYLink')

    size_link = ADSignalGroup(_size_xlink, _size_ylink)


class TransformPlugin(PluginBase):
    _default_suffix = 'Trans1:'
    _suffix_re = 'Trans\d:'
    _html_docs = ['NDPluginTransform.html']

    width = ADSignal('ArraySize0', has_rbv=True)
    height = ADSignal('ArraySize1', has_rbv=True)
    depth = ADSignal('ArraySize2', has_rbv=True)
    array_size = ADSignalGroup(height, width, depth)

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
    _suffix_re = ''
    _html_docs = ['NDPluginFile.html']

    FileWriteMode = enum(SINGLE=0, CAPTURE=1, STREAM=2)

    auto_increment = ADSignal('AutoIncrement', has_rbv=True)
    auto_save = ADSignal('AutoSave', has_rbv=True)
    capture = ADSignal('Capture', has_rbv=True)
    delete_driver_file = ADSignal('DeleteDriverFile', has_rbv=True)
    file_format = ADSignal('FileFormat', has_rbv=True)
    file_name = ADSignal('FileName', has_rbv=True, string=True)
    file_number = ADSignal('FileNumber', has_rbv=True)
    file_number_sync = ADSignal('FileNumber_Sync')
    file_number_write = ADSignal('FileNumber_write')
    file_path = ADSignal('FilePath', has_rbv=True, string=True)
    file_path_exists = ADSignal('FilePathExists_RBV', rw=False)
    file_template = ADSignal('FileTemplate', has_rbv=True, string=True)
    file_write_mode = ADSignal('FileWriteMode', has_rbv=True)
    full_file_name = ADSignal('FullFileName_RBV', rw=False, string=True)
    num_capture = ADSignal('NumCapture', has_rbv=True)
    num_captured = ADSignal('NumCaptured_RBV', rw=False)
    read_file = ADSignal('ReadFile', has_rbv=True)
    write_file = ADSignal('WriteFile', has_rbv=True)
    write_message = ADSignal('WriteMessage', string=True)
    write_status = ADSignal('WriteStatus')

    def get_filenames(self, detector=None, check=True,
                      using_autosave=True, acquired=True):
        '''Get the filenames saved or to be saved by this file plugin.

        Parameters
        ----------
        detector : AreaDetector, optional
            The detector to use (defaults to the one the plugin was instantiated
            with)
        check : bool, optional
            Check the configured parameters to see if they make sense
        using_autosave : bool, optional
            If using `Capture` mode, set this to False.
        acquired : bool, optional
            If True, pre-existing image filenames are returned.
            If False, image filenames that will be written are returned.

        Returns
        -------
        filenames : list of str
        '''
        detector = self._get_detector(detector)

        if detector.image_mode.value == detector.ImageMode.SINGLE:
            images = 1
        elif detector.image_mode.value == detector.ImageMode.MULTIPLE:
            images = detector.num_images.value
        # elif detector.image_mode.value == detector.ImageMode.CONTINUOUS:
        else:
            raise ValueError('Unhandled image mode: %s' % (detector.image_mode.value, ))

        base_path = self.file_path.value
        file_name = self.file_name.value
        template = self.file_template.value

        if check:
            if not self.file_path_exists.value:
                raise ValueError('Plugin reports path does not exist')

            try:
                template % ('a', 'b', 1)
            except Exception as ex:
                raise ValueError('Invalid filename template (%s)' % ex)

            if not acquired:
                if not self.enable.value:
                    raise ValueError('Plugin not enabled (set enable to 1)')

                if using_autosave:
                    if images > 1 and not self.auto_increment.value:
                        raise ValueError('Images will be overwritten')
                    elif not self.auto_save.value:
                        raise ValueError('Autosave not enabled (set enable to 1)')

        next_number = self.file_number.value
        current_number = next_number - 1

        write_mode = self.file_write_mode.value
        if write_mode == self.FileWriteMode.SINGLE:
            # One file per image
            if acquired:
                # file_number is the next one to save
                last_number = current_number
                first_number = current_number - images + 1
            else:
                first_number = current_number
                last_number = first_number + images - 1
        elif write_mode in (self.FileWriteMode.CAPTURE, self.FileWriteMode.STREAM):
            # Multiple images saved in one file
            #
            # Does not advance to next file if num_capture is hit

            # max_capture = self.num_capture.value
            # if max_capture > 0:
            #     remaining = max_capture - self.num_capture.value

            # TODO this may need reworking
            if acquired:
                first_number = current_number
            else:
                first_number = next_number
            last_number = first_number

        else:
            raise RuntimeError('Unhandled capture write mode')

        return [template % (base_path, file_name, file_num)
                for file_num in range(first_number, last_number + 1)]


class NetCDFPlugin(FilePlugin):
    _default_suffix = 'netCDF1:'
    _suffix_re = 'netCDF\d:'
    _html_docs = ['NDFileNetCDF.html']


class TIFFPlugin(FilePlugin):
    _default_suffix = 'TIFF1:'
    _suffix_re = 'TIFF\d:'
    _html_docs = ['NDFileTIFF.html']


class JPEGPlugin(FilePlugin):
    _default_suffix = 'JPEG1:'
    _suffix_re = 'JPEG\d:'
    _html_docs = ['NDFileJPEG.html']

    jpeg_quality = ADSignal('JPEGQuality', has_rbv=True)


class NexusPlugin(FilePlugin):
    _default_suffix = 'Nexus1:'
    _suffix_re = 'Nexus\d:'
    _html_docs = ['NDFileNexus.html']

    file_template_valid = ADSignal('FileTemplateValid')
    template_file_name = ADSignal('TemplateFileName', has_rbv=True, string=True)
    template_file_path = ADSignal('TemplateFilePath', has_rbv=True, string=True)


class HDF5Plugin(FilePlugin):
    _default_suffix = 'HDF1:'
    _suffix_re = 'HDF\d:'
    _html_docs = ['NDFileHDF5.html']

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
    _suffix_re = 'Magick\d:'
    _html_docs = ['NDFileMagick']  # sic., no html extension

    bit_depth = ADSignal('BitDepth', has_rbv=True)
    compress_type = ADSignal('CompressType', has_rbv=True)
    quality = ADSignal('Quality', has_rbv=True)


type_map = {'NDPluginROI': ROIPlugin,
            'NDPluginStats': StatsPlugin,
            'NDPluginColorConvert': ColorConvPlugin,
            'NDPluginStdArrays': ImagePlugin,
            'NDPluginTransform': TransformPlugin,
            'NDFileNetCDF': NetCDFPlugin,
            'NDFileTIFF': TIFFPlugin,
            'NDFileJPEG': JPEGPlugin,
            'NDPluginFile': NexusPlugin,
            'NDPluginOverlay': OverlayPlugin,
            'NDFileHDF5': HDF5Plugin,
            'NDFileMagick': MagickPlugin,
            'NDPluginProcess': ProcessPlugin,
            }


def plugin_from_pvname(pv):
    '''Get the plugin class from a pvname,
    using regular expressions defined in the classes (_suffix_re).
    '''
    for class_ in type_map.values():
        expr = class_._suffix_re
        m = re.search(expr, pv)
        if m:
            return class_

    return None


def get_areadetector_plugin_class(prefix, suffix=''):
    '''Get an areadetector plugin class by supplying the prefix, suffix, and any
    kwargs for the constructor.

    Uses `plugin_from_pvname` first, but falls back on using epics channel
    access to determine the plugin type.

    Returns
    -------
    plugin : Plugin
        The plugin class

    Raises
    ------
    ValueError
        If the plugin type can't be determined
    '''
    base = ''.join([prefix, suffix])
    class_ = plugin_from_pvname(base)
    if class_ is None:
        type_rbv = ''.join([prefix, suffix, 'PluginType_RBV'])
        type_ = epics.caget(type_rbv)

        # HDF5 includes version number, remove it
        type_ = type_.split(' ')[0]

        class_ = type_map[type_].class_

    return class_


def get_areadetector_plugin(prefix, suffix='', **kwargs):
    '''Get an instance of an areadetector plugin by supplying the prefix,
    suffix, and any kwargs for the constructor.

    Uses `plugin_from_pvname` first, but falls back on using
    epics channel access to determine the plugin type.

    Returns
    -------
    plugin : Plugin
        The plugin instance

    Raises
    ------
    ValueError
        If the plugin type can't be determined
    '''

    class_ = get_areadetector_plugin_class(prefix, suffix)
    if class_ is None:
        raise ValueError('Unable to determine plugin type')

    return class_(prefix, suffix=suffix, **kwargs)


update_docstrings(globals())
