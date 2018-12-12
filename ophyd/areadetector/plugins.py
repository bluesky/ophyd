# vi: ts=4 sw=4
'''AreaDetector plugins

 `areaDetector`_ plugin abstractions

.. _areaDetector: http://cars.uchicago.edu/software/epics/areaDetector.html
'''


import functools
import logging
import numpy as np
import operator
import re
import time as ttime

from collections import OrderedDict

from .. import Component
from .base import (ADBase, ADComponent as Cpt,
                   EpicsSignalWithRBV as SignalWithRBV,
                   DDC_EpicsSignal, DDC_EpicsSignalRO, DDC_SignalWithRBV,
                   NDDerivedSignal)
from ..signal import (EpicsSignalRO, EpicsSignal, ArrayAttributeSignal)
from ..device import GenerateDatumInterface
from ..utils import enum, set_and_wait
from ..utils.errors import (PluginMisconfigurationError, DestroyedError)


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
    return cls


class PluginBase(ADBase, version=(1, 9, 1)):
    '''AreaDetector plugin base class'''
    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        if self._plugin_type is not None:
            # Misconfigured until proven otherwise - this will happen when
            # plugin_type first connects
            self._misconfigured = None
        else:
            self._misconfigured = False

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

    array_counter = Cpt(SignalWithRBV, 'ArrayCounter')
    array_rate = Cpt(EpicsSignalRO, 'ArrayRate_RBV')
    asyn_io = Cpt(EpicsSignal, 'AsynIO')

    nd_attributes_file = Cpt(EpicsSignal, 'NDAttributesFile', string=True)
    pool_alloc_buffers = Cpt(EpicsSignalRO, 'PoolAllocBuffers')
    pool_free_buffers = Cpt(EpicsSignalRO, 'PoolFreeBuffers')
    pool_max_buffers = Cpt(EpicsSignalRO, 'PoolMaxBuffers')
    pool_max_mem = Cpt(EpicsSignalRO, 'PoolMaxMem')
    pool_used_buffers = Cpt(EpicsSignalRO, 'PoolUsedBuffers')
    pool_used_mem = Cpt(EpicsSignalRO, 'PoolUsedMem')
    port_name = Cpt(EpicsSignalRO, 'PortName_RBV', string=True)

    def stage(self):
        super().stage()

        if self._misconfigured is None:
            # If plugin_type has not yet connected, ensure it has here
            self.plugin_type.wait_for_connection()
            # And for good measure, make sure the callback has been called:
            self._plugin_type_connected(connected=True)

        if self._misconfigured:
            raise PluginMisconfigurationError(
                'Plugin prefix {!r}: trying to use {!r} class (with plugin '
                'type={!r}) but the plugin reports it is of type {!r}'
                ''.format(self.prefix, self.__class__.__name__,
                          self._plugin_type, self.plugin_type.get()))

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

    asyn_pipeline_config = Component(ArrayAttributeSignal,
                                     attr='_asyn_pipeline_configuration_names')

    width = Cpt(EpicsSignalRO, 'ArraySize0_RBV')
    height = Cpt(EpicsSignalRO, 'ArraySize1_RBV')
    depth = Cpt(EpicsSignalRO, 'ArraySize2_RBV')
    array_size = DDC_EpicsSignalRO(
        ('height', 'ArraySize1_RBV'),
        ('width', 'ArraySize0_RBV'),
        ('depth', 'ArraySize2_RBV'),
        doc='The array size'
    )

    bayer_pattern = Cpt(EpicsSignalRO, 'BayerPattern_RBV')
    blocking_callbacks = Cpt(SignalWithRBV, 'BlockingCallbacks', string=True)
    color_mode = Cpt(EpicsSignalRO, 'ColorMode_RBV')
    data_type = Cpt(EpicsSignalRO, 'DataType_RBV', string=True)

    dim0_sa = Cpt(EpicsSignal, 'Dim0SA')
    dim1_sa = Cpt(EpicsSignal, 'Dim1SA')
    dim2_sa = Cpt(EpicsSignal, 'Dim2SA')
    dim_sa = DDC_EpicsSignal(
        ('dim0', 'Dim0SA'),
        ('dim1', 'Dim1SA'),
        ('dim2', 'Dim2SA'),
        doc='Dimension sub-arrays'
    )

    dimensions = Cpt(EpicsSignalRO, 'Dimensions_RBV')
    dropped_arrays = Cpt(SignalWithRBV, 'DroppedArrays')
    enable = Cpt(SignalWithRBV, 'EnableCallbacks', string=True)
    min_callback_time = Cpt(SignalWithRBV, 'MinCallbackTime')
    nd_array_address = Cpt(SignalWithRBV, 'NDArrayAddress')
    nd_array_port = Cpt(SignalWithRBV, 'NDArrayPort')
    ndimensions = Cpt(EpicsSignalRO, 'NDimensions_RBV')
    plugin_type = Cpt(EpicsSignalRO, 'PluginType_RBV', lazy=False)

    queue_free = Cpt(EpicsSignal, 'QueueFree')
    queue_free_low = Cpt(EpicsSignal, 'QueueFreeLow')
    queue_size = Cpt(EpicsSignal, 'QueueSize')
    queue_use = Cpt(EpicsSignal, 'QueueUse')
    queue_use_high = Cpt(EpicsSignal, 'QueueUseHIGH')
    queue_use_hihi = Cpt(EpicsSignal, 'QueueUseHIHI')
    time_stamp = Cpt(EpicsSignalRO, 'TimeStamp_RBV')
    unique_id = Cpt(EpicsSignalRO, 'UniqueId_RBV')

    @plugin_type.sub_meta
    def _plugin_type_connected(self, connected, **kw):
        'Connection callback on the plugin type'
        if not connected or self._plugin_type is None:
            return

        try:
            plugin_type = self.plugin_type.get()
        except DestroyedError:
            return

        self._misconfigured = not plugin_type.startswith(self._plugin_type)
        if self._misconfigured:
            logger.warning(
                'Plugin prefix %r: trying to use %r class (plugin type=%r) '
                ' but the plugin reports it is of type %r',
                self.prefix, self.__class__.__name__, self._plugin_type,
                plugin_type
            )
        else:
            logger.debug(
                'Plugin prefix %r type confirmed: %r class (plugin type=%r);'
                ' plugin reports it is of type %r',
                self.prefix, self.__class__.__name__, self._plugin_type,
                plugin_type
            )


@register_plugin
class ImagePlugin(PluginBase, version=(1, 9, 1)):
    _default_suffix = 'image1:'
    _suffix_re = r'image\d:'
    _html_docs = ['NDPluginStdArrays.html']
    _plugin_type = 'NDPluginStdArrays'

    array_data = Cpt(EpicsSignal, 'ArrayData')
    shaped_image = Cpt(NDDerivedSignal, derived_from='array_data',
                       shape=('array_size.height',
                              'array_size.width',
                              'array_size.depth'),
                       num_dimensions='ndimensions',
                       kind='omitted')

    @property
    def image(self):
        array_size = self.array_size.get()
        if array_size == (0, 0, 0):
            raise RuntimeError('Invalid image; ensure array_callbacks are on')

        if array_size[-1] == 0:
            array_size = array_size[:-1]

        pixel_count = self.array_pixels
        image = self.array_data.get(count=pixel_count)
        return np.array(image).reshape(array_size)


@register_plugin
class StatsPlugin(PluginBase, version=(1, 9, 1)):
    _default_suffix = 'Stats1:'
    _suffix_re = r'Stats\d:'
    _html_docs = ['NDPluginStats.html']
    _plugin_type = 'NDPluginStats'

    _default_configuration_attrs = (PluginBase._default_configuration_attrs + (
        'centroid_threshold', 'compute_centroid', 'compute_histogram',
        'compute_profiles', 'ts_control', 'compute_statistics', 'bgd_width',
        'hist_size', 'hist_min', 'hist_max', 'ts_num_points', 'profile_size',
        'profile_cursor')
    )

    bgd_width = Cpt(SignalWithRBV, 'BgdWidth')
    centroid_threshold = Cpt(SignalWithRBV, 'CentroidThreshold')

    centroid = DDC_EpicsSignalRO(
        ('x', 'CentroidX_RBV'),
        ('y', 'CentroidY_RBV'),
        doc='The centroid XY',
    )

    compute_centroid = Cpt(SignalWithRBV, 'ComputeCentroid', string=True)
    compute_histogram = Cpt(SignalWithRBV, 'ComputeHistogram', string=True)
    compute_profiles = Cpt(SignalWithRBV, 'ComputeProfiles', string=True)
    compute_statistics = Cpt(SignalWithRBV, 'ComputeStatistics', string=True)

    cursor = DDC_SignalWithRBV(
        ('x', 'CursorX'),
        ('y', 'CursorY'),
        doc='The cursor XY',
    )

    hist_entropy = Cpt(EpicsSignalRO, 'HistEntropy_RBV')
    hist_max = Cpt(SignalWithRBV, 'HistMax')
    hist_min = Cpt(SignalWithRBV, 'HistMin')
    hist_size = Cpt(SignalWithRBV, 'HistSize')
    histogram = Cpt(EpicsSignalRO, 'Histogram_RBV')

    max_size = DDC_EpicsSignal(
        ('x', 'MaxSizeX'),
        ('y', 'MaxSizeY'),
        doc='The maximum size in XY',
    )

    max_value = Cpt(EpicsSignalRO, 'MaxValue_RBV')
    max_xy = DDC_EpicsSignalRO(
        ('x', 'MaxX_RBV'),
        ('y', 'MaxY_RBV'),
        doc='Maximum in XY',
    )

    mean_value = Cpt(EpicsSignalRO, 'MeanValue_RBV')
    min_value = Cpt(EpicsSignalRO, 'MinValue_RBV')

    min_xy = DDC_EpicsSignalRO(
        ('x', 'MinX_RBV'),
        ('y', 'MinY_RBV'),
        doc='Minimum in XY',
    )

    net = Cpt(EpicsSignalRO, 'Net_RBV')
    profile_average = DDC_EpicsSignalRO(
        ('x', 'ProfileAverageX_RBV'),
        ('y', 'ProfileAverageY_RBV'),
        doc='Profile average in XY',
    )

    profile_centroid = DDC_EpicsSignalRO(
        ('x', 'ProfileCentroidX_RBV'),
        ('y', 'ProfileCentroidY_RBV'),
        doc='Profile centroid in XY',
    )

    profile_cursor = DDC_EpicsSignalRO(
        ('x', 'ProfileCursorX_RBV'),
        ('y', 'ProfileCursorY_RBV'),
        doc='Profile cursor in XY',
    )

    profile_size = DDC_EpicsSignalRO(
        ('x', 'ProfileSizeX_RBV'),
        ('y', 'ProfileSizeY_RBV'),
        doc='Profile size in XY',
    )

    profile_threshold = DDC_EpicsSignalRO(
        ('x', 'ProfileThresholdX_RBV'),
        ('y', 'ProfileThresholdY_RBV'),
        doc='Profile threshold in XY',
    )

    set_xhopr = Cpt(EpicsSignal, 'SetXHOPR')
    set_yhopr = Cpt(EpicsSignal, 'SetYHOPR')
    sigma_xy = Cpt(EpicsSignalRO, 'SigmaXY_RBV')
    sigma_x = Cpt(EpicsSignalRO, 'SigmaX_RBV')
    sigma_y = Cpt(EpicsSignalRO, 'SigmaY_RBV')
    sigma = Cpt(EpicsSignalRO, 'Sigma_RBV')
    ts_acquiring = Cpt(EpicsSignal, 'TSAcquiring')

    ts_centroid = DDC_EpicsSignal(
        ('x', 'TSCentroidX'),
        ('y', 'TSCentroidY'),
        doc='Time series centroid in XY',
    )

    ts_control = Cpt(EpicsSignal, 'TSControl', string=True)
    ts_current_point = Cpt(EpicsSignal, 'TSCurrentPoint')
    ts_max_value = Cpt(EpicsSignal, 'TSMaxValue')

    ts_max = DDC_EpicsSignal(
        ('x', 'TSMaxX'),
        ('y', 'TSMaxY'),
        doc='Time series maximum in XY',
    )

    ts_mean_value = Cpt(EpicsSignal, 'TSMeanValue')
    ts_min_value = Cpt(EpicsSignal, 'TSMinValue')

    ts_min = DDC_EpicsSignal(
        ('x', 'TSMinX'),
        ('y', 'TSMinY'),
        doc='Time series minimum in XY',
    )

    ts_net = Cpt(EpicsSignal, 'TSNet')
    ts_num_points = Cpt(EpicsSignal, 'TSNumPoints')
    ts_read = Cpt(EpicsSignal, 'TSRead')
    ts_sigma = Cpt(EpicsSignal, 'TSSigma')
    ts_sigma_x = Cpt(EpicsSignal, 'TSSigmaX')
    ts_sigma_xy = Cpt(EpicsSignal, 'TSSigmaXY')
    ts_sigma_y = Cpt(EpicsSignal, 'TSSigmaY')
    ts_total = Cpt(EpicsSignal, 'TSTotal')
    total = Cpt(EpicsSignalRO, 'Total_RBV')


@register_plugin
class ColorConvPlugin(PluginBase, version=(1, 9, 1)):
    _default_suffix = 'CC1:'
    _suffix_re = r'CC\d:'
    _html_docs = ['NDPluginColorConvert.html']
    _plugin_type = 'NDPluginColorConvert'
    _default_configuration_attrs = (PluginBase._default_configuration_attrs +
                                    ('color_mode_out', 'false_color'))

    color_mode_out = Cpt(SignalWithRBV, 'ColorModeOut')
    false_color = Cpt(SignalWithRBV, 'FalseColor')


@register_plugin
class ProcessPlugin(PluginBase, version=(1, 9, 1)):
    _default_suffix = 'Proc1:'
    _suffix_re = r'Proc\d:'
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
    auto_offset_scale = Cpt(EpicsSignal, 'AutoOffsetScale', string=True)
    auto_reset_filter = Cpt(SignalWithRBV, 'AutoResetFilter', string=True)
    average_seq = Cpt(EpicsSignal, 'AverageSeq')
    copy_to_filter_seq = Cpt(EpicsSignal, 'CopyToFilterSeq')
    data_type_out = Cpt(SignalWithRBV, 'DataTypeOut', string=True)
    difference_seq = Cpt(EpicsSignal, 'DifferenceSeq')
    enable_background = Cpt(SignalWithRBV, 'EnableBackground', string=True)
    enable_filter = Cpt(SignalWithRBV, 'EnableFilter', string=True)
    enable_flat_field = Cpt(SignalWithRBV, 'EnableFlatField', string=True)
    enable_high_clip = Cpt(SignalWithRBV, 'EnableHighClip', string=True)
    enable_low_clip = Cpt(SignalWithRBV, 'EnableLowClip', string=True)
    enable_offset_scale = Cpt(SignalWithRBV, 'EnableOffsetScale', string=True)

    fc = DDC_SignalWithRBV(
        ('fc1', 'FC1'),
        ('fc2', 'FC2'),
        ('fc3', 'FC3'),
        ('fc4', 'FC4'),
        doc='Filter coefficients',
    )

    foffset = Cpt(SignalWithRBV, 'FOffset')
    fscale = Cpt(SignalWithRBV, 'FScale')
    filter_callbacks = Cpt(SignalWithRBV, 'FilterCallbacks', string=True)
    filter_type = Cpt(EpicsSignal, 'FilterType', string=True)
    filter_type_seq = Cpt(EpicsSignal, 'FilterTypeSeq')
    high_clip = Cpt(SignalWithRBV, 'HighClip')
    low_clip = Cpt(SignalWithRBV, 'LowClip')
    num_filter = Cpt(SignalWithRBV, 'NumFilter')
    num_filter_recip = Cpt(EpicsSignal, 'NumFilterRecip')
    num_filtered = Cpt(EpicsSignalRO, 'NumFiltered_RBV')

    oc = DDC_SignalWithRBV(
        ('oc1', 'OC1'),
        ('oc2', 'OC2'),
        ('oc3', 'OC3'),
        ('oc4', 'OC4'),
        doc='Output coefficients',
    )

    o_offset = Cpt(SignalWithRBV, 'OOffset')
    o_scale = Cpt(SignalWithRBV, 'OScale')
    offset = Cpt(SignalWithRBV, 'Offset')

    rc = DDC_SignalWithRBV(
        ('rc1', 'RC1'),
        ('rc2', 'RC2'),
        doc='Filter coefficients',
    )

    roffset = Cpt(SignalWithRBV, 'ROffset')
    recursive_ave_diff_seq = Cpt(EpicsSignal, 'RecursiveAveDiffSeq')
    recursive_ave_seq = Cpt(EpicsSignal, 'RecursiveAveSeq')
    reset_filter = Cpt(SignalWithRBV, 'ResetFilter')
    save_background = Cpt(SignalWithRBV, 'SaveBackground')
    save_flat_field = Cpt(SignalWithRBV, 'SaveFlatField')
    scale = Cpt(SignalWithRBV, 'Scale')
    scale_flat_field = Cpt(SignalWithRBV, 'ScaleFlatField')
    sum_seq = Cpt(EpicsSignal, 'SumSeq')
    valid_background = Cpt(EpicsSignalRO, 'ValidBackground_RBV', string=True)
    valid_flat_field = Cpt(EpicsSignalRO, 'ValidFlatField_RBV', string=True)


class Overlay(ADBase, version=(1, 9, 1)):
    _html_docs = ['NDPluginOverlay.html']

    blue = Cpt(SignalWithRBV, 'Blue')
    draw_mode = Cpt(SignalWithRBV, 'DrawMode')
    green = Cpt(SignalWithRBV, 'Green')
    max_size_x = Cpt(EpicsSignal, 'MaxSizeX')
    max_size_y = Cpt(EpicsSignal, 'MaxSizeY')
    overlay_portname = Cpt(SignalWithRBV, 'Name')

    position_x = Cpt(SignalWithRBV, 'PositionX')
    position_y = Cpt(SignalWithRBV, 'PositionY')

    position_xlink = Cpt(EpicsSignal, 'PositionXLink')
    position_ylink = Cpt(EpicsSignal, 'PositionYLink')

    red = Cpt(SignalWithRBV, 'Red')
    set_xhopr = Cpt(EpicsSignal, 'SetXHOPR')
    set_yhopr = Cpt(EpicsSignal, 'SetYHOPR')
    shape = Cpt(SignalWithRBV, 'Shape')

    size_x = Cpt(SignalWithRBV, 'SizeX')
    size_y = Cpt(SignalWithRBV, 'SizeY')

    size_xlink = Cpt(EpicsSignal, 'SizeXLink')
    size_ylink = Cpt(EpicsSignal, 'SizeYLink')
    use = Cpt(SignalWithRBV, 'Use')


@register_plugin
class OverlayPlugin(PluginBase, version=(1, 9, 1)):
    '''Plugin which adds graphics overlays to an NDArray image

    Keyword arguments are passed to the base class, PluginBase

    Parameters
    ----------
    prefix : str
        The areaDetector plugin prefix
    '''
    _default_suffix = 'Over1:'
    _suffix_re = r'Over\d:'
    _html_docs = ['NDPluginOverlay.html']
    _plugin_type = 'NDPluginOverlay'
    _default_configuration_attrs = (PluginBase._default_configuration_attrs + (
        'overlay_1', 'overlay_2', 'overlay_3', 'overlay_4', 'overlay_5',
        'overlay_6', 'overlay_7', 'overlay_8')
    )
    max_size = DDC_EpicsSignalRO(
        ('x', 'MaxSizeX_RBV'),
        ('y', 'MaxSizeY_RBV'),
        doc='The maximum size in XY',
    )

    overlay_1 = Cpt(Overlay, '1:')
    overlay_2 = Cpt(Overlay, '2:')
    overlay_3 = Cpt(Overlay, '3:')
    overlay_4 = Cpt(Overlay, '4:')
    overlay_5 = Cpt(Overlay, '5:')
    overlay_6 = Cpt(Overlay, '6:')
    overlay_7 = Cpt(Overlay, '7:')
    overlay_8 = Cpt(Overlay, '8:')


@register_plugin
class ROIPlugin(PluginBase, version=(1, 9, 1)):

    _default_suffix = 'ROI1:'
    _suffix_re = r'ROI\d:'
    _html_docs = ['NDPluginROI.html']
    _plugin_type = 'NDPluginROI'
    _default_configuration_attrs = (PluginBase._default_configuration_attrs + (
        'roi_enable', 'name_', 'bin_', 'data_type_out', 'enable_scale')
    )
    _default_read_attrs = ('enable', 'min_xyz.min_x', 'size.x',
                           'min_xyz.min_y', 'size.y', 'min_xyz.min_z',
                           'size.z')
    array_size = DDC_EpicsSignalRO(
        ('x', 'ArraySizeX_RBV'),
        ('y', 'ArraySizeY_RBV'),
        ('z', 'ArraySizeZ_RBV'),
        doc='Size of the ROI data in XYZ',
    )

    auto_size = DDC_SignalWithRBV(
        ('x', 'AutoSizeX'),
        ('y', 'AutoSizeY'),
        ('z', 'AutoSizeZ'),
        doc='Automatically set SizeXYZ to the input array size minus MinXYZ',
    )

    bin_ = DDC_SignalWithRBV(
        ('x', 'BinX'),
        ('y', 'BinY'),
        ('z', 'BinZ'),
        doc='Binning in XYZ',
    )

    data_type_out = Cpt(SignalWithRBV, 'DataTypeOut', string=True)
    enable_scale = Cpt(SignalWithRBV, 'EnableScale', string=True)

    roi_enable = DDC_SignalWithRBV(
        ('x', 'EnableX'),
        ('y', 'EnableY'),
        ('z', 'EnableZ'),
        string=True,
        doc=('Enable ROI calculations in the X, Y, Z dimensions. If not '
             'enabled then the start, size, binning, and reverse operations '
             'are disabled in the X/Y/Z dimension, and the values from the '
             'input array are used.')
    )

    max_xy = DDC_EpicsSignal(
        ('x', 'MaxX'),
        ('y', 'MaxY'),
        doc='Maximum in XY',
    )

    max_size = DDC_EpicsSignalRO(
        ('x', 'MaxSizeX_RBV'),
        ('y', 'MaxSizeY_RBV'),
        ('z', 'MaxSizeZ_RBV'),
        doc='Maximum size of the ROI in XYZ',
    )

    min_xyz = DDC_SignalWithRBV(
        ('min_x', 'MinX'),
        ('min_y', 'MinY'),
        ('min_z', 'MinZ'),
        doc='Minimum size of the ROI in XYZ',
    )

    def set(self, region):
        ''' This functions allows for the ROI regions to be set.

        This function takes in an ROI_number, and a dictionary of tuples and
        sets the ROI region.

        PARAMETERS
        ----------
        region: dictionary.
            A dictionary defining the region to be set, which has the
            structure:
            ``{'x': [min, size], 'y': [min, size], 'z': [min, size]}``. Any of
            the keywords can be omitted, and they will be ignored.
        '''
        if region is not None:
            status = []
            for direction, value in region.items():
                status.append(getattr(
                    self, 'min_xyz.min_{}'.format(direction)).set(value[0]))
                status.append(
                    getattr(self, 'size.{}'.format(direction)).set(value[1]))

        return functools.reduce(operator.and_, status)

    name_ = Cpt(SignalWithRBV, 'Name', doc='ROI name')
    reverse = DDC_SignalWithRBV(
        ('x', 'ReverseX'),
        ('y', 'ReverseY'),
        ('z', 'ReverseZ'),
        doc='Reverse ROI in the XYZ dimensions. (0=No, 1=Yes)',
    )

    scale = Cpt(SignalWithRBV, 'Scale')
    set_xhopr = Cpt(EpicsSignal, 'SetXHOPR')
    set_yhopr = Cpt(EpicsSignal, 'SetYHOPR')

    size = DDC_SignalWithRBV(
        ('x', 'SizeX'),
        ('y', 'SizeY'),
        ('z', 'SizeZ'),
        doc='Size of the ROI in XYZ',
    )


@register_plugin
class TransformPlugin(PluginBase, version=(1, 9, 1)):
    _default_suffix = 'Trans1:'
    _suffix_re = r'Trans\d:'
    _html_docs = ['NDPluginTransform.html']
    _plugin_type = 'NDPluginTransform'

    width = Cpt(SignalWithRBV, 'ArraySize0')
    height = Cpt(SignalWithRBV, 'ArraySize1')
    depth = Cpt(SignalWithRBV, 'ArraySize2')
    array_size = DDC_SignalWithRBV(
        ('height', 'ArraySize1'),
        ('width', 'ArraySize0'),
        ('depth', 'ArraySize2'),
        doc='Array size',
    )

    name_ = Cpt(EpicsSignal, 'Name')
    origin_location = Cpt(SignalWithRBV, 'OriginLocation')
    t1_max_size = DDC_EpicsSignal(
        ('size0', 'T1MaxSize0'),
        ('size1', 'T1MaxSize1'),
        ('size2', 'T1MaxSize2'),
        doc='Transform 1 max size',
    )

    t2_max_size = DDC_EpicsSignal(
        ('size0', 'T2MaxSize0'),
        ('size1', 'T2MaxSize1'),
        ('size2', 'T2MaxSize2'),
        doc='Transform 2 max size',
    )

    t3_max_size = DDC_EpicsSignal(
        ('size0', 'T3MaxSize0'),
        ('size1', 'T3MaxSize1'),
        ('size2', 'T3MaxSize2'),
        doc='Transform 3 max size',
    )

    t4_max_size = DDC_EpicsSignal(
        ('size0', 'T4MaxSize0'),
        ('size1', 'T4MaxSize1'),
        ('size2', 'T4MaxSize2'),
        doc='Transform 4 max size',
    )

    types = DDC_EpicsSignal(
        ('type1', 'Type1'),
        ('type2', 'Type2'),
        ('type3', 'Type3'),
        ('type4', 'Type4'),
        doc='Transform types',
    )


class FilePlugin(PluginBase, GenerateDatumInterface, version=(1, 9, 1)):
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

    auto_increment = Cpt(SignalWithRBV, 'AutoIncrement')
    auto_save = Cpt(SignalWithRBV, 'AutoSave')
    capture = Cpt(SignalWithRBV, 'Capture')
    delete_driver_file = Cpt(SignalWithRBV, 'DeleteDriverFile')
    file_format = Cpt(SignalWithRBV, 'FileFormat')
    file_name = Cpt(SignalWithRBV, 'FileName', string=True)
    file_number = Cpt(SignalWithRBV, 'FileNumber')
    file_number_sync = Cpt(EpicsSignal, 'FileNumber_Sync')
    file_number_write = Cpt(EpicsSignal, 'FileNumber_write')
    file_path = Cpt(SignalWithRBV, 'FilePath', string=True)
    file_path_exists = Cpt(EpicsSignalRO, 'FilePathExists_RBV')
    file_template = Cpt(SignalWithRBV, 'FileTemplate', string=True)
    file_write_mode = Cpt(SignalWithRBV, 'FileWriteMode')
    full_file_name = Cpt(EpicsSignalRO, 'FullFileName_RBV', string=True)
    num_capture = Cpt(SignalWithRBV, 'NumCapture')
    num_captured = Cpt(EpicsSignalRO, 'NumCaptured_RBV')
    read_file = Cpt(SignalWithRBV, 'ReadFile')
    write_file = Cpt(SignalWithRBV, 'WriteFile')
    write_message = Cpt(EpicsSignal, 'WriteMessage', string=True)
    write_status = Cpt(EpicsSignal, 'WriteStatus')


@register_plugin
class NetCDFPlugin(FilePlugin, version=(1, 9, 1)):
    _default_suffix = 'netCDF1:'
    _suffix_re = r'netCDF\d:'
    _html_docs = ['NDFileNetCDF.html']
    _plugin_type = 'NDFileNetCDF'


@register_plugin
class TIFFPlugin(FilePlugin, version=(1, 9, 1)):
    _default_suffix = 'TIFF1:'
    _suffix_re = r'TIFF\d:'
    _html_docs = ['NDFileTIFF.html']
    _plugin_type = 'NDFileTIFF'


@register_plugin
class JPEGPlugin(FilePlugin, version=(1, 9, 1)):
    _default_suffix = 'JPEG1:'
    _suffix_re = r'JPEG\d:'
    _html_docs = ['NDFileJPEG.html']
    _plugin_type = 'NDFileJPEG'
    _default_configuration_attrs = (FilePlugin._default_configuration_attrs + (
        'jpeg_quality',))

    jpeg_quality = Cpt(SignalWithRBV, 'JPEGQuality')


@register_plugin
class NexusPlugin(FilePlugin, version=(1, 9, 1)):
    _default_suffix = 'Nexus1:'
    _suffix_re = r'Nexus\d:'
    _html_docs = ['NDFileNexus.html']
    # _plugin_type = 'NDPluginFile'  # TODO was this ever fixed?
    _plugin_type = 'NDPluginNexus'
    _default_configuration_attrs = (FilePlugin._default_configuration_attrs + (
        'template_file_name', 'template_file_path'))

    file_template_valid = Cpt(EpicsSignal, 'FileTemplateValid')
    template_file_name = Cpt(SignalWithRBV, 'TemplateFileName', string=True)
    template_file_path = Cpt(SignalWithRBV, 'TemplateFilePath', string=True)


@register_plugin
class HDF5Plugin(FilePlugin, version=(1, 9, 1)):
    _default_suffix = 'HDF1:'
    _suffix_re = r'HDF\d:'
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

    boundary_align = Cpt(SignalWithRBV, 'BoundaryAlign')
    boundary_threshold = Cpt(SignalWithRBV, 'BoundaryThreshold')
    compression = Cpt(SignalWithRBV, 'Compression')
    data_bits_offset = Cpt(SignalWithRBV, 'DataBitsOffset')

    extra_dim_name = DDC_EpicsSignalRO(
        ('name_x', 'ExtraDimNameX_RBV'),
        ('name_y', 'ExtraDimNameY_RBV'),
        ('name_n', 'ExtraDimNameN_RBV'),
        doc='Extra dimension names (XYN)',
    )

    extra_dim_size = DDC_SignalWithRBV(
        ('size_x', 'ExtraDimSizeX'),
        ('size_y', 'ExtraDimSizeY'),
        ('size_n', 'ExtraDimSizeN'),
        doc='Extra dimension sizes (XYN)',
    )

    io_speed = Cpt(EpicsSignal, 'IOSpeed')
    num_col_chunks = Cpt(SignalWithRBV, 'NumColChunks')
    num_data_bits = Cpt(SignalWithRBV, 'NumDataBits')
    num_extra_dims = Cpt(SignalWithRBV, 'NumExtraDims')
    num_frames_chunks = Cpt(SignalWithRBV, 'NumFramesChunks')
    num_frames_flush = Cpt(SignalWithRBV, 'NumFramesFlush')
    num_row_chunks = Cpt(SignalWithRBV, 'NumRowChunks')
    run_time = Cpt(EpicsSignal, 'RunTime')
    szip_num_pixels = Cpt(SignalWithRBV, 'SZipNumPixels')
    store_attr = Cpt(SignalWithRBV, 'StoreAttr')
    store_perform = Cpt(SignalWithRBV, 'StorePerform')
    zlevel = Cpt(SignalWithRBV, 'ZLevel')

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
                            (self.parent.cam.acquire_time, 1),
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


@register_plugin
class MagickPlugin(FilePlugin, version=(1, 9, 1)):
    _default_suffix = 'Magick1:'
    _suffix_re = r'Magick\d:'
    _html_docs = ['NDFileMagick']  # sic., no html extension
    _plugin_type = 'NDFileMagick'
    _default_configuration_attrs = (FilePlugin._default_configuration_attrs + (
        'bit_depth', 'compress_type', 'quality',))

    bit_depth = Cpt(SignalWithRBV, 'BitDepth')
    compress_type = Cpt(SignalWithRBV, 'CompressType')
    quality = Cpt(SignalWithRBV, 'Quality')


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
