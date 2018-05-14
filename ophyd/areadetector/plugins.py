# vi: ts=4 sw=4
'''AreaDetector plugins

 `areaDetector`_ plugin abstractions

.. _areaDetector: http://cars.uchicago.edu/software/epics/areaDetector.html
'''


import re
import time as ttime
import logging
from collections import OrderedDict
import numpy as np

from ophyd import Component as Cpt
from .base import (ADBase, ADComponent as C, ad_group,
                   EpicsSignalWithRBV as SignalWithRBV)
from ..signal import (EpicsSignalRO, EpicsSignal, ArrayAttributeSignal)
from ..device import DynamicDeviceComponent as DDC, GenerateDatumInterface
from ..utils import enum, set_and_wait


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

        super().__init__(*args, **kwargs)
        # make sure it is the right type of plugin
        if (self._plugin_type is not None and
                not self.plugin_type.get().startswith(self._plugin_type)):
            raise TypeError('Trying to use {!r} class which is for {!r} '
                            'plugin type for a plugin that reports being '
                            'of type {!r} with base prefix '
                            '{!r}'.format(self.__class__.__name__,
                                          self._plugin_type,
                                          self.plugin_type.get(), self.prefix))

        self.enable_on_stage()
        self.stage_sigs.move_to_end('enable', last=False)
        self.ensure_blocking()
        if self.parent is not None and hasattr(self.parent, 'cam'):
            self.stage_sigs.update([('parent.cam.array_callbacks', 1),
                                    ])

    _default_configuration_attrs = (ADBase._default_configuration_attrs +
                                    ('port_name', 'nd_array_port', 'enable',
                                     'blocking_callbacks', 'plugin_type',
                                     'asyn_pipeline_config',
                                     'configuration_names'))

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

    def stage(self):
        super().stage()

    def enable_on_stage(self):
        """
        when the plugin is staged, ensure that it is enabled.

        a convenience method for adding ('enable', 1) to stage_sigs
        """
        self.stage_sigs['enable'] = 1

    def disable_on_stage(self):
        """
        when the plugin is staged, ensure that it is disabled.

        a convenience method for adding ```('enable', 0)`` to stage_sigs
        """
        self.stage_sigs['enable'] = 0	

    def ensure_blocking(self):
        """
        Ensure that if plugin is enabled after staging, callbacks block.

        a convenience method for adding ```('blocking_callbacks', 1)`` to
        stage_sigs
        """
        self.stage_sigs['blocking_callbacks'] = 'Yes'

    def ensure_nonblocking(self):
        """
        Ensure that if plugin is enabled after staging, callbacks don't block.

        a convenience method for adding ```('blocking_callbacks', 0)`` to
        stage_sigs
        """
        self.stage_sigs['blocking_callbacks'] = 'No'

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

    def read_configuration(self):
        ret = super().read_configuration()

        ret.update(self.source_plugin.read_configuration())

        return ret

    @property
    def source_plugin(self):
        '''The PluginBase object that is the asyn source for this plugin.
        '''
        source_port = self.nd_array_port.get()
        source_plugin = self.ad_root.get_plugin_by_asyn_port(source_port)
        return source_plugin

    def describe_configuration(self):
        ret = super().describe_configuration()

        source_plugin = self.source_plugin
        ret.update(source_plugin.describe_configuration())

        return ret

    @property
    def _asyn_pipeline(self):
        parent = self.ad_root.get_plugin_by_asyn_port(self.nd_array_port.get())
        if hasattr(parent, '_asyn_pipeline'):
            return parent._asyn_pipeline + (self, )
        return (parent, self)

    @property
    def _asyn_pipeline_configuration_names(self):
        return [_.configuration_names.name for _ in self._asyn_pipeline]

    asyn_pipeline_config = Cpt(ArrayAttributeSignal,
                               attr='_asyn_pipeline_configuration_names')

    width = C(EpicsSignalRO, 'ArraySize0_RBV')
    height = C(EpicsSignalRO, 'ArraySize1_RBV')
    depth = C(EpicsSignalRO, 'ArraySize2_RBV')
    array_size = DDC(ad_group(EpicsSignalRO,
                              (('height', 'ArraySize1_RBV'),
                               ('width', 'ArraySize0_RBV'),
                               ('depth', 'ArraySize2_RBV'))),
                     doc='The array size',
                     default_read_attrs=('height', 'width', 'depth'))

    bayer_pattern = C(EpicsSignalRO, 'BayerPattern_RBV')
    blocking_callbacks = C(SignalWithRBV, 'BlockingCallbacks',
                           string=True)
    color_mode = C(EpicsSignalRO, 'ColorMode_RBV')
    data_type = C(EpicsSignalRO, 'DataType_RBV', string=True)

    dim0_sa = C(EpicsSignal, 'Dim0SA')
    dim1_sa = C(EpicsSignal, 'Dim1SA')
    dim2_sa = C(EpicsSignal, 'Dim2SA')
    dim_sa = DDC(ad_group(EpicsSignal,
                          (('dim0', 'Dim0SA'),
                           ('dim1', 'Dim1SA'),
                           ('dim2', 'Dim2SA'))),
                 doc='Dimension sub-arrays',
                 default_read_attrs=('dim0', 'dim1', 'dim2'))

    dimensions = C(EpicsSignalRO, 'Dimensions_RBV')
    dropped_arrays = C(SignalWithRBV, 'DroppedArrays')
    enable = C(SignalWithRBV, 'EnableCallbacks', string=True)
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
        array_size = self.array_size.get()
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

    _default_configuration_attrs = (PluginBase._default_configuration_attrs + (
        'centroid_threshold', 'compute_centroid', 'compute_histogram',
        'compute_profiles', 'ts_control', 'compute_statistics', 'bgd_width',
        'hist_size', 'hist_min', 'hist_max', 'ts_num_points', 'profile_size',
        'profile_cursor')
    )

    bgd_width = C(SignalWithRBV, 'BgdWidth')
    centroid_threshold = C(SignalWithRBV, 'CentroidThreshold')

    centroid = DDC(ad_group(EpicsSignalRO,
                            (('x', 'CentroidX_RBV'),
                             ('y', 'CentroidY_RBV'))),
                   doc='The centroid XY',
                   default_read_attrs=('x', 'y'))

    compute_centroid = C(SignalWithRBV, 'ComputeCentroid', string=True)
    compute_histogram = C(SignalWithRBV, 'ComputeHistogram', string=True)
    compute_profiles = C(SignalWithRBV, 'ComputeProfiles', string=True)
    compute_statistics = C(SignalWithRBV, 'ComputeStatistics', string=True)

    cursor = DDC(ad_group(SignalWithRBV,
                          (('x', 'CursorX'),
                           ('y', 'CursorY'))),
                 doc='The cursor XY',
                 default_read_attrs=('x', 'y'))

    hist_entropy = C(EpicsSignalRO, 'HistEntropy_RBV')
    hist_max = C(SignalWithRBV, 'HistMax')
    hist_min = C(SignalWithRBV, 'HistMin')
    hist_size = C(SignalWithRBV, 'HistSize')
    histogram = C(EpicsSignalRO, 'Histogram_RBV')

    max_size = DDC(ad_group(EpicsSignal,
                            (('x', 'MaxSizeX'),
                             ('y', 'MaxSizeY'))),
                   doc='The maximum size in XY',
                   default_read_attrs=('x', 'y'))

    max_value = C(EpicsSignalRO, 'MaxValue_RBV')
    max_xy = DDC(ad_group(EpicsSignalRO,
                          (('x', 'MaxX_RBV'),
                           ('y', 'MaxY_RBV'))),
                 doc='Maximum in XY',
                 default_read_attrs=('x', 'y'))

    mean_value = C(EpicsSignalRO, 'MeanValue_RBV')
    min_value = C(EpicsSignalRO, 'MinValue_RBV')

    min_xy = DDC(ad_group(EpicsSignalRO,
                          (('x', 'MinX_RBV'),
                           ('y', 'MinY_RBV'))),
                 doc='Minimum in XY',
                 default_read_attrs=('x', 'y'))

    net = C(EpicsSignalRO, 'Net_RBV')
    profile_average = DDC(ad_group(EpicsSignalRO,
                                   (('x', 'ProfileAverageX_RBV'),
                                    ('y', 'ProfileAverageY_RBV'))),
                          doc='Profile average in XY',
                          default_read_attrs=('x', 'y'))

    profile_centroid = DDC(ad_group(EpicsSignalRO,
                                    (('x', 'ProfileCentroidX_RBV'),
                                     ('y', 'ProfileCentroidY_RBV'))),
                           doc='Profile centroid in XY',
                           default_read_attrs=('x', 'y'))

    profile_cursor = DDC(ad_group(EpicsSignalRO,
                                  (('x', 'ProfileCursorX_RBV'),
                                   ('y', 'ProfileCursorY_RBV'))),
                         doc='Profile cursor in XY',
                         default_read_attrs=('x', 'y'))

    profile_size = DDC(ad_group(EpicsSignalRO,
                                (('x', 'ProfileSizeX_RBV'),
                                 ('y', 'ProfileSizeY_RBV'))),
                       doc='Profile size in XY',
                       default_read_attrs=('x', 'y'))

    profile_threshold = DDC(ad_group(EpicsSignalRO,
                                     (('x', 'ProfileThresholdX_RBV'),
                                      ('y', 'ProfileThresholdY_RBV'))),
                            doc='Profile threshold in XY',
                            default_read_attrs=('x', 'y'))

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
                      doc='Time series centroid in XY',
                      default_read_attrs=('x', 'y'))

    ts_control = C(EpicsSignal, 'TSControl', string=True)
    ts_current_point = C(EpicsSignal, 'TSCurrentPoint')
    ts_max_value = C(EpicsSignal, 'TSMaxValue')

    ts_max = DDC(ad_group(EpicsSignal,
                          (('x', 'TSMaxX'),
                           ('y', 'TSMaxY'))),
                 doc='Time series maximum in XY',
                 default_read_attrs=('x', 'y'))

    ts_mean_value = C(EpicsSignal, 'TSMeanValue')
    ts_min_value = C(EpicsSignal, 'TSMinValue')

    ts_min = DDC(ad_group(EpicsSignal,
                          (('x', 'TSMinX'),
                           ('y', 'TSMinY'))),
                 doc='Time series minimum in XY',
                 default_read_attrs=('x', 'y'))

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
    _default_configuration_attrs = (PluginBase._default_configuration_attrs +
                                    ('color_mode_out', 'false_color'))

    color_mode_out = C(SignalWithRBV, 'ColorModeOut')
    false_color = C(SignalWithRBV, 'FalseColor')


class ProcessPlugin(PluginBase):
    _default_suffix = 'Proc1:'
    _suffix_re = 'Proc\d:'
    _html_docs = ['NDPluginProcess.html']
    _plugin_type = 'NDPluginProcess'
    _default_configuration_attrs = (PluginBase._default_configuration_attrs + (
        'data_type',
        'auto_offset_scale',
        'auto_reset_filter',
        'copy_to_filter_seq',
        'data_type_out',
        'difference_seq',
        'enable_background',
        'enable_filter',
        'enable_flat_field',
        'enable_high_clip',
        'enable_low_clip',
        'enable_offset_scale',
        'fc',
        'foffset',
        'fscale',
        'filter_callbacks',
        'filter_type',
        'filter_type_seq',
        'high_clip',
        'low_clip',
        'num_filter',
        'num_filter_recip',
        'num_filtered',
        'oc',
        'o_offset',
        'o_scale',
        'offset',
        'rc',
        'roffset',
        'scale',
        'scale_flat_field',
        'valid_background',
        'valid_flat_field')
    )
    auto_offset_scale = C(EpicsSignal, 'AutoOffsetScale', string=True)
    auto_reset_filter = C(SignalWithRBV, 'AutoResetFilter', string=True)
    average_seq = C(EpicsSignal, 'AverageSeq')
    copy_to_filter_seq = C(EpicsSignal, 'CopyToFilterSeq')
    data_type_out = C(SignalWithRBV, 'DataTypeOut', string=True)
    difference_seq = C(EpicsSignal, 'DifferenceSeq')
    enable_background = C(SignalWithRBV, 'EnableBackground', string=True)
    enable_filter = C(SignalWithRBV, 'EnableFilter', string=True)
    enable_flat_field = C(SignalWithRBV, 'EnableFlatField', string=True)
    enable_high_clip = C(SignalWithRBV, 'EnableHighClip', string=True)
    enable_low_clip = C(SignalWithRBV, 'EnableLowClip', string=True)
    enable_offset_scale = C(SignalWithRBV, 'EnableOffsetScale', string=True)

    fc = DDC(ad_group(SignalWithRBV,
                      (('fc1', 'FC1'),
                       ('fc2', 'FC2'),
                       ('fc3', 'FC3'),
                       ('fc4', 'FC4'))),
             doc='Filter coefficients',
             default_read_attrs=('fc1', 'fc2', 'fc3', 'fc4'))

    foffset = C(SignalWithRBV, 'FOffset')
    fscale = C(SignalWithRBV, 'FScale')
    filter_callbacks = C(SignalWithRBV, 'FilterCallbacks', string=True)
    filter_type = C(EpicsSignal, 'FilterType', string=True)
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
             doc='Output coefficients',
             default_read_attrs=('oc1', 'oc2', 'oc3', 'oc4'))

    o_offset = C(SignalWithRBV, 'OOffset')
    o_scale = C(SignalWithRBV, 'OScale')
    offset = C(SignalWithRBV, 'Offset')

    rc = DDC(ad_group(SignalWithRBV,
                      (('rc1', 'RC1'),
                       ('rc2', 'RC2'))),
             doc='Filter coefficients',
             default_read_attrs=('rc1', 'rc2'))

    roffset = C(SignalWithRBV, 'ROffset')
    recursive_ave_diff_seq = C(EpicsSignal, 'RecursiveAveDiffSeq')
    recursive_ave_seq = C(EpicsSignal, 'RecursiveAveSeq')
    reset_filter = C(SignalWithRBV, 'ResetFilter')
    save_background = C(SignalWithRBV, 'SaveBackground')
    save_flat_field = C(SignalWithRBV, 'SaveFlatField')
    scale = C(SignalWithRBV, 'Scale')
    scale_flat_field = C(SignalWithRBV, 'ScaleFlatField')
    sum_seq = C(EpicsSignal, 'SumSeq')
    valid_background = C(EpicsSignalRO, 'ValidBackground_RBV', string=True)
    valid_flat_field = C(EpicsSignalRO, 'ValidFlatField_RBV', string=True)


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
    '''
    _default_suffix = 'Over1:'
    _suffix_re = 'Over\d:'
    _html_docs = ['NDPluginOverlay.html']
    _plugin_type = 'NDPluginOverlay'
    _default_configuration_attrs = (PluginBase._default_configuration_attrs + (
        'overlay_1', 'overlay_2', 'overlay_3', 'overlay_4', 'overlay_5',
        'overlay_6', 'overlay_7', 'overlay_8')
    )
    max_size = DDC(ad_group(EpicsSignalRO,
                            (('x', 'MaxSizeX_RBV'),
                             ('y', 'MaxSizeY_RBV'))),
                   doc='The maximum size in XY',
                   default_read_attrs=('x', 'y'))

    overlay_1 = C(Overlay, '1:')
    overlay_2 = C(Overlay, '2:')
    overlay_3 = C(Overlay, '3:')
    overlay_4 = C(Overlay, '4:')
    overlay_5 = C(Overlay, '5:')
    overlay_6 = C(Overlay, '6:')
    overlay_7 = C(Overlay, '7:')
    overlay_8 = C(Overlay, '8:')


class ROIPlugin(PluginBase):
    _default_suffix = 'ROI1:'
    _suffix_re = 'ROI\d:'
    _html_docs = ['NDPluginROI.html']
    _plugin_type = 'NDPluginROI'
    _default_configuration_attrs = (PluginBase._default_configuration_attrs + (
        'roi_enable', 'name_', 'bin_', 'data_type_out', 'enable_scale')
    )
    array_size = DDC(ad_group(EpicsSignalRO,
                              (('x', 'ArraySizeX_RBV'),
                               ('y', 'ArraySizeY_RBV'),
                               ('z', 'ArraySizeZ_RBV'))),
                     doc='Size of the ROI data in XYZ',
                     default_read_attrs=('x', 'y', 'z'))

    auto_size = DDC(ad_group(SignalWithRBV,
                             (('x', 'AutoSizeX'),
                              ('y', 'AutoSizeY'),
                              ('z', 'AutoSizeZ'))),
                    doc=('Automatically set SizeXYZ to the input array size '
                         'minus MinXYZ'),
                    default_read_attrs=('x', 'y', 'z'))

    bin_ = DDC(ad_group(SignalWithRBV,
                        (('x', 'BinX'),
                         ('y', 'BinY'),
                         ('z', 'BinZ'))),
               doc='Binning in XYZ',
               default_read_attrs=('x', 'y', 'z'))

    data_type_out = C(SignalWithRBV, 'DataTypeOut', string=True)
    enable_scale = C(SignalWithRBV, 'EnableScale', string=True)

    roi_enable = DDC(ad_group(SignalWithRBV,
                              (('x', 'EnableX'),
                               ('y', 'EnableY'),
                               ('z', 'EnableZ')), string=True),
                     doc=('Enable ROI calculations in the X, Y, Z dimensions. '
                          'If not enabled then the start, size, binning, and '
                          'reverse operations are disabled in the X/Y/Z '
                          'dimension, and the values from the input array '
                          'are used.'),
                     default_read_attrs=('x', 'y', 'z'))

    max_xy = DDC(ad_group(EpicsSignal,
                          (('x', 'MaxX'),
                           ('y', 'MaxY'))),
                 doc='Maximum in XY',
                 default_read_attrs=('x', 'y'))

    max_size = DDC(ad_group(EpicsSignalRO,
                            (('x', 'MaxSizeX_RBV'),
                             ('y', 'MaxSizeY_RBV'),
                             ('z', 'MaxSizeZ_RBV'))),
                   doc='Maximum size of the ROI in XYZ',
                   default_read_attrs=('x', 'y', 'z'))

    min_xyz = DDC(ad_group(SignalWithRBV,
                           (('min_x', 'MinX'),
                            ('min_y', 'MinY'),
                            ('min_z', 'MinZ'))),
                  doc='Minimum size of the ROI in XYZ',
                  default_read_attrs=('min_x', 'min_y', 'min_z'))

    name_ = C(SignalWithRBV, 'Name', doc='ROI name')
    reverse = DDC(ad_group(SignalWithRBV,
                           (('x', 'ReverseX'),
                            ('y', 'ReverseY'),
                            ('z', 'ReverseZ'))),
                  doc='Reverse ROI in the XYZ dimensions. (0=No, 1=Yes)',
                  default_read_attrs=('x', 'y', 'z'))

    scale = C(SignalWithRBV, 'Scale')
    set_xhopr = C(EpicsSignal, 'SetXHOPR')
    set_yhopr = C(EpicsSignal, 'SetYHOPR')

    size = DDC(ad_group(SignalWithRBV,
                        (('x', 'SizeX'),
                         ('y', 'SizeY'),
                         ('z', 'SizeZ'))),
               doc='Size of the ROI in XYZ',
               default_read_attrs=('x', 'y', 'z'))


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
                     doc='Array size',
                     default_read_attrs=('height', 'width', 'depth'))


    name_ = C(EpicsSignal, 'Name')
    origin_location = C(SignalWithRBV, 'OriginLocation')
    t1_max_size = DDC(ad_group(EpicsSignal,
                               (('size0', 'T1MaxSize0'),
                                ('size1', 'T1MaxSize1'),
                                ('size2', 'T1MaxSize2'))),
                      doc='Transform 1 max size',
                      default_read_attrs=('size0', 'size1', 'size2'))


    t2_max_size = DDC(ad_group(EpicsSignal,
                               (('size0', 'T2MaxSize0'),
                                ('size1', 'T2MaxSize1'),
                                ('size2', 'T2MaxSize2'))),
                      doc='Transform 2 max size',
                      default_read_attrs=('size0', 'size1', 'size2'))


    t3_max_size = DDC(ad_group(EpicsSignal,
                               (('size0', 'T3MaxSize0'),
                                ('size1', 'T3MaxSize1'),
                                ('size2', 'T3MaxSize2'))),
                      doc='Transform 3 max size',
                      default_read_attrs=('size0', 'size1', 'size2'))


    t4_max_size = DDC(ad_group(EpicsSignal,
                               (('size0', 'T4MaxSize0'),
                                ('size1', 'T4MaxSize1'),
                                ('size2', 'T4MaxSize2'))),
                      doc='Transform 4 max size',
                      default_read_attrs=('size0', 'size1', 'size2'))


    types = DDC(ad_group(EpicsSignal,
                         (('type1', 'Type1'),
                          ('type2', 'Type2'),
                          ('type3', 'Type3'),
                          ('type4', 'Type4'))),
                doc='Transform types',
                default_read_attrs=('type1', 'type2', 'type3', 'type4'))



class FilePlugin(PluginBase, GenerateDatumInterface):
    _default_suffix = ''
    _html_docs = ['NDPluginFile.html']
    _plugin_type = 'NDPluginFile'
    _default_configuration_attrs = (PluginBase._default_configuration_attrs + (
        'auto_increment',
        'auto_save',
        'file_format',
        'file_name',
        'file_path',
        'file_path_exists',
        'file_template',
        'file_write_mode',
        'full_file_name',
        'num_capture'
        ))
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
    _default_configuration_attrs = (FilePlugin._default_configuration_attrs + (
        'jpeg_quality',))

    jpeg_quality = C(SignalWithRBV, 'JPEGQuality')


class NexusPlugin(FilePlugin):
    _default_suffix = 'Nexus1:'
    _suffix_re = 'Nexus\d:'
    _html_docs = ['NDFileNexus.html']
    # _plugin_type = 'NDPluginFile'  # TODO was this ever fixed?
    _plugin_type = 'NDPluginNexus'
    _default_configuration_attrs = (FilePlugin._default_configuration_attrs + (
        'template_file_name', 'template_file_path'))

    file_template_valid = C(EpicsSignal, 'FileTemplateValid')
    template_file_name = C(SignalWithRBV, 'TemplateFileName', string=True)
    template_file_path = C(SignalWithRBV, 'TemplateFilePath', string=True)


class HDF5Plugin(FilePlugin):
    _default_suffix = 'HDF1:'
    _suffix_re = 'HDF\d:'
    _html_docs = ['NDFileHDF5.html']
    _plugin_type = 'NDFileHDF5'

    _default_configuration_attrs = (FilePlugin._default_configuration_attrs + (
        'boundary_align',
        'boundary_threshold',
        'compression',
        'data_bits_offset',
        'extra_dim_name',
        'extra_dim_size',
        'io_speed',
        'num_col_chunks',
        'num_data_bits',
        'num_extra_dims',
        'num_frames_chunks',
        'num_frames_flush',
        'num_row_chunks',
        'run_time',
        'store_attr',
        'store_perform',
        'szip_num_pixels',
        'zlevel')
    )

    boundary_align = C(SignalWithRBV, 'BoundaryAlign')
    boundary_threshold = C(SignalWithRBV, 'BoundaryThreshold')
    compression = C(SignalWithRBV, 'Compression')
    data_bits_offset = C(SignalWithRBV, 'DataBitsOffset')

    extra_dim_name = DDC(ad_group(EpicsSignalRO,
                                  (('name_x', 'ExtraDimNameX_RBV'),
                                   ('name_y', 'ExtraDimNameY_RBV'),
                                   ('name_n', 'ExtraDimNameN_RBV'))),
                         doc='Extra dimension names (XYN)',
                         default_read_attrs=('name_x', 'name_y', 'name_n'))

    extra_dim_size = DDC(ad_group(SignalWithRBV,
                                  (('size_x', 'ExtraDimSizeX'),
                                   ('size_y', 'ExtraDimSizeY'),
                                   ('size_n', 'ExtraDimSizeN'))),
                         doc='Extra dimension sizes (XYN)',
                         default_read_attrs=('size_x', 'size_y', 'size_n'))


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
        """
        A convenience method for 'priming' the plugin.

        The plugin has to 'see' one acquisition before it is ready to capture.
        This sets the array size, etc.
        """
        set_and_wait(self.enable, 1)
        sigs = OrderedDict([(self.parent.cam.array_callbacks, 1),
                            (self.parent.cam.image_mode, 'Single'),
                            (self.parent.cam.trigger_mode, 'Internal'),
                            # just in case tha acquisition time is set very long...
                            (self.parent.cam.acquire_time , 1),
                            (self.parent.cam.acquire_period, 1),
                            (self.parent.cam.acquire, 1)])

        original_vals = {sig: sig.get() for sig in sigs}

        for sig, val in sigs.items():
            ttime.sleep(0.1)  # abundance of caution
            set_and_wait(sig, val)

        ttime.sleep(2)  # wait for acquisition

        for sig, val in reversed(list(original_vals.items())):
            ttime.sleep(0.1)
            set_and_wait(sig, val)


class MagickPlugin(FilePlugin):
    _default_suffix = 'Magick1:'
    _suffix_re = 'Magick\d:'
    _html_docs = ['NDFileMagick']  # sic., no html extension
    _plugin_type = 'NDFileMagick'
    _default_configuration_attrs = (FilePlugin._default_configuration_attrs + (
        'bit_depth', 'compress_type', 'quality',))

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
    from .. import cl

    cls = plugin_from_pvname(prefix)
    if cls is not None:
        return cls

    type_rbv = prefix + 'PluginType_RBV'
    type_ = cl.caget(type_rbv, timeout=timeout)

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
