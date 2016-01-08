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

from .base import (ADBase, ADComponent as C, ad_group,
                   EpicsSignalWithRBV as SignalWithRBV)
from ..signal import (EpicsSignalRO, EpicsSignal)
from ..device import DynamicDeviceComponent as DDC, GenerateDatumInterface
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
           'register_plugin',
           ]


_plugin_class = {}


def register_plugin(cls):
    '''Register a plugin'''
    global _plugin_class

    _plugin_class[cls._plugin_type] = cls


class PluginBase(ADBase):
    '''AreaDetector plugin base class'''
    def __init__(self, *args, **kwargs):
        # Turn array callbacks on during staging.
        # Without this, no array data is sent to the plugins.
        self.staged_sigs.update([(self.cam.array_callbacks, 1)])
        super().__init__(*args, **kwargs)

    _html_docs = ['pluginDoc.html']
    _plugin_type = None
    _suffix_re = None

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

    @property
    def array_pixels(self):
        '''The total number of pixels, calculated from array_size'''

        array_size = self.array_size.get()
        dimensions = self.ndimensions.get()

        if dimensions == 0:
            return 0

        pixels = array_size[0]
        for dim in array_size[1:dimensions]:
            pixels *= dim

        return pixels

    width = C(EpicsSignalRO, 'ArraySize0_RBV')
    height = C(EpicsSignalRO, 'ArraySize1_RBV')
    depth = C(EpicsSignalRO, 'ArraySize2_RBV')
    array_size = DDC(ad_group(EpicsSignalRO,
                              (('height', 'ArraySize1_RBV'),
                               ('width', 'ArraySize0_RBV'),
                               ('depth', 'ArraySize2_RBV'))),
                     doc='The array size')

    bayer_pattern = C(EpicsSignalRO, 'BayerPattern_RBV')
    blocking_callbacks = C(SignalWithRBV, 'BlockingCallbacks')
    color_mode = C(EpicsSignalRO, 'ColorMode_RBV')
    data_type = C(EpicsSignalRO, 'DataType_RBV')

    dim0_sa = C(EpicsSignal, 'Dim0SA')
    dim1_sa = C(EpicsSignal, 'Dim1SA')
    dim2_sa = C(EpicsSignal, 'Dim2SA')
    dim_sa = DDC(ad_group(EpicsSignal,
                          (('dim0', 'Dim0SA'),
                           ('dim1', 'Dim1SA'),
                           ('dim2', 'Dim2SA'))),
                 doc='Dimension sub-arrays')

    dimensions = C(EpicsSignalRO, 'Dimensions_RBV')
    dropped_arrays = C(SignalWithRBV, 'DroppedArrays')
    enable = C(SignalWithRBV, 'EnableCallbacks')
    min_callback_time = C(SignalWithRBV, 'MinCallbackTime')
    nd_array_address = C(SignalWithRBV, 'NDArrayAddress')
    nd_array_port = C(SignalWithRBV, 'NDArrayPort')
    ndimensions = C(EpicsSignalRO, 'NDimensions_RBV')
    plugin_type = C(EpicsSignalRO, 'PluginType_RBV')

    queue_free = C(EpicsSignal, 'QueueFree')
    queue_free_low = C(EpicsSignal, 'QueueFreeLow')
    queue_size = C(EpicsSignal, 'QueueSize')
    queue_use = C(EpicsSignal, 'QueueUse')
    queue_use_high = C(EpicsSignal, 'QueueUseHIGH')
    queue_use_hihi = C(EpicsSignal, 'QueueUseHIHI')
    time_stamp = C(EpicsSignalRO, 'TimeStamp_RBV')
    unique_id = C(EpicsSignalRO, 'UniqueId_RBV')


class ImagePlugin(PluginBase):
    _default_suffix = 'image1:'
    _suffix_re = 'image\d:'
    _html_docs = ['NDPluginStdArrays.html']
    _plugin_type = 'NDPluginStdArrays'

    array_data = C(EpicsSignal, 'ArrayData')

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
    _plugin_type = 'NDPluginStats'

    bgd_width = C(SignalWithRBV, 'BgdWidth')
    centroid_threshold = C(SignalWithRBV, 'CentroidThreshold')

    centroid = DDC(ad_group(EpicsSignalRO,
                            (('x', 'CentroidX_RBV'),
                             ('y', 'CentroidY_RBV'))),
                   doc='The centroid XY')

    compute_centroid = C(SignalWithRBV, 'ComputeCentroid')
    compute_histogram = C(SignalWithRBV, 'ComputeHistogram')
    compute_profiles = C(SignalWithRBV, 'ComputeProfiles')
    compute_statistics = C(SignalWithRBV, 'ComputeStatistics')

    cursor = DDC(ad_group(SignalWithRBV,
                          (('x', 'CursorX'),
                           ('y', 'CursorY'))),
                 doc='The cursor XY')

    hist_entropy = C(EpicsSignalRO, 'HistEntropy_RBV')
    hist_max = C(SignalWithRBV, 'HistMax')
    hist_min = C(SignalWithRBV, 'HistMin')
    hist_size = C(SignalWithRBV, 'HistSize')
    histogram = C(EpicsSignalRO, 'Histogram_RBV')

    max_size = DDC(ad_group(EpicsSignal,
                            (('x', 'MaxSizeX'),
                             ('y', 'MaxSizeY'))),
                   doc='The maximum size in XY')

    max_value = C(EpicsSignalRO, 'MaxValue_RBV')
    max_xy = DDC(ad_group(EpicsSignalRO,
                          (('x', 'MaxX_RBV'),
                           ('y', 'MaxY_RBV'))),
                 doc='Maximum in XY')

    mean_value = C(EpicsSignalRO, 'MeanValue_RBV')
    min_value = C(EpicsSignalRO, 'MinValue_RBV')

    min_xy = DDC(ad_group(EpicsSignalRO,
                          (('x', 'MinX_RBV'),
                           ('y', 'MinY_RBV'))),
                 doc='Minimum in XY')

    net = C(EpicsSignalRO, 'Net_RBV')
    profile_average = DDC(ad_group(EpicsSignalRO,
                                   (('x', 'ProfileAverageX_RBV'),
                                    ('y', 'ProfileAverageY_RBV'))),
                          doc='Profile average in XY')

    profile_centroid = DDC(ad_group(EpicsSignalRO,
                                    (('x', 'ProfileCentroidX_RBV'),
                                     ('y', 'ProfileCentroidY_RBV'))),
                           doc='Profile centroid in XY')

    profile_cursor = DDC(ad_group(EpicsSignalRO,
                                  (('x', 'ProfileCursorX_RBV'),
                                   ('y', 'ProfileCursorY_RBV'))),
                         doc='Profile cursor in XY')

    profile_size = DDC(ad_group(EpicsSignalRO,
                                (('x', 'ProfileSizeX_RBV'),
                                 ('y', 'ProfileSizeY_RBV'))),
                       doc='Profile size in XY')

    profile_threshold = DDC(ad_group(EpicsSignalRO,
                                     (('x', 'ProfileThresholdX_RBV'),
                                      ('y', 'ProfileThresholdY_RBV'))),
                            doc='Profile threshold in XY')

    set_xhopr = C(EpicsSignal, 'SetXHOPR')
    set_yhopr = C(EpicsSignal, 'SetYHOPR')
    sigma_xy = C(EpicsSignalRO, 'SigmaXY_RBV')
    sigma_x = C(EpicsSignalRO, 'SigmaX_RBV')
    sigma_y = C(EpicsSignalRO, 'SigmaY_RBV')
    sigma = C(EpicsSignalRO, 'Sigma_RBV')
    ts_acquiring = C(EpicsSignal, 'TSAcquiring')

    ts_centroid = DDC(ad_group(EpicsSignal,
                               (('x', 'TSCentroidX'),
                                ('y', 'TSCentroidY'))),
                      doc='Time series centroid in XY')

    ts_control = C(EpicsSignal, 'TSControl')
    ts_current_point = C(EpicsSignal, 'TSCurrentPoint')
    ts_max_value = C(EpicsSignal, 'TSMaxValue')

    ts_max = DDC(ad_group(EpicsSignal,
                          (('x', 'TSMaxX'),
                           ('y', 'TSMaxY'))),
                 doc='Time series maximum in XY')

    ts_mean_value = C(EpicsSignal, 'TSMeanValue')
    ts_min_value = C(EpicsSignal, 'TSMinValue')

    ts_min = DDC(ad_group(EpicsSignal,
                          (('x', 'TSMinX'),
                           ('y', 'TSMinY'))),
                 doc='Time series minimum in XY')

    ts_net = C(EpicsSignal, 'TSNet')
    ts_num_points = C(EpicsSignal, 'TSNumPoints')
    ts_read = C(EpicsSignal, 'TSRead')
    ts_sigma = C(EpicsSignal, 'TSSigma')
    ts_sigma_x = C(EpicsSignal, 'TSSigmaX')
    ts_sigma_xy = C(EpicsSignal, 'TSSigmaXY')
    ts_sigma_y = C(EpicsSignal, 'TSSigmaY')
    ts_total = C(EpicsSignal, 'TSTotal')
    total = C(EpicsSignalRO, 'Total_RBV')


class ColorConvPlugin(PluginBase):
    _default_suffix = 'CC1:'
    _suffix_re = 'CC\d:'
    _html_docs = ['NDPluginColorConvert.html']
    _plugin_type = 'NDPluginColorConvert'

    color_mode_out = C(SignalWithRBV, 'ColorModeOut')
    false_color = C(SignalWithRBV, 'FalseColor')


class ProcessPlugin(PluginBase):
    _default_suffix = 'Proc1:'
    _suffix_re = 'Proc\d:'
    _html_docs = ['NDPluginProcess.html']
    _plugin_type = 'NDPluginProcess'

    auto_offset_scale = C(EpicsSignal, 'AutoOffsetScale')
    auto_reset_filter = C(SignalWithRBV, 'AutoResetFilter')
    average_seq = C(EpicsSignal, 'AverageSeq')
    copy_to_filter_seq = C(EpicsSignal, 'CopyToFilterSeq')
    data_type_out = C(SignalWithRBV, 'DataTypeOut')
    difference_seq = C(EpicsSignal, 'DifferenceSeq')
    enable_background = C(SignalWithRBV, 'EnableBackground')
    enable_filter = C(SignalWithRBV, 'EnableFilter')
    enable_flat_field = C(SignalWithRBV, 'EnableFlatField')
    enable_high_clip = C(SignalWithRBV, 'EnableHighClip')
    enable_low_clip = C(SignalWithRBV, 'EnableLowClip')
    enable_offset_scale = C(SignalWithRBV, 'EnableOffsetScale')

    fc = DDC(ad_group(SignalWithRBV,
                      (('fc1', 'FC1'),
                       ('fc2', 'FC2'),
                       ('fc3', 'FC3'),
                       ('fc4', 'FC4'))),
             doc='Filter coefficients')

    foffset = C(SignalWithRBV, 'FOffset')
    fscale = C(SignalWithRBV, 'FScale')
    filter_callbacks = C(SignalWithRBV, 'FilterCallbacks')
    filter_type = C(EpicsSignal, 'FilterType')
    filter_type_seq = C(EpicsSignal, 'FilterTypeSeq')
    high_clip = C(SignalWithRBV, 'HighClip')
    low_clip = C(SignalWithRBV, 'LowClip')
    num_filter = C(SignalWithRBV, 'NumFilter')
    num_filter_recip = C(EpicsSignal, 'NumFilterRecip')
    num_filtered = C(EpicsSignalRO, 'NumFiltered_RBV')

    oc = DDC(ad_group(SignalWithRBV,
                      (('oc1', 'OC1'),
                       ('oc2', 'OC2'),
                       ('oc3', 'OC3'),
                       ('oc4', 'OC4'))),
             doc='Output coefficients')

    o_offset = C(SignalWithRBV, 'OOffset')
    o_scale = C(SignalWithRBV, 'OScale')
    offset = C(SignalWithRBV, 'Offset')

    rc = DDC(ad_group(SignalWithRBV,
                      (('rc1', 'RC1'),
                       ('rc2', 'RC2'))),
             doc='Filter coefficients')

    roffset = C(SignalWithRBV, 'ROffset')
    recursive_ave_diff_seq = C(EpicsSignal, 'RecursiveAveDiffSeq')
    recursive_ave_seq = C(EpicsSignal, 'RecursiveAveSeq')
    reset_filter = C(SignalWithRBV, 'ResetFilter')
    save_background = C(SignalWithRBV, 'SaveBackground')
    save_flat_field = C(SignalWithRBV, 'SaveFlatField')
    scale = C(SignalWithRBV, 'Scale')
    scale_flat_field = C(SignalWithRBV, 'ScaleFlatField')
    sum_seq = C(EpicsSignal, 'SumSeq')
    valid_background = C(EpicsSignalRO, 'ValidBackground_RBV')
    valid_flat_field = C(EpicsSignalRO, 'ValidFlatField_RBV')


class Overlay(ADBase):
    _html_docs = ['NDPluginOverlay.html']

    blue = C(SignalWithRBV, 'Blue')
    draw_mode = C(SignalWithRBV, 'DrawMode')
    green = C(SignalWithRBV, 'Green')
    max_size_x = C(EpicsSignal, 'MaxSizeX')
    max_size_y = C(EpicsSignal, 'MaxSizeY')
    overlay_portname = C(SignalWithRBV, 'Name')

    position_x = C(SignalWithRBV, 'PositionX')
    position_y = C(SignalWithRBV, 'PositionY')

    position_xlink = C(EpicsSignal, 'PositionXLink')
    position_ylink = C(EpicsSignal, 'PositionYLink')

    red = C(SignalWithRBV, 'Red')
    set_xhopr = C(EpicsSignal, 'SetXHOPR')
    set_yhopr = C(EpicsSignal, 'SetYHOPR')
    shape = C(SignalWithRBV, 'Shape')

    size_x = C(SignalWithRBV, 'SizeX')
    size_y = C(SignalWithRBV, 'SizeY')

    size_xlink = C(EpicsSignal, 'SizeXLink')
    size_ylink = C(EpicsSignal, 'SizeYLink')
    use = C(SignalWithRBV, 'Use')


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
    _plugin_type = 'NDPluginOverlay'

    max_size = DDC(ad_group(EpicsSignalRO,
                            (('x', 'MaxSizeX_RBV'),
                             ('y', 'MaxSizeY_RBV'))),
                   doc='The maximum size in XY')

    overlay_1 = C(Overlay, 'Overlay1:')


class ROIPlugin(PluginBase):
    _default_suffix = 'ROI1:'
    _suffix_re = 'ROI\d:'
    _html_docs = ['NDPluginROI.html']
    _plugin_type = 'NDPluginROI'

    array_size = DDC(ad_group(EpicsSignalRO,
                              (('x', 'ArraySizeX_RBV'),
                               ('y', 'ArraySizeY_RBV'),
                               ('z', 'ArraySizeZ_RBV'))),
                     doc='Size of the ROI data in XYZ')

    auto_size = DDC(ad_group(SignalWithRBV,
                             (('x', 'AutoSizeX'),
                              ('y', 'AutoSizeY'),
                              ('z', 'AutoSizeZ'))),
                    doc=('Automatically set SizeXYZ to the input array size '
                         'minus MinXYZ'))

    bin_ = DDC(ad_group(SignalWithRBV,
                        (('x', 'BinX'),
                         ('y', 'BinY'),
                         ('z', 'BinZ'))),
               doc='Binning in XYZ')

    data_type_out = C(SignalWithRBV, 'DataTypeOut')
    enable_scale = C(SignalWithRBV, 'EnableScale')

    enable = DDC(ad_group(SignalWithRBV,
                          (('x', 'EnableX'),
                           ('y', 'EnableY'),
                           ('z', 'EnableZ'))),
                 doc=('Enable ROI calculations in the X, Y, Z dimensions. '
                      'If not enabled then the start, size, binning, and '
                      'reverse operations are disabled in the X/Y/Z '
                      'dimension, and the values from the input array '
                      'are used.'))

    max_xy = DDC(ad_group(EpicsSignal,
                          (('x', 'MaxX'),
                           ('y', 'MaxY'))),
                 doc='Maximum in XY')

    max_size = DDC(ad_group(EpicsSignalRO,
                            (('x', 'MaxSizeX_RBV'),
                             ('y', 'MaxSizeY_RBV'),
                             ('z', 'MaxSizeZ_RBV'))),
                   doc='Maximum size of the ROI in XYZ')

    min_xyz = DDC(ad_group(SignalWithRBV,
                           (('min_x', 'MinX'),
                            ('min_y', 'MinY'),
                            ('min_z', 'MinZ'))),
                  doc='Minimum size of the ROI in XYZ')

    name_ = C(SignalWithRBV, 'Name', doc='ROI name')
    reverse = DDC(ad_group(SignalWithRBV,
                           (('x', 'ReverseX'),
                            ('y', 'ReverseY'),
                            ('z', 'ReverseZ'))),
                  doc='Reverse ROI in the XYZ dimensions. (0=No, 1=Yes)')

    scale = C(SignalWithRBV, 'Scale')
    set_xhopr = C(EpicsSignal, 'SetXHOPR')
    set_yhopr = C(EpicsSignal, 'SetYHOPR')

    size = DDC(ad_group(SignalWithRBV,
                        (('x', 'SizeX'),
                         ('y', 'SizeY'),
                         ('z', 'SizeZ'))),
               doc='Size of the ROI in XYZ')

    size_link = DDC(ad_group(EpicsSignal,
                             (('x', 'SizeXLink'),
                              ('y', 'SizeYLink'))),
                    doc='Size link in XY')


class TransformPlugin(PluginBase):
    _default_suffix = 'Trans1:'
    _suffix_re = 'Trans\d:'
    _html_docs = ['NDPluginTransform.html']
    _plugin_type = 'NDPluginTransform'

    width = C(SignalWithRBV, 'ArraySize0')
    height = C(SignalWithRBV, 'ArraySize1')
    depth = C(SignalWithRBV, 'ArraySize2')
    array_size = DDC(ad_group(SignalWithRBV,
                              (('height', 'ArraySize1'),
                               ('width', 'ArraySize0'),
                               ('depth', 'ArraySize2'))),
                     doc='Array size')

    name_ = C(EpicsSignal, 'Name')
    origin_location = C(SignalWithRBV, 'OriginLocation')
    t1_max_size = DDC(ad_group(EpicsSignal,
                               (('size0', 'T1MaxSize0'),
                                ('size1', 'T1MaxSize1'),
                                ('size2', 'T1MaxSize2'))),
                      doc='Transform 1 max size')

    t2_max_size = DDC(ad_group(EpicsSignal,
                               (('size0', 'T2MaxSize0'),
                                ('size1', 'T2MaxSize1'),
                                ('size2', 'T2MaxSize2'))),
                      doc='Transform 2 max size')

    t3_max_size = DDC(ad_group(EpicsSignal,
                               (('size0', 'T3MaxSize0'),
                                ('size1', 'T3MaxSize1'),
                                ('size2', 'T3MaxSize2'))),
                      doc='Transform 3 max size')

    t4_max_size = DDC(ad_group(EpicsSignal,
                               (('size0', 'T4MaxSize0'),
                                ('size1', 'T4MaxSize1'),
                                ('size2', 'T4MaxSize2'))),
                      doc='Transform 4 max size')

    types = DDC(ad_group(EpicsSignal,
                         (('type1', 'Type1'),
                          ('type2', 'Type2'),
                          ('type3', 'Type3'),
                          ('type4', 'Type4'))),
                doc='Transform types')


class FilePlugin(PluginBase, GenerateDatumInterface):
    _default_suffix = ''
    _html_docs = ['NDPluginFile.html']
    _plugin_type = 'NDPluginFile'

    FileWriteMode = enum(SINGLE=0, CAPTURE=1, STREAM=2)

    auto_increment = C(SignalWithRBV, 'AutoIncrement')
    auto_save = C(SignalWithRBV, 'AutoSave')
    capture = C(SignalWithRBV, 'Capture')
    delete_driver_file = C(SignalWithRBV, 'DeleteDriverFile')
    file_format = C(SignalWithRBV, 'FileFormat')
    file_name = C(SignalWithRBV, 'FileName', string=True)
    file_number = C(SignalWithRBV, 'FileNumber')
    file_number_sync = C(EpicsSignal, 'FileNumber_Sync')
    file_number_write = C(EpicsSignal, 'FileNumber_write')
    file_path = C(SignalWithRBV, 'FilePath', string=True)
    file_path_exists = C(EpicsSignalRO, 'FilePathExists_RBV')
    file_template = C(SignalWithRBV, 'FileTemplate', string=True)
    file_write_mode = C(SignalWithRBV, 'FileWriteMode')
    full_file_name = C(EpicsSignalRO, 'FullFileName_RBV', string=True)
    num_capture = C(SignalWithRBV, 'NumCapture')
    num_captured = C(EpicsSignalRO, 'NumCaptured_RBV')
    read_file = C(SignalWithRBV, 'ReadFile')
    write_file = C(SignalWithRBV, 'WriteFile')
    write_message = C(EpicsSignal, 'WriteMessage', string=True)
    write_status = C(EpicsSignal, 'WriteStatus')


class NetCDFPlugin(FilePlugin):
    _default_suffix = 'netCDF1:'
    _suffix_re = 'netCDF\d:'
    _html_docs = ['NDFileNetCDF.html']
    _plugin_type = 'NDFileNetCDF'


class TIFFPlugin(FilePlugin):
    _default_suffix = 'TIFF1:'
    _suffix_re = 'TIFF\d:'
    _html_docs = ['NDFileTIFF.html']
    _plugin_type = 'NDFileTIFF'


class JPEGPlugin(FilePlugin):
    _default_suffix = 'JPEG1:'
    _suffix_re = 'JPEG\d:'
    _html_docs = ['NDFileJPEG.html']
    _plugin_type = 'NDFileJPEG'

    jpeg_quality = C(SignalWithRBV, 'JPEGQuality')


class NexusPlugin(FilePlugin):
    _default_suffix = 'Nexus1:'
    _suffix_re = 'Nexus\d:'
    _html_docs = ['NDFileNexus.html']
    # _plugin_type = 'NDPluginFile'  # TODO was this ever fixed?
    _plugin_type = 'NDPluginNexus'

    file_template_valid = C(EpicsSignal, 'FileTemplateValid')
    template_file_name = C(SignalWithRBV, 'TemplateFileName', string=True)
    template_file_path = C(SignalWithRBV, 'TemplateFilePath', string=True)


class HDF5Plugin(FilePlugin):
    _default_suffix = 'HDF1:'
    _suffix_re = 'HDF\d:'
    _html_docs = ['NDFileHDF5.html']
    _plugin_type = 'NDFileHDF5'

    boundary_align = C(SignalWithRBV, 'BoundaryAlign')
    boundary_threshold = C(SignalWithRBV, 'BoundaryThreshold')
    compression = C(SignalWithRBV, 'Compression')
    data_bits_offset = C(SignalWithRBV, 'DataBitsOffset')

    extra_dim_name = DDC(ad_group(EpicsSignalRO,
                                  (('name_x', 'ExtraDimNameX_RBV'),
                                   ('name_y', 'ExtraDimNameY_RBV'),
                                   ('name_n', 'ExtraDimNameN_RBV'))),
                         doc='Extra dimension names (XYN)')
    extra_dim_size = DDC(ad_group(SignalWithRBV,
                                  (('size_x', 'ExtraDimSizeX'),
                                   ('size_y', 'ExtraDimSizeY'),
                                   ('size_n', 'ExtraDimSizeN'))),
                         doc='Extra dimension sizes (XYN)')

    io_speed = C(EpicsSignal, 'IOSpeed')
    num_col_chunks = C(SignalWithRBV, 'NumColChunks')
    num_data_bits = C(SignalWithRBV, 'NumDataBits')
    num_extra_dims = C(SignalWithRBV, 'NumExtraDims')
    num_frames_chunks = C(SignalWithRBV, 'NumFramesChunks')
    num_frames_flush = C(SignalWithRBV, 'NumFramesFlush')
    num_row_chunks = C(SignalWithRBV, 'NumRowChunks')
    run_time = C(EpicsSignal, 'RunTime')
    szip_num_pixels = C(SignalWithRBV, 'SZipNumPixels')
    store_attr = C(SignalWithRBV, 'StoreAttr')
    store_perform = C(SignalWithRBV, 'StorePerform')
    zlevel = C(SignalWithRBV, 'ZLevel')

    def warmup(self):
        # TODO save and then restore previous values
        self.parent.cam.array_callbacks.put(1)  # make plugins work
        self.enable.put(1)  # enable HDF5 plugin
        self.parent.cam.image_mode.put(0)  # single image mode
        self.parent.cam.trigger_mode.put(0)  # 'internal'
        self.parent.cam.acquire_time.put(1)  # to make sure they are not super long
        self.parent.cam.acquire_period.put(1)
        self.parent.cam.acquire.put(1)  # acquiring one image primes array info


class MagickPlugin(FilePlugin):
    _default_suffix = 'Magick1:'
    _suffix_re = 'Magick\d:'
    _html_docs = ['NDFileMagick']  # sic., no html extension
    _plugin_type = 'NDFileMagick'

    bit_depth = C(SignalWithRBV, 'BitDepth')
    compress_type = C(SignalWithRBV, 'CompressType')
    quality = C(SignalWithRBV, 'Quality')


# register_plugin(PluginBase)
register_plugin(ImagePlugin)
register_plugin(StatsPlugin)
register_plugin(ColorConvPlugin)
register_plugin(ProcessPlugin)
register_plugin(OverlayPlugin)
register_plugin(ROIPlugin)
register_plugin(TransformPlugin)
# register_plugin(FilePlugin)
register_plugin(NetCDFPlugin)
register_plugin(TIFFPlugin)
register_plugin(JPEGPlugin)
register_plugin(NexusPlugin)
register_plugin(HDF5Plugin)
register_plugin(MagickPlugin)


def plugin_from_pvname(pv):
    '''Get the plugin class from a pvname,
    using regular expressions defined in the classes (_suffix_re).
    '''
    global _plugin_class

    for type_, cls in _plugin_class.items():
        m = re.search(cls._suffix_re, pv)
        if m:
            return cls

    return None


def get_areadetector_plugin_class(prefix, timeout=2.0):
    '''Get an areadetector plugin class by supplying its PV prefix

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
    cls = plugin_from_pvname(prefix)
    if cls is not None:
        return cls

    type_rbv = prefix + 'PluginType_RBV'
    type_ = epics.caget(type_rbv, timeout=timeout)

    if type_ is None:
        raise ValueError('Unable to determine plugin type (caget timed out)')

    # HDF5 includes version number, remove it
    type_ = type_.split(' ')[0]

    try:
        return _plugin_class[type_]
    except KeyError:
        raise ValueError('Unable to determine plugin type (PluginType={})'
                         ''.format(type_))


def get_areadetector_plugin(prefix, **kwargs):
    '''Get an instance of an areadetector plugin by supplying its PV prefix
    and any kwargs for the constructor.

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

    cls = get_areadetector_plugin_class(prefix)
    if cls is None:
        raise ValueError('Unable to determine plugin type')

    return cls(prefix, **kwargs)
