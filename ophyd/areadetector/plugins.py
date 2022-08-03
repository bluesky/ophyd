# vi: ts=4 sw=4
"""AreaDetector plugins

 `areaDetector`_ plugin abstractions

.. _areaDetector: http://cars.uchicago.edu/software/epics/areaDetector.html
"""
# This module contains:
# - Classes like `StatsPlugin` that are designed to be counterparts to Area
#   Detector version 1.9.1, which was what ophyd was originally written
#   against.
# - Classes like `StatsPlugin_V{X}{Y}` that are design to be counterparts to
#   AreaDetector verion X.Y.
#
# The module was partly auto-generated and then hand-edited. The generation
# code is not included in the repo, as it was considered a one-off productivity
# enhancement for bootstrapping all the versions of Area Detector to date.
# Updates should be made either by hand or by producing new auto-generation
# code to suit.


import functools
import logging
import operator
import re
import time as ttime
from collections import OrderedDict

import numpy as np

from ..device import Component, Device
from ..device import FormattedComponent as FCpt
from ..device import GenerateDatumInterface
from ..signal import ArrayAttributeSignal, EpicsSignal, EpicsSignalRO
from ..utils import enum
from ..utils.errors import DestroyedError, PluginMisconfigurationError, UnprimedPlugin
from .base import ADBase
from .base import ADComponent as Cpt
from .base import DDC_EpicsSignal, DDC_EpicsSignalRO, DDC_SignalWithRBV
from .base import EpicsSignalWithRBV as SignalWithRBV
from .base import NDDerivedSignal
from .paths import EpicsPathSignal

logger = logging.getLogger(__name__)

__all__ = [
    "AttrPlotPlugin",
    "AttributeNPlugin",
    "AttributePlugin",
    "CircularBuffPlugin",
    "CodecPlugin",
    "ColorConvPlugin",
    "FFTPlugin",
    "FilePlugin",
    "GatherNPlugin",
    "GatherPlugin",
    "HDF5Plugin",
    "ImagePlugin",
    "JPEGPlugin",
    "KafkaPlugin",
    "MagickPlugin",
    "NetCDFPlugin",
    "NexusPlugin",
    "Overlay",
    "OverlayPlugin",
    "PluginBase",
    "FileBase",
    "PosPlugin",
    "ProcessPlugin",
    "PvaPlugin",
    "ROIPlugin",
    "ROIStatNPlugin",
    "ROIStatPlugin",
    "ScatterPlugin",
    "StatsPlugin",
    "TIFFPlugin",
    "TimeSeriesNPlugin",
    "TimeSeriesPlugin",
    "TransformPlugin",
    "get_areadetector_plugin",
    "get_areadetector_plugin_class",
    "plugin_from_pvname",
    "register_plugin",
]


_plugin_class = {}


def register_plugin(cls):
    """Register a plugin"""
    global _plugin_class

    _plugin_class[cls._plugin_type] = cls
    return cls


class PluginBase(ADBase, version=(1, 9, 1), version_type="ADCore"):
    """AreaDetector plugin base class"""

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        if self._plugin_type is not None:
            # Misconfigured until proven otherwise - this will happen when
            # plugin_type first connects
            self._misconfigured = None
        else:
            self._misconfigured = False

        self.enable_on_stage()
        self.stage_sigs.move_to_end("enable", last=False)
        self.ensure_blocking()
        if self.parent is not None and hasattr(self.parent, "cam"):
            self.stage_sigs.update(
                [
                    ("parent.cam.array_callbacks", 1),
                ]
            )

    _html_docs = ["pluginDoc.html"]
    _plugin_type = None
    _suffix_re = None

    array_counter = Cpt(SignalWithRBV, "ArrayCounter")
    array_rate = Cpt(EpicsSignalRO, "ArrayRate_RBV")
    asyn_io = Cpt(EpicsSignal, "AsynIO")

    nd_attributes_file = Cpt(EpicsSignal, "NDAttributesFile", string=True)
    pool_alloc_buffers = Cpt(EpicsSignalRO, "PoolAllocBuffers")
    pool_free_buffers = Cpt(EpicsSignalRO, "PoolFreeBuffers")
    pool_max_buffers = Cpt(EpicsSignalRO, "PoolMaxBuffers")
    pool_max_mem = Cpt(EpicsSignalRO, "PoolMaxMem")
    pool_used_buffers = Cpt(EpicsSignalRO, "PoolUsedBuffers")
    pool_used_mem = Cpt(EpicsSignalRO, "PoolUsedMem")
    port_name = Cpt(EpicsSignalRO, "PortName_RBV", string=True, kind="config")

    def stage(self):
        super().stage()

        if self._misconfigured is None:
            # If plugin_type has not yet connected, ensure it has here
            self.plugin_type.wait_for_connection()
            # And for good measure, make sure the callback has been called:
            self._plugin_type_connected(connected=True)

        if self._misconfigured:
            raise PluginMisconfigurationError(
                "Plugin prefix {!r}: trying to use {!r} class (with plugin "
                "type={!r}) but the plugin reports it is of type {!r}"
                "".format(
                    self.prefix,
                    self.__class__.__name__,
                    self._plugin_type,
                    self.plugin_type.get(),
                )
            )

    def enable_on_stage(self):
        """
        when the plugin is staged, ensure that it is enabled.

        a convenience method for adding ('enable', 1) to stage_sigs
        """
        self.stage_sigs["enable"] = 1

    def disable_on_stage(self):
        """
        when the plugin is staged, ensure that it is disabled.

        a convenience method for adding ```('enable', 0)`` to stage_sigs
        """
        self.stage_sigs["enable"] = 0

    def ensure_blocking(self):
        """
        Ensure that if plugin is enabled after staging, callbacks block.

        a convenience method for adding ```('blocking_callbacks', 1)`` to
        stage_sigs
        """
        self.stage_sigs["blocking_callbacks"] = "Yes"

    def ensure_nonblocking(self):
        """
        Ensure that if plugin is enabled after staging, callbacks don't block.

        a convenience method for adding ```('blocking_callbacks', 0)`` to
        stage_sigs
        """
        self.stage_sigs["blocking_callbacks"] = "No"

    @property
    def array_pixels(self):
        """The total number of pixels, calculated from array_size"""

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
        """The PluginBase object that is the asyn source for this plugin."""
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
        if hasattr(parent, "_asyn_pipeline"):
            return parent._asyn_pipeline + (self,)
        return (parent, self)

    @property
    def _asyn_pipeline_configuration_names(self):
        return [_.configuration_names.name for _ in self._asyn_pipeline]

    asyn_pipeline_config = Component(
        ArrayAttributeSignal, attr="_asyn_pipeline_configuration_names", kind="config"
    )

    width = Cpt(EpicsSignalRO, "ArraySize0_RBV")
    height = Cpt(EpicsSignalRO, "ArraySize1_RBV")
    depth = Cpt(EpicsSignalRO, "ArraySize2_RBV")
    array_size = DDC_EpicsSignalRO(
        ("depth", "ArraySize2_RBV"),
        ("height", "ArraySize1_RBV"),
        ("width", "ArraySize0_RBV"),
        doc="The array size",
    )

    bayer_pattern = Cpt(EpicsSignalRO, "BayerPattern_RBV")
    blocking_callbacks = Cpt(
        SignalWithRBV, "BlockingCallbacks", string=True, kind="config"
    )
    color_mode = Cpt(EpicsSignalRO, "ColorMode_RBV")
    data_type = Cpt(EpicsSignalRO, "DataType_RBV", string=True)

    dim0_sa = Cpt(EpicsSignal, "Dim0SA")
    dim1_sa = Cpt(EpicsSignal, "Dim1SA")
    dim2_sa = Cpt(EpicsSignal, "Dim2SA")
    dim_sa = DDC_EpicsSignal(
        ("dim0", "Dim0SA"),
        ("dim1", "Dim1SA"),
        ("dim2", "Dim2SA"),
        doc="Dimension sub-arrays",
    )

    dimensions = Cpt(EpicsSignalRO, "Dimensions_RBV")
    dropped_arrays = Cpt(SignalWithRBV, "DroppedArrays")
    enable = Cpt(SignalWithRBV, "EnableCallbacks", string=True, kind="config")
    min_callback_time = Cpt(SignalWithRBV, "MinCallbackTime")
    nd_array_address = Cpt(SignalWithRBV, "NDArrayAddress")
    nd_array_port = Cpt(SignalWithRBV, "NDArrayPort", kind="config")
    ndimensions = Cpt(EpicsSignalRO, "NDimensions_RBV")
    plugin_type = Cpt(EpicsSignalRO, "PluginType_RBV", lazy=False, kind="config")

    queue_free = Cpt(EpicsSignal, "QueueFree")
    queue_free_low = Cpt(EpicsSignal, "QueueFreeLow")
    queue_size = Cpt(EpicsSignal, "QueueSize")
    queue_use = Cpt(EpicsSignal, "QueueUse")
    queue_use_high = Cpt(EpicsSignal, "QueueUseHIGH")
    queue_use_hihi = Cpt(EpicsSignal, "QueueUseHIHI")
    time_stamp = Cpt(EpicsSignalRO, "TimeStamp_RBV")
    unique_id = Cpt(EpicsSignalRO, "UniqueId_RBV")

    @plugin_type.sub_meta
    def _plugin_type_connected(self, connected, **kw):
        "Connection callback on the plugin type"
        if not connected or self._plugin_type is None:
            return

        try:
            plugin_type = self.plugin_type.get()
        except DestroyedError:
            return

        self._misconfigured = not plugin_type.startswith(self._plugin_type)
        if self._misconfigured:
            logger.warning(
                "Plugin prefix %r: trying to use %r class (plugin type=%r) "
                " but the plugin reports it is of type %r",
                self.prefix,
                self.__class__.__name__,
                self._plugin_type,
                plugin_type,
            )
        else:
            logger.debug(
                "Plugin prefix %r type confirmed: %r class (plugin type=%r);"
                " plugin reports it is of type %r",
                self.prefix,
                self.__class__.__name__,
                self._plugin_type,
                plugin_type,
            )


@register_plugin
class ImagePlugin(PluginBase, version=(1, 9, 1), version_type="ADCore"):
    _default_suffix = "image1:"
    _suffix_re = r"image\d:"
    _html_docs = ["NDPluginStdArrays.html"]
    _plugin_type = "NDPluginStdArrays"

    array_data = Cpt(EpicsSignal, "ArrayData")
    shaped_image = Cpt(
        NDDerivedSignal,
        derived_from="array_data",
        shape=("array_size.depth", "array_size.height", "array_size.width"),
        num_dimensions="ndimensions",
        kind="omitted",
    )

    @property
    def image(self):
        array_size = self.array_size.get()
        if array_size == (0, 0, 0):
            raise RuntimeError("Invalid image; ensure array_callbacks are on")

        if array_size[0] == 0:
            array_size = array_size[1:]

        pixel_count = self.array_pixels
        image = self.array_data.get(count=pixel_count)
        return np.array(image).reshape(array_size)


@register_plugin
class StatsPlugin(PluginBase, version=(1, 9, 1), version_type="ADCore"):
    _default_suffix = "Stats1:"
    _suffix_re = r"Stats\d:"
    _html_docs = ["NDPluginStats.html"]
    _plugin_type = "NDPluginStats"

    bgd_width = Cpt(SignalWithRBV, "BgdWidth", kind="config")
    centroid_threshold = Cpt(SignalWithRBV, "CentroidThreshold", kind="config")

    centroid = DDC_EpicsSignalRO(
        ("x", "CentroidX_RBV"),
        ("y", "CentroidY_RBV"),
        doc="The centroid XY",
    )

    compute_centroid = Cpt(SignalWithRBV, "ComputeCentroid", string=True, kind="config")
    compute_histogram = Cpt(
        SignalWithRBV, "ComputeHistogram", string=True, kind="config"
    )
    compute_profiles = Cpt(SignalWithRBV, "ComputeProfiles", string=True, kind="config")
    compute_statistics = Cpt(
        SignalWithRBV, "ComputeStatistics", string=True, kind="config"
    )

    cursor = DDC_SignalWithRBV(
        ("x", "CursorX"),
        ("y", "CursorY"),
        doc="The cursor XY",
    )

    hist_entropy = Cpt(EpicsSignalRO, "HistEntropy_RBV", kind="config")
    hist_max = Cpt(SignalWithRBV, "HistMax", kind="config")
    hist_min = Cpt(SignalWithRBV, "HistMin", kind="config")
    hist_size = Cpt(SignalWithRBV, "HistSize")
    histogram = Cpt(EpicsSignalRO, "Histogram_RBV")

    max_size = DDC_EpicsSignal(
        ("x", "MaxSizeX"),
        ("y", "MaxSizeY"),
        doc="The maximum size in XY",
    )

    max_value = Cpt(EpicsSignalRO, "MaxValue_RBV")
    max_xy = DDC_EpicsSignalRO(
        ("x", "MaxX_RBV"),
        ("y", "MaxY_RBV"),
        doc="Maximum in XY",
    )

    mean_value = Cpt(EpicsSignalRO, "MeanValue_RBV")
    min_value = Cpt(EpicsSignalRO, "MinValue_RBV")

    min_xy = DDC_EpicsSignalRO(
        ("x", "MinX_RBV"),
        ("y", "MinY_RBV"),
        doc="Minimum in XY",
    )

    net = Cpt(EpicsSignalRO, "Net_RBV")
    profile_average = DDC_EpicsSignalRO(
        ("x", "ProfileAverageX_RBV"),
        ("y", "ProfileAverageY_RBV"),
        doc="Profile average in XY",
    )

    profile_centroid = DDC_EpicsSignalRO(
        ("x", "ProfileCentroidX_RBV"),
        ("y", "ProfileCentroidY_RBV"),
        doc="Profile centroid in XY",
    )

    profile_cursor = DDC_EpicsSignalRO(
        ("x", "ProfileCursorX_RBV"),
        ("y", "ProfileCursorY_RBV"),
        doc="Profile cursor in XY",
        kind="config",
    )

    profile_size = DDC_EpicsSignalRO(
        ("x", "ProfileSizeX_RBV"),
        ("y", "ProfileSizeY_RBV"),
        doc="Profile size in XY",
        kind="config",
    )

    profile_threshold = DDC_EpicsSignalRO(
        ("x", "ProfileThresholdX_RBV"),
        ("y", "ProfileThresholdY_RBV"),
        doc="Profile threshold in XY",
    )

    set_xhopr = Cpt(EpicsSignal, "SetXHOPR")
    set_yhopr = Cpt(EpicsSignal, "SetYHOPR")
    sigma_xy = Cpt(EpicsSignalRO, "SigmaXY_RBV")
    sigma_x = Cpt(EpicsSignalRO, "SigmaX_RBV")
    sigma_y = Cpt(EpicsSignalRO, "SigmaY_RBV")
    sigma = Cpt(EpicsSignalRO, "Sigma_RBV")
    ts_acquiring = Cpt(EpicsSignal, "TSAcquiring")

    ts_centroid = DDC_EpicsSignal(
        ("x", "TSCentroidX"),
        ("y", "TSCentroidY"),
        doc="Time series centroid in XY",
    )

    ts_control = Cpt(EpicsSignal, "TSControl", string=True, kind="config")
    ts_current_point = Cpt(EpicsSignal, "TSCurrentPoint")
    ts_max_value = Cpt(EpicsSignal, "TSMaxValue")

    ts_max = DDC_EpicsSignal(
        ("x", "TSMaxX"),
        ("y", "TSMaxY"),
        doc="Time series maximum in XY",
    )

    ts_mean_value = Cpt(EpicsSignal, "TSMeanValue")
    ts_min_value = Cpt(EpicsSignal, "TSMinValue")

    ts_min = DDC_EpicsSignal(
        ("x", "TSMinX"),
        ("y", "TSMinY"),
        doc="Time series minimum in XY",
    )

    ts_net = Cpt(EpicsSignal, "TSNet")
    ts_num_points = Cpt(EpicsSignal, "TSNumPoints", kind="config")
    ts_read = Cpt(EpicsSignal, "TSRead")
    ts_sigma = Cpt(EpicsSignal, "TSSigma")
    ts_sigma_x = Cpt(EpicsSignal, "TSSigmaX")
    ts_sigma_xy = Cpt(EpicsSignal, "TSSigmaXY")
    ts_sigma_y = Cpt(EpicsSignal, "TSSigmaY")
    ts_total = Cpt(EpicsSignal, "TSTotal")
    total = Cpt(EpicsSignalRO, "Total_RBV")


@register_plugin
class ColorConvPlugin(PluginBase, version=(1, 9, 1), version_type="ADCore"):
    _default_suffix = "CC1:"
    _suffix_re = r"CC\d:"
    _html_docs = ["NDPluginColorConvert.html"]
    _plugin_type = "NDPluginColorConvert"

    color_mode_out = Cpt(SignalWithRBV, "ColorModeOut", kind="config")
    false_color = Cpt(SignalWithRBV, "FalseColor", kind="config")


@register_plugin
class ProcessPlugin(PluginBase, version=(1, 9, 1), version_type="ADCore"):
    _default_suffix = "Proc1:"
    _suffix_re = r"Proc\d:"
    _html_docs = ["NDPluginProcess.html"]
    _plugin_type = "NDPluginProcess"

    auto_offset_scale = Cpt(EpicsSignal, "AutoOffsetScale", string=True, kind="config")
    auto_reset_filter = Cpt(
        SignalWithRBV, "AutoResetFilter", string=True, kind="config"
    )
    average_seq = Cpt(EpicsSignal, "AverageSeq", kind="config")
    copy_to_filter_seq = Cpt(EpicsSignal, "CopyToFilterSeq", kind="config")
    data_type_out = Cpt(SignalWithRBV, "DataTypeOut", string=True, kind="config")
    difference_seq = Cpt(EpicsSignal, "DifferenceSeq", kind="config")
    enable_background = Cpt(
        SignalWithRBV, "EnableBackground", string=True, kind="config"
    )
    enable_filter = Cpt(SignalWithRBV, "EnableFilter", string=True, kind="config")
    enable_flat_field = Cpt(
        SignalWithRBV, "EnableFlatField", string=True, kind="config"
    )
    enable_high_clip = Cpt(SignalWithRBV, "EnableHighClip", string=True, kind="config")
    enable_low_clip = Cpt(SignalWithRBV, "EnableLowClip", string=True, kind="config")
    enable_offset_scale = Cpt(
        SignalWithRBV, "EnableOffsetScale", string=True, kind="config"
    )

    fc = DDC_SignalWithRBV(
        ("fc1", "FC1"),
        ("fc2", "FC2"),
        ("fc3", "FC3"),
        ("fc4", "FC4"),
        doc="Filter coefficients",
        kind="config",
    )

    foffset = Cpt(SignalWithRBV, "FOffset", kind="config")
    fscale = Cpt(SignalWithRBV, "FScale", kind="config")
    filter_callbacks = Cpt(SignalWithRBV, "FilterCallbacks", string=True, kind="config")
    filter_type = Cpt(EpicsSignal, "FilterType", string=True, kind="config")
    filter_type_seq = Cpt(EpicsSignal, "FilterTypeSeq", kind="config")
    high_clip = Cpt(SignalWithRBV, "HighClip", kind="config")
    low_clip = Cpt(SignalWithRBV, "LowClip", kind="config")
    num_filter = Cpt(SignalWithRBV, "NumFilter", kind="config")
    num_filter_recip = Cpt(EpicsSignal, "NumFilterRecip", kind="config")
    num_filtered = Cpt(EpicsSignalRO, "NumFiltered_RBV", kind="config")

    oc = DDC_SignalWithRBV(
        ("oc1", "OC1"),
        ("oc2", "OC2"),
        ("oc3", "OC3"),
        ("oc4", "OC4"),
        doc="Output coefficients",
        kind="config",
    )

    o_offset = Cpt(SignalWithRBV, "OOffset", kind="config")
    o_scale = Cpt(SignalWithRBV, "OScale", kind="config")
    offset = Cpt(SignalWithRBV, "Offset", kind="config")

    rc = DDC_SignalWithRBV(
        ("rc1", "RC1"),
        ("rc2", "RC2"),
        doc="Filter coefficients",
        kind="config",
    )

    roffset = Cpt(SignalWithRBV, "ROffset", kind="config")
    recursive_ave_diff_seq = Cpt(EpicsSignal, "RecursiveAveDiffSeq", kind="config")
    recursive_ave_seq = Cpt(EpicsSignal, "RecursiveAveSeq", kind="config")
    reset_filter = Cpt(SignalWithRBV, "ResetFilter", kind="config")
    save_background = Cpt(SignalWithRBV, "SaveBackground", kind="config")
    save_flat_field = Cpt(SignalWithRBV, "SaveFlatField", kind="config")
    scale = Cpt(SignalWithRBV, "Scale", kind="config")
    scale_flat_field = Cpt(SignalWithRBV, "ScaleFlatField", kind="config")
    sum_seq = Cpt(EpicsSignal, "SumSeq", kind="config")
    valid_background = Cpt(
        EpicsSignalRO, "ValidBackground_RBV", string=True, kind="config"
    )
    valid_flat_field = Cpt(
        EpicsSignalRO, "ValidFlatField_RBV", string=True, kind="config"
    )


class Overlay(ADBase, version=(1, 9, 1), version_type="ADCore"):
    _html_docs = ["NDPluginOverlay.html"]

    blue = Cpt(SignalWithRBV, "Blue")
    draw_mode = Cpt(SignalWithRBV, "DrawMode")
    green = Cpt(SignalWithRBV, "Green")
    max_size_x = Cpt(EpicsSignal, "MaxSizeX")
    max_size_y = Cpt(EpicsSignal, "MaxSizeY")
    overlay_portname = Cpt(SignalWithRBV, "Name")

    position_x = Cpt(SignalWithRBV, "PositionX")
    position_y = Cpt(SignalWithRBV, "PositionY")

    position_xlink = Cpt(EpicsSignal, "PositionXLink")
    position_ylink = Cpt(EpicsSignal, "PositionYLink")

    red = Cpt(SignalWithRBV, "Red")
    set_xhopr = Cpt(EpicsSignal, "SetXHOPR")
    set_yhopr = Cpt(EpicsSignal, "SetYHOPR")
    shape = Cpt(SignalWithRBV, "Shape")

    size_x = Cpt(SignalWithRBV, "SizeX")
    size_y = Cpt(SignalWithRBV, "SizeY")

    size_xlink = Cpt(EpicsSignal, "SizeXLink")
    size_ylink = Cpt(EpicsSignal, "SizeYLink")
    use = Cpt(SignalWithRBV, "Use")


@register_plugin
class OverlayPlugin(PluginBase, version=(1, 9, 1), version_type="ADCore"):
    """Plugin which adds graphics overlays to an NDArray image

    Keyword arguments are passed to the base class, PluginBase

    Parameters
    ----------
    prefix : str
        The areaDetector plugin prefix
    """

    _default_suffix = "Over1:"
    _suffix_re = r"Over\d:"
    _html_docs = ["NDPluginOverlay.html"]
    _plugin_type = "NDPluginOverlay"
    max_size = DDC_EpicsSignalRO(
        ("x", "MaxSizeX_RBV"),
        ("y", "MaxSizeY_RBV"),
        doc="The maximum size in XY",
    )

    overlay_1 = Cpt(Overlay, "1:", kind="config")
    overlay_2 = Cpt(Overlay, "2:", kind="config")
    overlay_3 = Cpt(Overlay, "3:", kind="config")
    overlay_4 = Cpt(Overlay, "4:", kind="config")
    overlay_5 = Cpt(Overlay, "5:", kind="config")
    overlay_6 = Cpt(Overlay, "6:", kind="config")
    overlay_7 = Cpt(Overlay, "7:", kind="config")
    overlay_8 = Cpt(Overlay, "8:", kind="config")


@register_plugin
class ROIPlugin(PluginBase, version=(1, 9, 1), version_type="ADCore"):

    _default_suffix = "ROI1:"
    _suffix_re = r"ROI\d:"
    _html_docs = ["NDPluginROI.html"]
    _plugin_type = "NDPluginROI"

    array_size = DDC_EpicsSignalRO(
        ("z", "ArraySizeZ_RBV"),
        ("y", "ArraySizeY_RBV"),
        ("x", "ArraySizeX_RBV"),
        doc="Size of the ROI data in XYZ",
    )

    auto_size = DDC_SignalWithRBV(
        ("x", "AutoSizeX"),
        ("y", "AutoSizeY"),
        ("z", "AutoSizeZ"),
        doc="Automatically set SizeXYZ to the input array size minus MinXYZ",
    )

    bin_ = DDC_SignalWithRBV(
        ("x", "BinX"),
        ("y", "BinY"),
        ("z", "BinZ"),
        doc="Binning in XYZ",
        kind="config",
    )

    data_type_out = Cpt(SignalWithRBV, "DataTypeOut", string=True, kind="config")
    enable_scale = Cpt(SignalWithRBV, "EnableScale", string=True, kind="config")

    roi_enable = DDC_SignalWithRBV(
        ("x", "EnableX"),
        ("y", "EnableY"),
        ("z", "EnableZ"),
        string=True,
        kind="config",
        doc=(
            "Enable ROI calculations in the X, Y, Z dimensions. If not "
            "enabled then the start, size, binning, and reverse operations "
            "are disabled in the X/Y/Z dimension, and the values from the "
            "input array are used."
        ),
    )

    max_xy = DDC_EpicsSignal(
        ("x", "MaxX"),
        ("y", "MaxY"),
        doc="Maximum in XY",
    )

    max_size = DDC_EpicsSignalRO(
        ("x", "MaxSizeX_RBV"),
        ("y", "MaxSizeY_RBV"),
        ("z", "MaxSizeZ_RBV"),
        doc="Maximum size of the ROI in XYZ",
    )

    min_xyz = DDC_SignalWithRBV(
        ("min_x", "MinX"),
        ("min_y", "MinY"),
        ("min_z", "MinZ"),
        doc="Minimum size of the ROI in XYZ",
        kind="normal",
    )

    def set(self, region):
        """This functions allows for the ROI regions to be set.

        This function takes in an ROI_number, and a dictionary of tuples and
        sets the ROI region.

        PARAMETERS
        ----------
        region: dictionary.
            A dictionary defining the region to be set, which has the
            structure:
            ``{'x': [min, size], 'y': [min, size], 'z': [min, size]}``. Any of
            the keywords can be omitted, and they will be ignored.
        """
        if region is not None:
            status = []
            for direction, value in region.items():
                status.append(
                    getattr(self, "min_xyz.min_{}".format(direction)).set(value[0])
                )
                status.append(getattr(self, "size.{}".format(direction)).set(value[1]))

        return functools.reduce(operator.and_, status)

    name_ = Cpt(SignalWithRBV, "Name", doc="ROI name", kind="config")
    reverse = DDC_SignalWithRBV(
        ("x", "ReverseX"),
        ("y", "ReverseY"),
        ("z", "ReverseZ"),
        doc="Reverse ROI in the XYZ dimensions. (0=No, 1=Yes)",
    )

    scale = Cpt(SignalWithRBV, "Scale")
    set_xhopr = Cpt(EpicsSignal, "SetXHOPR")
    set_yhopr = Cpt(EpicsSignal, "SetYHOPR")

    size = DDC_SignalWithRBV(
        ("x", "SizeX"),
        ("y", "SizeY"),
        ("z", "SizeZ"),
        doc="Size of the ROI in XYZ",
        kind="normal",
    )


@register_plugin
class TransformPlugin(PluginBase, version=(1, 9, 1), version_type="ADCore"):
    _default_suffix = "Trans1:"
    _suffix_re = r"Trans\d:"
    _html_docs = ["NDPluginTransform.html"]
    _plugin_type = "NDPluginTransform"

    width = Cpt(SignalWithRBV, "ArraySize0")
    height = Cpt(SignalWithRBV, "ArraySize1")
    depth = Cpt(SignalWithRBV, "ArraySize2")
    array_size = DDC_SignalWithRBV(
        ("depth", "ArraySize2"),
        ("height", "ArraySize1"),
        ("width", "ArraySize0"),
        doc="Array size",
    )

    name_ = Cpt(EpicsSignal, "Name")
    origin_location = Cpt(SignalWithRBV, "OriginLocation")
    t1_max_size = DDC_EpicsSignal(
        ("size0", "T1MaxSize0"),
        ("size1", "T1MaxSize1"),
        ("size2", "T1MaxSize2"),
        doc="Transform 1 max size",
    )

    t2_max_size = DDC_EpicsSignal(
        ("size0", "T2MaxSize0"),
        ("size1", "T2MaxSize1"),
        ("size2", "T2MaxSize2"),
        doc="Transform 2 max size",
    )

    t3_max_size = DDC_EpicsSignal(
        ("size0", "T3MaxSize0"),
        ("size1", "T3MaxSize1"),
        ("size2", "T3MaxSize2"),
        doc="Transform 3 max size",
    )

    t4_max_size = DDC_EpicsSignal(
        ("size0", "T4MaxSize0"),
        ("size1", "T4MaxSize1"),
        ("size2", "T4MaxSize2"),
        doc="Transform 4 max size",
    )

    types = DDC_EpicsSignal(
        ("type1", "Type1"),
        ("type2", "Type2"),
        ("type3", "Type3"),
        ("type4", "Type4"),
        doc="Transform types",
    )


class FileBase(Device):
    _default_suffix = ""
    FileWriteMode = enum(SINGLE=0, CAPTURE=1, STREAM=2)

    auto_increment = Cpt(SignalWithRBV, "AutoIncrement", kind="config")
    auto_save = Cpt(SignalWithRBV, "AutoSave", kind="config")
    capture = Cpt(SignalWithRBV, "Capture")
    delete_driver_file = Cpt(SignalWithRBV, "DeleteDriverFile", kind="config")
    file_format = Cpt(SignalWithRBV, "FileFormat", kind="config")
    file_name = Cpt(SignalWithRBV, "FileName", string=True, kind="config")
    file_number = Cpt(SignalWithRBV, "FileNumber")
    file_number_sync = Cpt(EpicsSignal, "FileNumber_Sync")
    file_number_write = Cpt(EpicsSignal, "FileNumber_write")
    file_path = Cpt(
        EpicsPathSignal, "FilePath", string=True, kind="config", path_semantics="posix"
    )
    file_path_exists = Cpt(EpicsSignalRO, "FilePathExists_RBV", kind="config")
    file_template = Cpt(SignalWithRBV, "FileTemplate", string=True, kind="config")
    file_write_mode = Cpt(SignalWithRBV, "FileWriteMode", kind="config")
    full_file_name = Cpt(EpicsSignalRO, "FullFileName_RBV", string=True, kind="config")
    num_capture = Cpt(SignalWithRBV, "NumCapture", kind="config")
    num_captured = Cpt(EpicsSignalRO, "NumCaptured_RBV")
    read_file = Cpt(SignalWithRBV, "ReadFile")
    write_file = Cpt(SignalWithRBV, "WriteFile")
    write_message = Cpt(EpicsSignal, "WriteMessage", string=True)
    write_status = Cpt(EpicsSignal, "WriteStatus")


class FilePlugin(
    PluginBase,
    FileBase,
    GenerateDatumInterface,
    version=(1, 9, 1),
    version_type="ADCore",
):
    _default_suffix = ""
    _html_docs = ["NDPluginFile.html"]
    _plugin_type = "NDPluginFile"


@register_plugin
class NetCDFPlugin(FilePlugin, version=(1, 9, 1), version_type="ADCore"):
    _default_suffix = "netCDF1:"
    _suffix_re = r"netCDF\d:"
    _html_docs = ["NDFileNetCDF.html"]
    _plugin_type = "NDFileNetCDF"


@register_plugin
class TIFFPlugin(FilePlugin, version=(1, 9, 1), version_type="ADCore"):
    _default_suffix = "TIFF1:"
    _suffix_re = r"TIFF\d:"
    _html_docs = ["NDFileTIFF.html"]
    _plugin_type = "NDFileTIFF"


@register_plugin
class JPEGPlugin(FilePlugin, version=(1, 9, 1), version_type="ADCore"):
    _default_suffix = "JPEG1:"
    _suffix_re = r"JPEG\d:"
    _html_docs = ["NDFileJPEG.html"]
    _plugin_type = "NDFileJPEG"

    jpeg_quality = Cpt(SignalWithRBV, "JPEGQuality", kind="config")


@register_plugin
class KafkaPlugin(PluginBase, version=(1, 9, 1), version_type="ADCore"):

    _default_suffix = "KAFKA1:"
    _suffix_re = r"KAFKA\d:"
    _html_docs = ["NDPluginKafka.html"]
    _plugin_type = "NDPluginKafka"

    connection_message = Cpt(EpicsSignalRO, "ConnectionMessage_RBV")
    connection_status = Cpt(EpicsSignalRO, "ConnectionStatus_RBV")
    kafka_broker_address = Cpt(SignalWithRBV, "KafkaBrokerAddress")
    kafka_buffer_size = Cpt(SignalWithRBV, "KafkaBufferSize")
    kafka_max_message_size = Cpt(SignalWithRBV, "KafkaMaxMessageSize")
    kafka_max_queue_size = Cpt(SignalWithRBV, "KafkaMaxQueueSize")
    kafka_stats_interval_time = Cpt(SignalWithRBV, "KafkaStatsIntervalTime")
    kafka_topic = Cpt(SignalWithRBV, "KafkaTopic")
    reconnect_flush = Cpt(SignalWithRBV, "ReconnectFlush")
    reconnect_flush_time = Cpt(SignalWithRBV, "ReconnectFlushTime")
    source_name = Cpt(SignalWithRBV, "SourceName")
    unsent_packets = Cpt(EpicsSignalRO, "UnsentPackets_RBV")


@register_plugin
class NexusPlugin(FilePlugin, version=(1, 9, 1), version_type="ADCore"):
    _default_suffix = "Nexus1:"
    _suffix_re = r"Nexus\d:"
    _html_docs = ["NDFileNexus.html"]
    # _plugin_type = 'NDPluginFile'  # TODO was this ever fixed?
    _plugin_type = "NDPluginNexus"

    file_template_valid = Cpt(EpicsSignal, "FileTemplateValid")
    template_file_name = Cpt(
        SignalWithRBV, "TemplateFileName", string=True, kind="config"
    )
    template_file_path = Cpt(
        SignalWithRBV, "TemplateFilePath", string=True, kind="config"
    )


@register_plugin
class HDF5Plugin(FilePlugin, version=(1, 9, 1), version_type="ADCore"):
    _default_suffix = "HDF1:"
    _suffix_re = r"HDF\d:"
    _html_docs = ["NDFileHDF5.html"]
    _plugin_type = "NDFileHDF5"

    boundary_align = Cpt(SignalWithRBV, "BoundaryAlign", kind="config")
    boundary_threshold = Cpt(SignalWithRBV, "BoundaryThreshold", kind="config")
    compression = Cpt(SignalWithRBV, "Compression", kind="config")
    data_bits_offset = Cpt(SignalWithRBV, "DataBitsOffset", kind="config")

    extra_dim_name = DDC_EpicsSignalRO(
        ("name_x", "ExtraDimNameX_RBV"),
        ("name_y", "ExtraDimNameY_RBV"),
        ("name_n", "ExtraDimNameN_RBV"),
        doc="Extra dimension names (XYN)",
        kind="config",
    )

    extra_dim_size = DDC_SignalWithRBV(
        ("size_x", "ExtraDimSizeX"),
        ("size_y", "ExtraDimSizeY"),
        ("size_n", "ExtraDimSizeN"),
        doc="Extra dimension sizes (XYN)",
        kind="config",
    )

    io_speed = Cpt(EpicsSignal, "IOSpeed", kind="config")
    num_col_chunks = Cpt(SignalWithRBV, "NumColChunks", kind="config")
    num_data_bits = Cpt(SignalWithRBV, "NumDataBits", kind="config")
    num_extra_dims = Cpt(SignalWithRBV, "NumExtraDims", kind="config")
    num_frames_chunks = Cpt(SignalWithRBV, "NumFramesChunks", kind="config")
    num_frames_flush = Cpt(SignalWithRBV, "NumFramesFlush", kind="config")
    num_row_chunks = Cpt(SignalWithRBV, "NumRowChunks", kind="config")
    run_time = Cpt(EpicsSignal, "RunTime", kind="config")
    szip_num_pixels = Cpt(SignalWithRBV, "SZipNumPixels", kind="config")
    store_attr = Cpt(
        SignalWithRBV, "StoreAttr", kind="config", string=True, doc="0='No' 1='Yes'"
    )
    store_perform = Cpt(
        SignalWithRBV, "StorePerform", kind="config", string=True, doc="0='No' 1='Yes'"
    )
    zlevel = Cpt(SignalWithRBV, "ZLevel", kind="config")

    def warmup(self):
        """
        A convenience method for 'priming' the plugin.

        The plugin has to 'see' one acquisition before it is ready to capture.
        This sets the array size, etc.
        """
        self.enable.set(1).wait()
        sigs = OrderedDict(
            [
                (self.parent.cam.array_callbacks, 1),
                (self.parent.cam.image_mode, "Single"),
                (self.parent.cam.trigger_mode, "Internal"),
                # just in case tha acquisition time is set very long...
                (self.parent.cam.acquire_time, 1),
                (self.parent.cam.acquire_period, 1),
                (self.parent.cam.acquire, 1),
            ]
        )

        original_vals = {sig: sig.get() for sig in sigs}

        for sig, val in sigs.items():
            ttime.sleep(0.1)  # abundance of caution
            sig.set(val).wait()

        ttime.sleep(2)  # wait for acquisition

        for sig, val in reversed(list(original_vals.items())):
            ttime.sleep(0.1)
            sig.set(val).wait()

    def stage(self):
        if np.array(self.array_size.get()).sum() == 0:
            raise UnprimedPlugin(
                f"The plugin {self.dotted_name} on the "
                f"area detector with name {self.root.name} "
                f"has not been primed."
            )
        return super().stage()


@register_plugin
class MagickPlugin(FilePlugin, version=(1, 9, 1), version_type="ADCore"):
    _default_suffix = "Magick1:"
    _suffix_re = r"Magick\d:"
    _html_docs = ["NDFileMagick"]  # sic., no html extension
    _plugin_type = "NDFileMagick"

    bit_depth = Cpt(SignalWithRBV, "BitDepth", kind="config")
    compress_type = Cpt(SignalWithRBV, "CompressType", kind="config")
    quality = Cpt(SignalWithRBV, "Quality", kind="config")


# --- NDPluginBase ---


class PluginBase_V20(PluginBase, version=(2, 0), version_of=PluginBase):
    epics_ts_sec = Cpt(EpicsSignalRO, "EpicsTSSec_RBV")
    epics_ts_nsec = Cpt(EpicsSignalRO, "EpicsTSNsec_RBV")


class PluginBase_V22(PluginBase_V20, version=(2, 2), version_of=PluginBase):
    ad_core_version = Cpt(EpicsSignalRO, "ADCoreVersion_RBV", string=True)
    array_callbacks = Cpt(
        SignalWithRBV, "ArrayCallbacks", string=True, doc="0='Disable' 1='Enable'"
    )
    array_size_int = Cpt(EpicsSignalRO, "ArraySize_RBV")
    color_mode = Cpt(
        SignalWithRBV,
        "ColorMode",
        string=True,
        doc="0=Mono 1=Bayer 2=RGB1 3=RGB2 4=RGB3 5=YUV444 6=YUV422 7=YUV421",
    )
    data_type = Cpt(
        SignalWithRBV,
        "DataType",
        string=True,
        doc="0=Int8 1=UInt8 2=Int16 3=UInt16 4=Int32 5=UInt32 6=Float32 7=Float64",
    )
    array_size_xyz = DDC_EpicsSignalRO(
        ("array_size_x", "ArraySizeX_RBV"),
        ("array_size_y", "ArraySizeY_RBV"),
        ("array_size_z", "ArraySizeZ_RBV"),
    )


class PluginBase_V25(PluginBase_V22, version=(2, 5), version_of=PluginBase):
    queue_size = Cpt(SignalWithRBV, "QueueSize")


class PluginBase_V26(PluginBase_V25, version=(2, 6), version_of=PluginBase):
    dimensions = Cpt(SignalWithRBV, "Dimensions")
    driver_version = Cpt(EpicsSignalRO, "DriverVersion_RBV", string=True)
    execution_time = Cpt(EpicsSignalRO, "ExecutionTime_RBV", string=True)
    ndimensions = Cpt(SignalWithRBV, "NDimensions", string=True)
    array_size_all = DDC_SignalWithRBV(
        ("array_size0", "ArraySize0"),
        ("array_size1", "ArraySize1"),
        ("array_size2", "ArraySize2"),
        ("array_size3", "ArraySize3"),
        ("array_size4", "ArraySize4"),
        ("array_size5", "ArraySize5"),
        ("array_size6", "ArraySize6"),
        ("array_size7", "ArraySize7"),
        ("array_size8", "ArraySize8"),
        ("array_size9", "ArraySize9"),
        doc="array_size",
    )
    dim_sa = DDC_SignalWithRBV(
        ("dim0_sa", "Dim0SA"),
        ("dim1_sa", "Dim1SA"),
        ("dim2_sa", "Dim2SA"),
        ("dim3_sa", "Dim3SA"),
        ("dim4_sa", "Dim4SA"),
        ("dim5_sa", "Dim5SA"),
        ("dim6_sa", "Dim6SA"),
        ("dim7_sa", "Dim7SA"),
        ("dim8_sa", "Dim8SA"),
        ("dim9_sa", "Dim9SA"),
        doc="dim_sa",
    )


class PluginBase_V31(PluginBase_V26, version=(3, 1), version_of=PluginBase):
    disordered_arrays = Cpt(SignalWithRBV, "DisorderedArrays")
    dropped_output_arrays = Cpt(SignalWithRBV, "DroppedOutputArrays")
    max_threads = Cpt(EpicsSignalRO, "MaxThreads_RBV")
    nd_attributes_macros = Cpt(EpicsSignal, "NDAttributesMacros")
    nd_attributes_status = Cpt(
        EpicsSignal,
        "NDAttributesStatus",
        string=True,
        doc="0='Attributes file OK' 1='File not found' 2='XML syntax error' 3='Macro substitution error'",
    )
    num_threads = Cpt(SignalWithRBV, "NumThreads")
    process_plugin = Cpt(EpicsSignal, "ProcessPlugin", string=True)
    sort_free = Cpt(EpicsSignal, "SortFree")
    sort_free_low = Cpt(EpicsSignal, "SortFreeLow")
    sort_mode = Cpt(SignalWithRBV, "SortMode", string=True, doc="0=Unsorted 1=Sorted")
    sort_size = Cpt(SignalWithRBV, "SortSize")
    sort_time = Cpt(SignalWithRBV, "SortTime")


class PluginBase_V33(PluginBase_V31, version=(3, 3), version_of=PluginBase):
    empty_free_list = Cpt(EpicsSignal, "EmptyFreeList", string=True)
    num_queued_arrays = Cpt(EpicsSignal, "NumQueuedArrays", string=True)
    pool_max_buffers = None  # REMOVED


class PluginBase_V34(PluginBase_V33, version=(3, 4), version_of=PluginBase):
    max_array_rate = Cpt(SignalWithRBV, "MaxArrayRate")
    max_array_rate_cout = Cpt(EpicsSignal, "MaxArrayRate_COUT")
    max_byte_rate = Cpt(SignalWithRBV, "MaxByteRate")
    min_callback_time = Cpt(SignalWithRBV, "MinCallbackTime")


# --- NDFile ---


class FilePlugin_V20(PluginBase_V20, FilePlugin, version=(2, 0), version_of=FilePlugin):
    ...


class FilePlugin_V21(FilePlugin_V20, version=(2, 1), version_of=FilePlugin):
    lazy_open = Cpt(SignalWithRBV, "LazyOpen", string=True, doc="0='No' 1='Yes'")


class FilePlugin_V22(
    PluginBase_V22, FilePlugin_V21, version=(2, 2), version_of=FilePlugin
):
    create_directory = Cpt(SignalWithRBV, "CreateDirectory", kind="config")
    file_number = Cpt(SignalWithRBV, "FileNumber")
    file_number_sync = None  # REMOVED
    file_number_write = None  # REMOVED
    temp_suffix = Cpt(SignalWithRBV, "TempSuffix", string=True)


class FilePlugin_V25(
    PluginBase_V25, FilePlugin_V22, version=(2, 5), version_of=FilePlugin
):
    ...


class FilePlugin_V26(
    PluginBase_V26, FilePlugin_V25, version=(2, 6), version_of=FilePlugin
):
    ...


class FilePlugin_V31(
    PluginBase_V31, FilePlugin_V26, version=(3, 1), version_of=FilePlugin
):
    ...


class FilePlugin_V33(
    PluginBase_V33, FilePlugin_V31, version=(3, 3), version_of=FilePlugin
):
    ...


class FilePlugin_V34(
    PluginBase_V34, FilePlugin_V33, version=(3, 4), version_of=FilePlugin
):
    ...


# --- ColorConvPlugin ---


class ColorConvPlugin_V20(
    PluginBase_V20, ColorConvPlugin, version=(2, 0), version_of=ColorConvPlugin
):
    ...


class ColorConvPlugin_V22(
    PluginBase_V22, ColorConvPlugin_V20, version=(2, 2), version_of=ColorConvPlugin
):
    ...


class ColorConvPlugin_V25(
    PluginBase_V25, ColorConvPlugin_V22, version=(2, 5), version_of=ColorConvPlugin
):
    ...


class ColorConvPlugin_V26(
    PluginBase_V26, ColorConvPlugin_V25, version=(2, 6), version_of=ColorConvPlugin
):
    ...


class ColorConvPlugin_V31(
    PluginBase_V31, ColorConvPlugin_V26, version=(3, 1), version_of=ColorConvPlugin
):
    ...


class ColorConvPlugin_V33(
    PluginBase_V33, ColorConvPlugin_V31, version=(3, 3), version_of=ColorConvPlugin
):
    ...


class ColorConvPlugin_V34(
    PluginBase_V34, ColorConvPlugin_V33, version=(3, 4), version_of=ColorConvPlugin
):
    ...


# --- NDFileHDF5 ---


class HDF5Plugin_V20(FilePlugin_V20, HDF5Plugin, version=(2, 0), version_of=HDF5Plugin):
    ...


class HDF5Plugin_V21(
    FilePlugin_V21, HDF5Plugin_V20, version=(2, 1), version_of=HDF5Plugin
):
    xml_error_msg = Cpt(EpicsSignalRO, "XMLErrorMsg_RBV")
    xml_file_name = Cpt(SignalWithRBV, "XMLFileName", string=True, kind="config")
    xml_valid = Cpt(EpicsSignalRO, "XMLValid_RBV", string=True, doc="0='No' 1='Yes'")


class HDF5Plugin_V22(
    FilePlugin_V22, HDF5Plugin_V21, version=(2, 2), version_of=HDF5Plugin
):
    nd_attribute_chunk = Cpt(SignalWithRBV, "NDAttributeChunk")


class HDF5Plugin_V25(
    FilePlugin_V25, HDF5Plugin_V22, version=(2, 5), version_of=HDF5Plugin
):
    dim_att_datasets = Cpt(
        SignalWithRBV, "DimAttDatasets", string=True, doc="0='No' 1='Yes'"
    )
    fill_value = Cpt(SignalWithRBV, "FillValue")
    position_mode = Cpt(
        SignalWithRBV, "PositionMode", string=True, doc="0='Off' 1='On'"
    )
    swmr_active = Cpt(
        EpicsSignalRO, "SWMRActive_RBV", string=True, doc="0='Off' 1='Active'"
    )
    swmr_cb_counter = Cpt(EpicsSignalRO, "SWMRCbCounter_RBV")
    swmr_mode = Cpt(SignalWithRBV, "SWMRMode", string=True, doc="0='Off' 1='On'")
    swmr_supported = Cpt(
        EpicsSignalRO,
        "SWMRSupported_RBV",
        string=True,
        doc="0='Not Supported' 1='Supported'",
    )
    extra_dim_chunk = DDC_SignalWithRBV(
        ("chunk_3", "ExtraDimChunk3"),
        ("chunk_4", "ExtraDimChunk4"),
        ("chunk_5", "ExtraDimChunk5"),
        ("chunk_6", "ExtraDimChunk6"),
        ("chunk_7", "ExtraDimChunk7"),
        ("chunk_8", "ExtraDimChunk8"),
        ("chunk_9", "ExtraDimChunk9"),
        ("chunk_x", "ExtraDimChunkX"),
        ("chunk_y", "ExtraDimChunkY"),
        doc="extra_dim_chunk",
    )
    extra_dim_name = DDC_EpicsSignalRO(
        ("name_3", "ExtraDimName3_RBV"),
        ("name_4", "ExtraDimName4_RBV"),
        ("name_5", "ExtraDimName5_RBV"),
        ("name_6", "ExtraDimName6_RBV"),
        ("name_7", "ExtraDimName7_RBV"),
        ("name_8", "ExtraDimName8_RBV"),
        ("name_9", "ExtraDimName9_RBV"),
        ("name_x", "ExtraDimNameX_RBV"),
        ("name_y", "ExtraDimNameY_RBV"),
        ("name_n", "ExtraDimNameN_RBV"),
        doc="extra_dim_name",
    )
    extra_dim_size = DDC_SignalWithRBV(
        ("size_3", "ExtraDimSize3"),
        ("size_4", "ExtraDimSize4"),
        ("size_5", "ExtraDimSize5"),
        ("size_6", "ExtraDimSize6"),
        ("size_7", "ExtraDimSize7"),
        ("size_8", "ExtraDimSize8"),
        ("size_9", "ExtraDimSize9"),
        ("size_x", "ExtraDimSizeX"),
        ("size_y", "ExtraDimSizeY"),
        ("size_n", "ExtraDimSizeN"),
        doc="extra_dim_size",
    )
    pos_index_dim = DDC_SignalWithRBV(
        ("dim_3", "PosIndexDim3"),
        ("dim_4", "PosIndexDim4"),
        ("dim_5", "PosIndexDim5"),
        ("dim_6", "PosIndexDim6"),
        ("dim_7", "PosIndexDim7"),
        ("dim_8", "PosIndexDim8"),
        ("dim_9", "PosIndexDim9"),
        ("dim_x", "PosIndexDimX"),
        ("dim_y", "PosIndexDimY"),
        ("dim_n", "PosIndexDimN"),
        doc="pos_index_dim",
    )
    pos_name_dim = DDC_SignalWithRBV(
        ("dim_3", "PosNameDim3"),
        ("dim_4", "PosNameDim4"),
        ("dim_5", "PosNameDim5"),
        ("dim_6", "PosNameDim6"),
        ("dim_7", "PosNameDim7"),
        ("dim_8", "PosNameDim8"),
        ("dim_9", "PosNameDim9"),
        ("dim_x", "PosNameDimX"),
        ("dim_y", "PosNameDimY"),
        ("dim_n", "PosNameDimN"),
        doc="pos_name_dim",
    )


class HDF5Plugin_V26(
    FilePlugin_V26, HDF5Plugin_V25, version=(2, 6), version_of=HDF5Plugin
):
    ...


class HDF5Plugin_V31(
    FilePlugin_V31, HDF5Plugin_V26, version=(3, 1), version_of=HDF5Plugin
):
    ...


class HDF5Plugin_V32(HDF5Plugin_V31, version=(3, 2), version_of=HDF5Plugin):
    blosc_compressor = Cpt(
        SignalWithRBV,
        "BloscCompressor",
        string=True,
        doc="0=blosclz 1=lz4 2=lz4hc 3=snappy 4=zlib 5=zstd",
    )
    blosc_level = Cpt(SignalWithRBV, "BloscLevel")
    blosc_shuffle = Cpt(
        SignalWithRBV,
        "BloscShuffle",
        string=True,
        doc="0=None 1=ByteShuffle 2=BitShuffle",
    )
    compression = Cpt(
        SignalWithRBV,
        "Compression",
        string=True,
        doc="0=None 1=N-bit 2=szip 3=zlib 4=blosc",
    )


class HDF5Plugin_V33(
    FilePlugin_V33, HDF5Plugin_V32, version=(3, 3), version_of=HDF5Plugin
):
    ...


class HDF5Plugin_V34(
    FilePlugin_V34, HDF5Plugin_V33, version=(3, 4), version_of=HDF5Plugin
):
    ...


# --- NDStdArrays ---


class ImagePlugin_V20(
    PluginBase_V20, ImagePlugin, version=(2, 0), version_of=ImagePlugin
):
    ...


class ImagePlugin_V22(
    PluginBase_V22, ImagePlugin_V20, version=(2, 2), version_of=ImagePlugin
):
    ...


class ImagePlugin_V25(
    PluginBase_V25, ImagePlugin_V22, version=(2, 5), version_of=ImagePlugin
):
    ...


class ImagePlugin_V26(
    PluginBase_V26, ImagePlugin_V25, version=(2, 6), version_of=ImagePlugin
):
    ...


class ImagePlugin_V31(
    PluginBase_V31, ImagePlugin_V26, version=(3, 1), version_of=ImagePlugin
):
    ...


class ImagePlugin_V33(
    PluginBase_V33, ImagePlugin_V31, version=(3, 3), version_of=ImagePlugin
):
    ...


class ImagePlugin_V34(
    PluginBase_V34, ImagePlugin_V33, version=(3, 4), version_of=ImagePlugin
):
    ...


# --- NDFileJPEG ---


class JPEGPlugin_V20(FilePlugin_V20, JPEGPlugin, version=(2, 0), version_of=JPEGPlugin):
    ...


class JPEGPlugin_V21(
    FilePlugin_V21, JPEGPlugin_V20, version=(2, 1), version_of=JPEGPlugin
):
    ...


class JPEGPlugin_V22(
    FilePlugin_V22, JPEGPlugin_V21, version=(2, 2), version_of=JPEGPlugin
):
    ...


class JPEGPlugin_V25(
    FilePlugin_V25, JPEGPlugin_V22, version=(2, 5), version_of=JPEGPlugin
):
    ...


class JPEGPlugin_V26(
    FilePlugin_V26, JPEGPlugin_V25, version=(2, 6), version_of=JPEGPlugin
):
    ...


class JPEGPlugin_V31(
    FilePlugin_V31, JPEGPlugin_V26, version=(3, 1), version_of=JPEGPlugin
):
    ...


class JPEGPlugin_V33(
    FilePlugin_V33, JPEGPlugin_V31, version=(3, 3), version_of=JPEGPlugin
):
    ...


class JPEGPlugin_V34(
    FilePlugin_V34, JPEGPlugin_V33, version=(3, 4), version_of=JPEGPlugin
):
    ...


# --- Kafka Plugin ---


class KafkaPlugin_V20(
    PluginBase_V20, KafkaPlugin, version=(2, 0), version_of=KafkaPlugin
):
    ...


class KafkaPlugin_V22(
    PluginBase_V22, KafkaPlugin_V20, version=(2, 2), version_of=KafkaPlugin
):
    ...


class KafkaPlugin_V25(
    PluginBase_V25, KafkaPlugin_V22, version=(2, 5), version_of=KafkaPlugin
):
    ...


class KafkaPlugin_V26(
    PluginBase_V26, KafkaPlugin_V25, version=(2, 6), version_of=KafkaPlugin
):
    ...


class KafkaPlugin_V31(
    PluginBase_V31, KafkaPlugin_V26, version=(3, 1), version_of=KafkaPlugin
):
    ...


class KafkaPlugin_V33(
    PluginBase_V33, KafkaPlugin_V31, version=(3, 3), version_of=KafkaPlugin
):
    ...


class KafkaPlugin_V34(
    PluginBase_V34, KafkaPlugin_V33, version=(3, 4), version_of=KafkaPlugin
):
    ...


# --- NDFileMagick ---


class MagickPlugin_V20(
    FilePlugin_V20, MagickPlugin, version=(2, 0), version_of=MagickPlugin
):
    ...


class MagickPlugin_V21(
    FilePlugin_V21, MagickPlugin_V20, version=(2, 1), version_of=MagickPlugin
):
    ...


class MagickPlugin_V22(
    FilePlugin_V22, MagickPlugin_V21, version=(2, 2), version_of=MagickPlugin
):
    ...


class MagickPlugin_V25(
    FilePlugin_V25, MagickPlugin_V22, version=(2, 5), version_of=MagickPlugin
):
    ...


class MagickPlugin_V26(
    FilePlugin_V26, MagickPlugin_V25, version=(2, 6), version_of=MagickPlugin
):
    ...


class MagickPlugin_V31(
    FilePlugin_V31, MagickPlugin_V26, version=(3, 1), version_of=MagickPlugin
):
    bit_depth = Cpt(SignalWithRBV, "BitDepth", string=True, doc="1=1 8=8 16=16 32=32")


class MagickPlugin_V33(
    FilePlugin_V33, MagickPlugin_V31, version=(3, 3), version_of=MagickPlugin
):
    ...


class MagickPlugin_V34(
    FilePlugin_V34, MagickPlugin_V33, version=(3, 4), version_of=MagickPlugin
):
    ...


# --- NDFileNetCDF ---


class NetCDFPlugin_V20(
    FilePlugin_V20, NetCDFPlugin, version=(2, 0), version_of=NetCDFPlugin
):
    ...


class NetCDFPlugin_V21(
    FilePlugin_V21, NetCDFPlugin_V20, version=(2, 1), version_of=NetCDFPlugin
):
    ...


class NetCDFPlugin_V22(
    FilePlugin_V22, NetCDFPlugin_V21, version=(2, 2), version_of=NetCDFPlugin
):
    ...


class NetCDFPlugin_V25(
    FilePlugin_V25, NetCDFPlugin_V22, version=(2, 5), version_of=NetCDFPlugin
):
    ...


class NetCDFPlugin_V26(
    FilePlugin_V26, NetCDFPlugin_V25, version=(2, 6), version_of=NetCDFPlugin
):
    ...


class NetCDFPlugin_V31(
    FilePlugin_V31, NetCDFPlugin_V26, version=(3, 1), version_of=NetCDFPlugin
):
    ...


class NetCDFPlugin_V33(
    FilePlugin_V33, NetCDFPlugin_V31, version=(3, 3), version_of=NetCDFPlugin
):
    ...


class NetCDFPlugin_V34(
    FilePlugin_V34, NetCDFPlugin_V33, version=(3, 4), version_of=NetCDFPlugin
):
    ...


# --- NDFileNexus ---


class NexusPlugin_V20(
    FilePlugin_V20, NexusPlugin, version=(2, 0), version_of=NexusPlugin
):
    ...


class NexusPlugin_V21(
    FilePlugin_V21, NexusPlugin_V20, version=(2, 1), version_of=NexusPlugin
):
    ...


class NexusPlugin_V22(
    FilePlugin_V22, NexusPlugin_V21, version=(2, 2), version_of=NexusPlugin
):
    ...


class NexusPlugin_V25(
    FilePlugin_V25, NexusPlugin_V22, version=(2, 5), version_of=NexusPlugin
):
    ...


class NexusPlugin_V26(
    FilePlugin_V26, NexusPlugin_V25, version=(2, 6), version_of=NexusPlugin
):
    ...


class NexusPlugin_V31(
    FilePlugin_V31, NexusPlugin_V26, version=(3, 1), version_of=NexusPlugin
):
    ...


class NexusPlugin_V33(
    FilePlugin_V33, NexusPlugin_V31, version=(3, 3), version_of=NexusPlugin
):
    ...


class NexusPlugin_V34(
    FilePlugin_V34, NexusPlugin_V33, version=(3, 4), version_of=NexusPlugin
):
    ...


# --- NDOverlayN ---


class Overlay_V21(Overlay, version=(2, 1), version_of=Overlay):
    display_text = Cpt(SignalWithRBV, "DisplayText")
    font = Cpt(
        SignalWithRBV,
        "Font",
        string=True,
        doc="0=6x13 1='6x13 Bold' 2=9x15 3='9x15 Bold'",
    )
    shape = Cpt(SignalWithRBV, "Shape", string=True, doc="0=Cross 1=Rectangle 2=Text")
    time_stamp_format = Cpt(SignalWithRBV, "TimeStampFormat", string=True)
    width = DDC_SignalWithRBV(("x", "WidthX"), ("y", "WidthY"), doc="width")
    width_link = DDC_EpicsSignal(
        ("x", "WidthXLink"), ("y", "WidthYLink"), doc="width_link"
    )


class Overlay_V26(Overlay_V21, version=(2, 6), version_of=Overlay):
    shape = Cpt(
        SignalWithRBV, "Shape", string=True, doc="0=Cross 1=Rectangle 2=Text 3=Ellipse "
    )
    center = DDC_SignalWithRBV(("x", "CenterX"), ("y", "CenterY"), doc="center")
    center_link = DDC_EpicsSignal(
        ("x", "CenterXLink"), ("y", "CenterYLink"), doc="center_link"
    )
    position_ = DDC_SignalWithRBV(
        ("x", "PositionX"), ("y", "PositionY"), doc="position"
    )
    set_hopr = DDC_EpicsSignal(("x", "SetXHOPR"), ("y", "SetYHOPR"), doc="set_hopr")


class Overlay_V31(Overlay_V26, version=(3, 1), version_of=Overlay):
    ...


# --- NDOverlay ---


class OverlayPlugin_V20(
    PluginBase_V20, OverlayPlugin, version=(2, 0), version_of=OverlayPlugin
):
    ...


class OverlayPlugin_V22(
    PluginBase_V22, OverlayPlugin_V20, version=(2, 2), version_of=OverlayPlugin
):
    ...


class OverlayPlugin_V25(
    PluginBase_V25, OverlayPlugin_V22, version=(2, 5), version_of=OverlayPlugin
):
    ...


class OverlayPlugin_V26(
    PluginBase_V26, OverlayPlugin_V25, version=(2, 6), version_of=OverlayPlugin
):
    ...


class OverlayPlugin_V31(
    PluginBase_V31, OverlayPlugin_V26, version=(3, 1), version_of=OverlayPlugin
):
    ...


class OverlayPlugin_V33(
    PluginBase_V33, OverlayPlugin_V31, version=(3, 3), version_of=OverlayPlugin
):
    ...


class OverlayPlugin_V34(
    PluginBase_V34, OverlayPlugin_V33, version=(3, 4), version_of=OverlayPlugin
):
    ...


# --- NDProcess ---


class ProcessPlugin_V20(
    PluginBase_V20, ProcessPlugin, version=(2, 0), version_of=ProcessPlugin
):
    ...


class ProcessPlugin_V22(
    PluginBase_V22, ProcessPlugin_V20, version=(2, 2), version_of=ProcessPlugin
):
    ...


class ProcessPlugin_V25(
    PluginBase_V25, ProcessPlugin_V22, version=(2, 5), version_of=ProcessPlugin
):
    ...


class ProcessPlugin_V26(
    PluginBase_V26, ProcessPlugin_V25, version=(2, 6), version_of=ProcessPlugin
):
    ...


class ProcessPlugin_V31(
    PluginBase_V31, ProcessPlugin_V26, version=(3, 1), version_of=ProcessPlugin
):
    ...


class ProcessPlugin_V33(
    PluginBase_V33, ProcessPlugin_V31, version=(3, 3), version_of=ProcessPlugin
):
    port_backup = Cpt(EpicsSignal, "PortBackup", string=True)
    read_background_tiff_seq = Cpt(EpicsSignal, "ReadBackgroundTIFFSeq")
    read_flat_field_tiff_seq = Cpt(EpicsSignal, "ReadFlatFieldTIFFSeq")


class ProcessPlugin_V34(
    PluginBase_V34, ProcessPlugin_V33, version=(3, 4), version_of=ProcessPlugin
):
    ...


# --- NDROI ---


class ROIPlugin_V20(PluginBase_V20, ROIPlugin, version=(2, 0), version_of=ROIPlugin):
    array_size_xyz = DDC_EpicsSignalRO(
        ("x", "ArraySizeX_RBV"),
        ("y", "ArraySizeY_RBV"),
        ("z", "ArraySizeZ_RBV"),
    )
    array_size_012 = DDC_EpicsSignalRO(
        ("size0", "ArraySize0_RBV"),
        ("size1", "ArraySize1_RBV"),
        ("size2", "ArraySize2_RBV"),
    )


class ROIPlugin_V22(
    PluginBase_V22, ROIPlugin_V20, version=(2, 2), version_of=ROIPlugin
):
    ...


class ROIPlugin_V25(
    PluginBase_V25, ROIPlugin_V22, version=(2, 5), version_of=ROIPlugin
):
    ...


class ROIPlugin_V26(
    PluginBase_V26, ROIPlugin_V25, version=(2, 6), version_of=ROIPlugin
):
    collapse_dims = Cpt(
        SignalWithRBV, "CollapseDims", string=True, doc="0='Disable' 1='Enable'"
    )


class ROIPlugin_V31(
    PluginBase_V31, ROIPlugin_V26, version=(3, 1), version_of=ROIPlugin
):
    ...


class ROIPlugin_V33(
    PluginBase_V33, ROIPlugin_V31, version=(3, 3), version_of=ROIPlugin
):
    ...


class ROIPlugin_V34(
    PluginBase_V34, ROIPlugin_V33, version=(3, 4), version_of=ROIPlugin
):
    ...


# --- NDROIStat ---


@register_plugin
class ROIStatPlugin(Device, version_type="ADCore"):
    "Serves as a base class for other versions"
    _default_suffix = "ROIStat1:"
    _suffix_re = r"ROIStat\d:"
    _plugin_type = "NDPluginROIStat"


class ROIStatPlugin_V22(
    PluginBase_V22, ROIStatPlugin, version=(2, 2), version_of=ROIStatPlugin
):
    reset_all = Cpt(EpicsSignal, "ResetAll", string=True, doc="")


class ROIStatPlugin_V23(ROIStatPlugin_V22, version=(2, 3), version_of=ROIStatPlugin):
    ts_acquiring = Cpt(
        EpicsSignal, "TSAcquiring", string=True, doc="0='Done' 1='Acquiring'"
    )
    ts_control = Cpt(
        EpicsSignal, "TSControl", string=True, doc="0=Erase/Start 1=Start 2=Stop 3=Read"
    )
    ts_current_point = Cpt(EpicsSignal, "TSCurrentPoint")
    ts_num_points = Cpt(EpicsSignal, "TSNumPoints")
    ts_read = Cpt(EpicsSignal, "TSRead")


class ROIStatPlugin_V25(
    PluginBase_V25, ROIStatPlugin_V23, version=(2, 5), version_of=ROIStatPlugin
):
    ...


class ROIStatPlugin_V26(
    PluginBase_V26, ROIStatPlugin_V25, version=(2, 6), version_of=ROIStatPlugin
):
    ...


class ROIStatPlugin_V31(
    PluginBase_V31, ROIStatPlugin_V26, version=(3, 1), version_of=ROIStatPlugin
):
    ...


class ROIStatPlugin_V33(
    PluginBase_V33, ROIStatPlugin_V31, version=(3, 3), version_of=ROIStatPlugin
):
    ...


class ROIStatPlugin_V34(
    PluginBase_V34, ROIStatPlugin_V33, version=(3, 4), version_of=ROIStatPlugin
):
    ...


# --- NDROIStatN ---


class ROIStatNPlugin(Device, version_type="ADCore"):
    "Serves as a base class for other versions"
    ...


class ROIStatNPlugin_V22(ROIStatNPlugin, version=(2, 2), version_of=ROIStatNPlugin):
    bgd_width = Cpt(SignalWithRBV, "BgdWidth")
    max_value = Cpt(EpicsSignalRO, "MaxValue_RBV")
    mean_value = Cpt(EpicsSignalRO, "MeanValue_RBV")
    min_value = Cpt(EpicsSignalRO, "MinValue_RBV")
    name_ = Cpt(EpicsSignal, "Name", string=True)
    net = Cpt(EpicsSignalRO, "Net_RBV")
    reset = Cpt(EpicsSignal, "Reset", string=True, doc="")
    total = Cpt(EpicsSignalRO, "Total_RBV")
    use = Cpt(SignalWithRBV, "Use", string=True, doc="0='No' 1='Yes'")
    max_size = DDC_EpicsSignalRO(
        ("x", "MaxSizeX_RBV"), ("y", "MaxSizeY_RBV"), doc="max_size"
    )
    min_ = DDC_SignalWithRBV(("x", "MinX"), ("y", "MinY"), doc="min")
    size = DDC_SignalWithRBV(("x", "SizeX"), ("y", "SizeY"), doc="size")


class ROIStatNPlugin_V23(ROIStatNPlugin_V22, version=(2, 3), version_of=ROIStatNPlugin):
    ts_max_value = Cpt(EpicsSignal, "TSMaxValue")
    ts_mean_value = Cpt(EpicsSignal, "TSMeanValue")
    ts_min_value = Cpt(EpicsSignal, "TSMinValue")
    ts_net = Cpt(EpicsSignal, "TSNet")
    ts_total = Cpt(EpicsSignal, "TSTotal")


class ROIStatNPlugin_V25(ROIStatNPlugin_V23, version=(2, 5), version_of=ROIStatNPlugin):
    ts_timestamp = Cpt(EpicsSignal, "TSTimestamp")


# --- NDStats ---


class StatsPlugin_V20(
    PluginBase_V20, StatsPlugin, version=(2, 0), version_of=StatsPlugin
):
    ...


class StatsPlugin_V22(
    PluginBase_V22, StatsPlugin_V20, version=(2, 2), version_of=StatsPlugin
):
    hist_entropy = Cpt(SignalWithRBV, "HistEntropy")
    max_value = Cpt(SignalWithRBV, "MaxValue")
    mean_value = Cpt(SignalWithRBV, "MeanValue")
    min_value = Cpt(SignalWithRBV, "MinValue")
    net = Cpt(SignalWithRBV, "Net")
    reset = Cpt(EpicsSignal, "Reset")
    resets = DDC_EpicsSignal(("reset1", "Reset1"), doc="reset")
    sigma_value = Cpt(EpicsSignal, "SigmaValue")
    sigma_readout = Cpt(EpicsSignalRO, "Sigma_RBV")
    sigma_xy = Cpt(SignalWithRBV, "SigmaXY")
    total = Cpt(SignalWithRBV, "Total")
    max_ = DDC_SignalWithRBV(("x", "MaxX"), ("y", "MaxY"), doc="max")
    min_ = DDC_SignalWithRBV(("x", "MinX"), ("y", "MinY"), doc="min")
    sigma = DDC_SignalWithRBV(("x", "SigmaX"), ("y", "SigmaY"), doc="sigma")

    # Changed type to SignalWithRBV in R2-2:
    centroid = DDC_SignalWithRBV(
        ("x", "CentroidX"), ("y", "CentroidY"), doc="The centroid XY"
    )
    color_mode = Cpt(SignalWithRBV, "ColorMode")
    data_type = Cpt(SignalWithRBV, "DataType", string=True)


class StatsPlugin_V25(
    PluginBase_V25, StatsPlugin_V22, version=(2, 5), version_of=StatsPlugin
):
    ts_timestamp = Cpt(EpicsSignal, "TSTimestamp")


class StatsPlugin_V26(
    PluginBase_V26, StatsPlugin_V25, version=(2, 6), version_of=StatsPlugin
):
    centroid_total = Cpt(SignalWithRBV, "CentroidTotal")
    eccentricity = Cpt(SignalWithRBV, "Eccentricity")
    hist_above = Cpt(SignalWithRBV, "HistAbove")
    hist_below = Cpt(SignalWithRBV, "HistBelow")
    orientation = Cpt(SignalWithRBV, "Orientation")
    resets = DDC_EpicsSignal(("reset1", "Reset1"), ("reset2", "Reset2"), doc="reset")
    ts_centroid_total = Cpt(EpicsSignal, "TSCentroidTotal")
    ts_eccentricity = Cpt(EpicsSignal, "TSEccentricity")
    ts_orientation = Cpt(EpicsSignal, "TSOrientation")
    kurtosis = DDC_SignalWithRBV(("x", "KurtosisX"), ("y", "KurtosisY"), doc="kurtosis")
    skew = DDC_SignalWithRBV(("x", "SkewX"), ("y", "SkewY"), doc="skew")
    ts_kurtosis = DDC_EpicsSignal(
        ("x", "TSKurtosisX"), ("y", "TSKurtosisY"), doc="ts_kurtosis"
    )
    ts_skew = DDC_EpicsSignal(("x", "TSSkewX"), ("y", "TSSkewY"), doc="ts_skew")


class StatsPlugin_V31(
    PluginBase_V31, StatsPlugin_V26, version=(3, 1), version_of=StatsPlugin
):
    ...


class StatsPlugin_V32(StatsPlugin_V31, version=(3, 2), version_of=StatsPlugin):
    histogram_x = Cpt(EpicsSignalRO, "HistogramX_RBV")


class StatsPlugin_V33(
    PluginBase_V33, StatsPlugin_V32, version=(3, 3), version_of=StatsPlugin
):
    ts_acquiring = None  # REMOVED
    ts_control = None  # REMOVED
    ts_current_point = None  # REMOVED
    ts_num_points = None  # REMOVED
    ts_read = None  # REMOVED
    ts_sigma_x = DDC_EpicsSignal(
        ("ts_sigma_x", "TSSigmaX"), ("ts_sigma_y", "TSSigmaY"), doc="ts_sigma"
    )


class StatsPlugin_V34(
    PluginBase_V34, StatsPlugin_V33, version=(3, 4), version_of=StatsPlugin
):
    ...


# --- NDFileTIFF ---


class TIFFPlugin_V20(FilePlugin_V20, TIFFPlugin, version=(2, 0), version_of=TIFFPlugin):
    ...


class TIFFPlugin_V21(
    FilePlugin_V21, TIFFPlugin_V20, version=(2, 1), version_of=TIFFPlugin
):
    ...


class TIFFPlugin_V22(
    FilePlugin_V22, TIFFPlugin_V21, version=(2, 2), version_of=TIFFPlugin
):
    ...


class TIFFPlugin_V25(
    FilePlugin_V25, TIFFPlugin_V22, version=(2, 5), version_of=TIFFPlugin
):
    ...


class TIFFPlugin_V26(
    FilePlugin_V26, TIFFPlugin_V25, version=(2, 6), version_of=TIFFPlugin
):
    ...


class TIFFPlugin_V31(
    FilePlugin_V31, TIFFPlugin_V26, version=(3, 1), version_of=TIFFPlugin
):
    ...


class TIFFPlugin_V33(
    FilePlugin_V33, TIFFPlugin_V31, version=(3, 3), version_of=TIFFPlugin
):
    ...


class TIFFPlugin_V34(
    FilePlugin_V34, TIFFPlugin_V33, version=(3, 4), version_of=TIFFPlugin
):
    ...


# --- NDTransform ---


class TransformPlugin_V20(
    PluginBase_V20, TransformPlugin, version=(2, 0), version_of=TransformPlugin
):
    array_size = DDC_SignalWithRBV(
        ("array_size0", "ArraySize0"),
        ("array_size1", "ArraySize1"),
        ("array_size2", "ArraySize2"),
        doc="Array size",
    )


class TransformPlugin_V21(
    TransformPlugin_V20, version=(2, 1), version_of=TransformPlugin
):
    name_ = None  # REMOVED
    origin_location = None  # REMOVED
    t1_max_size = None  # REMOVED DDC
    t2_max_size = None  # REMOVED DDC
    t3_max_size = None  # REMOVED DDC
    t4_max_size = None  # REMOVED DDC
    types = None  # REMOVED DDC
    width = None  # Removed array_size portions
    height = None  # Removed array_size portions
    depth = None  # Removed array_size portions
    type_ = Cpt(
        EpicsSignal,
        "Type",
        string=True,
        doc="0=None 1=Rot90 2=Rot180 3=Rot270 4=Mirror 5=Rot90Mirror 6=Rot180Mirror 7=Rot270Mirror",
    )
    array_size = DDC_EpicsSignalRO(
        ("array_size0", "ArraySize0_RBV"),
        ("array_size1", "ArraySize1_RBV"),
        ("array_size2", "ArraySize2_RBV"),
        doc="Array size",
    )


class TransformPlugin_V22(
    PluginBase_V22, TransformPlugin_V21, version=(2, 2), version_of=TransformPlugin
):
    ...


class TransformPlugin_V25(
    PluginBase_V25, TransformPlugin_V22, version=(2, 5), version_of=TransformPlugin
):
    ...


class TransformPlugin_V26(
    PluginBase_V26, TransformPlugin_V25, version=(2, 6), version_of=TransformPlugin
):
    ...


class TransformPlugin_V31(
    PluginBase_V31, TransformPlugin_V26, version=(3, 1), version_of=TransformPlugin
):
    ...


class TransformPlugin_V33(
    PluginBase_V33, TransformPlugin_V31, version=(3, 3), version_of=TransformPlugin
):
    ...


class TransformPlugin_V34(
    PluginBase_V34, TransformPlugin_V33, version=(3, 4), version_of=TransformPlugin
):
    ...


# --- NDPva ---


@register_plugin
class PvaPlugin(Device, version_type="ADCore"):
    "Serves as a base class for other versions"
    _default_suffix = "Pva1:"
    _suffix_re = r"Pva\d:"
    _plugin_type = "NDPluginPva"


class PvaPlugin_V25(PluginBase_V25, PvaPlugin, version=(2, 5), version_of=PvaPlugin):
    pv_name = Cpt(EpicsSignalRO, "PvName_RBV")


class PvaPlugin_V26(
    PluginBase_V26, PvaPlugin_V25, version=(2, 6), version_of=PvaPlugin
):
    ...


class PvaPlugin_V31(
    PluginBase_V31, PvaPlugin_V26, version=(3, 1), version_of=PvaPlugin
):
    ...


class PvaPlugin_V33(
    PluginBase_V33, PvaPlugin_V31, version=(3, 3), version_of=PvaPlugin
):
    ...


class PvaPlugin_V34(
    PluginBase_V34, PvaPlugin_V33, version=(3, 4), version_of=PvaPlugin
):
    ...


# --- NDFFT ---


@register_plugin
class FFTPlugin(Device, version_type="ADCore"):
    "Serves as a base class for other versions"
    ...
    _default_suffix = "FFT1:"
    _suffix_re = r"FFT\d:"
    _plugin_type = "NDPluginFFT"


class FFTPlugin_V25(PluginBase_V25, FFTPlugin, version=(2, 5), version_of=FFTPlugin):
    fft_abs_value = Cpt(EpicsSignal, "FFTAbsValue")
    fft_direction = Cpt(
        SignalWithRBV,
        "FFTDirection",
        string=True,
        doc="0='Time to freq.' 1='Freq. to time'",
    )
    fft_freq_axis = Cpt(EpicsSignal, "FFTFreqAxis")
    fft_imaginary = Cpt(EpicsSignal, "FFTImaginary")
    fft_num_average = Cpt(SignalWithRBV, "FFTNumAverage")
    fft_num_averaged = Cpt(EpicsSignal, "FFTNumAveraged")
    fft_real = Cpt(EpicsSignal, "FFTReal")
    fft_reset_average = Cpt(
        EpicsSignal, "FFTResetAverage", string=True, doc="0='Done' 1='Reset'"
    )
    fft_suppress_dc = Cpt(
        SignalWithRBV, "FFTSuppressDC", string=True, doc="0='Disable' 1='Enable'"
    )
    fft_time_axis = Cpt(EpicsSignal, "FFTTimeAxis")
    fft_time_per_point = Cpt(SignalWithRBV, "FFTTimePerPoint")
    fft_time_per_point_link = Cpt(EpicsSignal, "FFTTimePerPointLink")
    fft_time_series = Cpt(EpicsSignal, "FFTTimeSeries")
    name_ = Cpt(EpicsSignal, "Name", string=True)


class FFTPlugin_V26(
    PluginBase_V26, FFTPlugin_V25, version=(2, 6), version_of=FFTPlugin
):
    ...


class FFTPlugin_V31(
    PluginBase_V31, FFTPlugin_V26, version=(3, 1), version_of=FFTPlugin
):
    ...


class FFTPlugin_V33(
    PluginBase_V33, FFTPlugin_V31, version=(3, 3), version_of=FFTPlugin
):
    ...


class FFTPlugin_V34(
    PluginBase_V34, FFTPlugin_V33, version=(3, 4), version_of=FFTPlugin
):
    ...


# --- NDScatter ---


@register_plugin
class ScatterPlugin(Device, version_type="ADCore"):
    "Serves as a base class for other versions"
    _default_suffix = "Scatter1:"
    _suffix_re = r"Scatter\d:"
    _plugin_type = "NDPluginScatter"


class ScatterPlugin_V31(
    PluginBase_V31, ScatterPlugin, version=(3, 1), version_of=ScatterPlugin
):
    scatter_method = Cpt(
        SignalWithRBV, "ScatterMethod", string=True, doc="0='Round robin'"
    )


class ScatterPlugin_V32(ScatterPlugin_V31, version=(3, 2), version_of=ScatterPlugin):
    ...


class ScatterPlugin_V33(
    PluginBase_V33, ScatterPlugin_V32, version=(3, 3), version_of=ScatterPlugin
):
    ...


class ScatterPlugin_V34(
    PluginBase_V34, ScatterPlugin_V33, version=(3, 4), version_of=ScatterPlugin
):
    ...


# --- NDPosPlugin ---


@register_plugin
class PosPlugin(Device, version_type="ADCore"):
    "Serves as a base class for other versions"
    _default_suffix = "Pos1:"
    _suffix_re = r"Pos\d:"
    _plugin_type = "NDPosPlugin"


class PosPluginPlugin_V25(
    PluginBase_V25, PosPlugin, version=(2, 5), version_of=PosPlugin
):
    delete = Cpt(EpicsSignal, "Delete", string=True, doc="")
    duplicate = Cpt(SignalWithRBV, "Duplicate")
    expected_id = Cpt(EpicsSignalRO, "ExpectedID_RBV")
    file_valid = Cpt(EpicsSignalRO, "FileValid_RBV", string=True, doc="0='No' 1='Yes'")
    filename = Cpt(SignalWithRBV, "Filename")
    id_difference = Cpt(SignalWithRBV, "IDDifference")
    id_name = Cpt(SignalWithRBV, "IDName", string=True)
    id_start = Cpt(SignalWithRBV, "IDStart")
    index = Cpt(EpicsSignalRO, "Index_RBV")
    missing = Cpt(SignalWithRBV, "Missing")
    mode = Cpt(SignalWithRBV, "Mode", string=True, doc="0='Discard' 1='Keep'")
    position_ = Cpt(EpicsSignalRO, "Position_RBV", string=True)
    qty = Cpt(EpicsSignalRO, "Qty_RBV")
    reset = Cpt(EpicsSignal, "Reset", string=True, doc="")
    running = Cpt(SignalWithRBV, "Running")


class PosPluginPlugin_V26(
    PluginBase_V26, PosPluginPlugin_V25, version=(2, 6), version_of=PosPlugin
):
    ...


class PosPluginPlugin_V31(
    PluginBase_V31, PosPluginPlugin_V26, version=(3, 1), version_of=PosPlugin
):
    ...


class PosPluginPlugin_V33(
    PluginBase_V33, PosPluginPlugin_V31, version=(3, 3), version_of=PosPlugin
):
    ...


class PosPluginPlugin_V34(
    PluginBase_V34, PosPluginPlugin_V33, version=(3, 4), version_of=PosPlugin
):
    ...


# --- NDCircularBuff ---


@register_plugin
class CircularBuffPlugin(Device, version_type="ADCore"):
    "Serves as a base class for other versions"
    _default_suffix = "CB1:"
    _suffix_re = r"CB\d:"
    _plugin_type = "NDPluginCircularBuff"


class CircularBuffPlugin_V22(
    PluginBase_V22, CircularBuffPlugin, version=(2, 2), version_of=CircularBuffPlugin
):
    actual_trigger_count = Cpt(EpicsSignalRO, "ActualTriggerCount_RBV")
    capture = Cpt(SignalWithRBV, "Capture")
    current_qty = Cpt(EpicsSignalRO, "CurrentQty_RBV")
    post_count = Cpt(SignalWithRBV, "PostCount")
    post_trigger_qty = Cpt(EpicsSignalRO, "PostTriggerQty_RBV")
    pre_count = Cpt(SignalWithRBV, "PreCount")
    preset_trigger_count = Cpt(SignalWithRBV, "PresetTriggerCount")
    status_message = Cpt(EpicsSignal, "StatusMessage", string=True)
    trigger_ = Cpt(SignalWithRBV, "Trigger")
    trigger_a = Cpt(SignalWithRBV, "TriggerA", string=True)
    trigger_a_val = Cpt(EpicsSignal, "TriggerAVal")
    trigger_b = Cpt(SignalWithRBV, "TriggerB", string=True)
    trigger_b_val = Cpt(EpicsSignal, "TriggerBVal")
    trigger_calc = Cpt(SignalWithRBV, "TriggerCalc")
    trigger_calc_val = Cpt(EpicsSignal, "TriggerCalcVal")

    array_size_xyz = DDC_EpicsSignalRO(
        ("array_size_x", "ArraySizeX_RBV"),
        ("array_size_y", "ArraySizeY_RBV"),
        ("array_size_z", "ArraySizeZ_RBV"),
    )


class CircularBuffPlugin_V25(
    PluginBase_V25,
    CircularBuffPlugin_V22,
    version=(2, 5),
    version_of=CircularBuffPlugin,
):
    ...


class CircularBuffPlugin_V26(
    PluginBase_V26,
    CircularBuffPlugin_V25,
    version=(2, 6),
    version_of=CircularBuffPlugin,
):
    ...


class CircularBuffPlugin_V31(
    PluginBase_V31,
    CircularBuffPlugin_V26,
    version=(3, 1),
    version_of=CircularBuffPlugin,
):
    ...


class CircularBuffPlugin_V33(
    PluginBase_V33,
    CircularBuffPlugin_V31,
    version=(3, 3),
    version_of=CircularBuffPlugin,
):
    ...


class CircularBuffPlugin_V34(
    PluginBase_V34,
    CircularBuffPlugin_V33,
    version=(3, 4),
    version_of=CircularBuffPlugin,
):
    flush_on_soft_trigger = Cpt(
        SignalWithRBV,
        "FlushOnSoftTrg",
        string=True,
        doc="0='OnNewImage' 1='Immediately'",
    )


# --- NDAttributeN ---


class AttributeNPlugin(Device, version_type="ADCore"):
    "Serves as a base class for other versions"
    ...


class AttributeNPlugin_V22(
    AttributeNPlugin, version=(2, 2), version_of=AttributeNPlugin
):
    attribute_name = Cpt(SignalWithRBV, "AttrName")
    ts_array_value = Cpt(EpicsSignal, "TSArrayValue")
    value_sum = Cpt(EpicsSignalRO, "ValueSum_RBV")
    value = Cpt(EpicsSignalRO, "Value_RBV")


class AttributeNPlugin_V26(
    AttributeNPlugin_V22, version=(2, 6), version_of=AttributeNPlugin
):
    ...


# --- NDAttrPlot ---


class AttrPlotPlugin(Device, version_type="ADCore"):
    "Serves as a base class for other versions"
    _plugin_type = "NDAttrPlot"


class AttrPlotPlugin_V31(
    PluginBase_V31, AttrPlotPlugin, version=(3, 1), version_of=AttrPlotPlugin
):
    npts = Cpt(EpicsSignal, "NPts")
    reset = Cpt(EpicsSignal, "Reset")


class AttrPlotPlugin_V33(
    PluginBase_V33, AttrPlotPlugin_V31, version=(3, 3), version_of=AttrPlotPlugin
):
    ...


class AttrPlotPlugin_V34(
    PluginBase_V34, AttrPlotPlugin_V33, version=(3, 4), version_of=AttrPlotPlugin
):
    ...


# --- NDTimeSeriesN ---


class TimeSeriesNPlugin(Device, version_type="ADCore"):
    "Serves as a base class for other versions"
    ...


class TimeSeriesNPlugin_V25(
    TimeSeriesNPlugin, version=(2, 5), version_of=TimeSeriesNPlugin
):
    name_ = Cpt(EpicsSignal, "Name", string=True)
    time_series = Cpt(EpicsSignal, "TimeSeries")


# --- NDTimeSeries ---


@register_plugin
class TimeSeriesPlugin(Device, version_type="ADCore"):
    "Serves as a base class for other versions"
    _plugin_type = "NDPluginTimeSeries"


class TimeSeriesPlugin_V25(
    PluginBase_V25, TimeSeriesPlugin, version=(2, 5), version_of=TimeSeriesPlugin
):
    ts_acquire = Cpt(EpicsSignal, "TSAcquire")
    ts_acquire_mode = Cpt(
        SignalWithRBV,
        "TSAcquireMode",
        string=True,
        doc="0='Fixed length' 1='Circ. buffer'",
    )
    ts_acquiring = Cpt(
        EpicsSignal, "TSAcquiring", string=True, doc="0='Done' 1='Acquiring'"
    )
    ts_averaging_time = Cpt(SignalWithRBV, "TSAveragingTime")
    ts_current_point = Cpt(EpicsSignal, "TSCurrentPoint")
    ts_elapsed_time = Cpt(EpicsSignal, "TSElapsedTime")
    ts_num_average = Cpt(EpicsSignal, "TSNumAverage")
    ts_num_points = Cpt(EpicsSignal, "TSNumPoints")
    ts_read = Cpt(EpicsSignal, "TSRead", string=True, doc="0='Done' 1='Read'")
    ts_time_axis = Cpt(EpicsSignal, "TSTimeAxis")
    ts_time_per_point = Cpt(SignalWithRBV, "TSTimePerPoint")
    ts_time_per_point_link = Cpt(EpicsSignal, "TSTimePerPointLink")
    ts_timestamp = Cpt(EpicsSignal, "TSTimestamp")


class TimeSeriesPlugin_V26(
    PluginBase_V26, TimeSeriesPlugin_V25, version=(2, 6), version_of=TimeSeriesPlugin
):
    ...


class TimeSeriesPlugin_V31(
    PluginBase_V31, TimeSeriesPlugin_V26, version=(3, 1), version_of=TimeSeriesPlugin
):
    ...


class TimeSeriesPlugin_V33(
    PluginBase_V33, TimeSeriesPlugin_V31, version=(3, 3), version_of=TimeSeriesPlugin
):
    ...


class TimeSeriesPlugin_V34(
    PluginBase_V34, TimeSeriesPlugin_V33, version=(3, 4), version_of=TimeSeriesPlugin
):
    ...


# --- NDCodec ---


@register_plugin
class CodecPlugin(Device, version_type="ADCore"):
    "Serves as a base class for other versions"
    _plugin_type = "NDPluginCodec"


class CodecPlugin_V34(
    PluginBase_V34, CodecPlugin, version=(3, 4), version_of=CodecPlugin
):
    blosc_compression_level = Cpt(SignalWithRBV, "BloscCLevel")
    blosc_compressor = Cpt(
        SignalWithRBV,
        "BloscCompressor",
        string=True,
        doc="0=BloscLZ 1=LZ4 2=LZ4HC 3=SNAPPY 4=ZLIB 5=ZSTD",
    )
    blosc_num_threads = Cpt(SignalWithRBV, "BloscNumThreads")
    blosc_shuffle = Cpt(
        SignalWithRBV, "BloscShuffle", string=True, doc="0=None 1=Bit 2=Byte"
    )
    codec_error = Cpt(EpicsSignal, "CodecError")
    codec_status = Cpt(
        EpicsSignal, "CodecStatus", string=True, doc="0=Success 1=Warning 2=Error"
    )
    comp_factor = Cpt(EpicsSignalRO, "CompFactor_RBV")
    compressor = Cpt(
        SignalWithRBV, "Compressor", string=True, doc="0=None 1=JPEG 2=Blosc"
    )
    jpeg_quality = Cpt(SignalWithRBV, "JPEGQuality")
    mode = Cpt(SignalWithRBV, "Mode", string=True, doc="0=Compress 1=Decompress")


@register_plugin
class AttributePlugin(Device, version_type="ADCore"):
    "Serves as a base class for other versions"
    _default_suffix = "Attr1:"
    _suffix_re = r"Attr\d:"
    _plugin_type = "NDPluginAttribute"


class AttributePlugin_V20(
    PluginBase_V20, AttributePlugin, version=(2, 0), version_of=AttributePlugin
):
    array_data = Cpt(EpicsSignalRO, "ArrayData_RBV")
    attribute_name = Cpt(SignalWithRBV, "AttrName")
    reset = Cpt(EpicsSignal, "Reset", string=True, doc="0='Done Reset' 1='Reset'")
    reset_array_counter = Cpt(EpicsSignal, "ResetArrayCounter")
    update = Cpt(
        EpicsSignal, "Update", string=True, doc="0='Done Update Array' 1='Update Array'"
    )
    update_period = Cpt(SignalWithRBV, "UpdatePeriod")
    value_sum = Cpt(EpicsSignalRO, "ValueSum_RBV")
    value = Cpt(EpicsSignalRO, "Value_RBV")


class AttributePlugin_V22(
    PluginBase_V22, AttributePlugin_V20, version=(2, 2), version_of=AttributePlugin
):
    array_data = None  # REMOVED
    attribute_name = None  # REMOVED
    reset_array_counter = None  # REMOVED
    ts_acquiring = Cpt(
        EpicsSignal, "TSAcquiring", string=True, doc="0='Done' 1='Acquiring'"
    )
    ts_control = Cpt(
        EpicsSignal, "TSControl", string=True, doc="0=Erase/Start 1=Start 2=Stop 3=Read"
    )
    ts_current_point = Cpt(EpicsSignal, "TSCurrentPoint")
    ts_num_points = Cpt(EpicsSignal, "TSNumPoints")
    ts_read = Cpt(EpicsSignal, "TSRead")
    update = None  # REMOVED
    update_period = None  # REMOVED
    value_sum = None  # REMOVED
    value = None  # REMOVED
    array_size_xyz = DDC_EpicsSignalRO(
        ("x", "ArraySizeX_RBV"),
        ("y", "ArraySizeY_RBV"),
        ("z", "ArraySizeZ_RBV"),
    )


class AttributePlugin_V25(
    PluginBase_V25, AttributePlugin_V22, version=(2, 5), version_of=AttributePlugin
):
    ...


class AttributePlugin_V26(
    PluginBase_V26, AttributePlugin_V25, version=(2, 6), version_of=AttributePlugin
):
    ts_acquiring = Cpt(
        EpicsSignal, "TSAcquiring", string=True, doc="0='Done' 1='Acquiring'"
    )
    ts_control = Cpt(
        EpicsSignal, "TSControl", string=True, doc="0=Erase/Start 1=Start 2=Stop 3=Read"
    )
    ts_current_point = Cpt(EpicsSignal, "TSCurrentPoint")
    ts_num_points = Cpt(EpicsSignal, "TSNumPoints")
    ts_read = Cpt(EpicsSignal, "TSRead")


class AttributePlugin_V31(
    PluginBase_V31, AttributePlugin_V26, version=(3, 1), version_of=AttributePlugin
):
    array_size_all = DDC_SignalWithRBV(
        ("size0", "ArraySize0"),
        ("size1", "ArraySize1"),
        ("size2", "ArraySize2"),
        ("size3", "ArraySize3"),
        ("size4", "ArraySize4"),
        ("size5", "ArraySize5"),
        ("size6", "ArraySize6"),
        ("size7", "ArraySize7"),
        ("size8", "ArraySize8"),
        ("size9", "ArraySize9"),
        doc="array_size",
    )


class AttributePlugin_V33(
    PluginBase_V33, AttributePlugin_V31, version=(3, 3), version_of=AttributePlugin
):
    ...


class AttributePlugin_V34(
    PluginBase_V34, AttributePlugin_V33, version=(3, 4), version_of=AttributePlugin
):
    ...


# --- NDGather / NDGatherN ---


@register_plugin
class GatherPlugin(PluginBase_V31, version=(3, 1), version_type="ADCore"):
    _default_suffix = "Gather:"
    _suffix_re = r"Gather\d:"
    _plugin_type = "NDPluginGather"


class GatherNPlugin(Device, version_type="ADCore"):
    "Serves as a base class for other versions"

    def __init__(self, *args, index, **kwargs):
        self.index = index
        super().__init__(*args, **kwargs)


class GatherNPlugin_V31(GatherNPlugin, version=(3, 1), version_of=GatherNPlugin):
    gather_array_address = FCpt(
        SignalWithRBV, "{self.prefix}NDArrayAddress_{self.index}"
    )
    gather_array_port = FCpt(
        SignalWithRBV, "{self.prefix}NDArrayPort_{self.index}", string=True
    )


def plugin_from_pvname(pv):
    """Get the plugin class from a pvname,
    using regular expressions defined in the classes (_suffix_re).
    """
    global _plugin_class

    for type_, cls in _plugin_class.items():
        if getattr(cls, "_suffix_re", None) is not None:
            m = re.search(cls._suffix_re, pv)
            if m:
                return cls

    return None


def get_areadetector_plugin_class(prefix, timeout=2.0):
    """Get an areadetector plugin class by supplying its PV prefix

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
    """
    from .. import cl

    cls = plugin_from_pvname(prefix)
    if cls is not None:
        return cls

    type_rbv = prefix + "PluginType_RBV"
    type_ = cl.caget(type_rbv, timeout=timeout)

    if type_ is None:
        raise ValueError("Unable to determine plugin type (caget timed out)")

    # HDF5 includes version number, remove it
    type_ = type_.split(" ")[0]

    try:
        return _plugin_class[type_]
    except KeyError:
        raise ValueError(
            "Unable to determine plugin type (PluginType={})" "".format(type_)
        )


def get_areadetector_plugin(prefix, **kwargs):
    """Get an instance of an areadetector plugin by supplying its PV prefix
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
    """

    cls = get_areadetector_plugin_class(prefix)
    if cls is None:
        raise ValueError("Unable to determine plugin type")

    return cls(prefix, **kwargs)
