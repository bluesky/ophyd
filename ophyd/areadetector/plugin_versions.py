from .. import (Device, Component as Cpt)
from ..device import create_device_from_components

from . import new_plugins


class PluginVersions(Device):
    ...


def _select_version(cls, version):
    all_versions = cls._class_info_['versions']
    matched_version = max(ver for ver in all_versions if ver <= version)
    return all_versions[matched_version]


def _get_bases(cls, version):
    mixin_cls = _select_version(cls, version)
    base_cls = _select_version(new_plugins.PluginBase, version)
    if issubclass(mixin_cls, base_cls):
        return (mixin_cls, )

    return (mixin_cls, base_cls)


def _make_common_overlay(clsname, version):
    cpt_cls = _select_version(new_plugins.Overlay, version)
    bases = _get_bases(new_plugins.OverlayPlugin, version)

    return create_device_from_components(
        name=clsname,
        base_class=bases + (CommonOverlayPlugin, ),
        overlay_1=Cpt(cpt_cls, '1:'),
        overlay_2=Cpt(cpt_cls, '2:'),
        overlay_3=Cpt(cpt_cls, '3:'),
        overlay_4=Cpt(cpt_cls, '4:'),
        overlay_5=Cpt(cpt_cls, '5:'),
        overlay_6=Cpt(cpt_cls, '6:'),
        overlay_7=Cpt(cpt_cls, '7:'),
        overlay_8=Cpt(cpt_cls, '8:'),
    )


def _make_common_attribute(clsname, version):
    cpt_cls = _select_version(new_plugins.AttributeNPlugin, version)
    bases = _get_bases(new_plugins.AttributePlugin, version)

    return create_device_from_components(
        name=clsname,
        base_class=bases + (CommonAttributePlugin, ),
        attr_1=Cpt(cpt_cls, '1:'),
        attr_2=Cpt(cpt_cls, '2:'),
        attr_3=Cpt(cpt_cls, '3:'),
        attr_4=Cpt(cpt_cls, '4:'),
        attr_5=Cpt(cpt_cls, '5:'),
        attr_6=Cpt(cpt_cls, '6:'),
        attr_7=Cpt(cpt_cls, '7:'),
        attr_8=Cpt(cpt_cls, '8:'),
    )


def _make_common_roistat(clsname, version):
    cpt_cls = _select_version(new_plugins.ROIStatNPlugin, version)
    bases = _get_bases(new_plugins.ROIStatPlugin, version)

    return create_device_from_components(
        name=clsname,
        base_class=bases + (CommonROIStatPlugin, ),
        roistat_1=Cpt(cpt_cls, '1:'),
        roistat_2=Cpt(cpt_cls, '2:'),
        roistat_3=Cpt(cpt_cls, '3:'),
        roistat_4=Cpt(cpt_cls, '4:'),
        roistat_5=Cpt(cpt_cls, '5:'),
        roistat_6=Cpt(cpt_cls, '6:'),
        roistat_7=Cpt(cpt_cls, '7:'),
        roistat_8=Cpt(cpt_cls, '8:'),
    )


def _make_common_gather(clsname, version):
    cpt_cls = _select_version(new_plugins.GatherNPlugin, version)
    bases = _get_bases(new_plugins.GatherPlugin, version)

    return create_device_from_components(
        name=clsname,
        base_class=bases + (CommonGatherPlugin, ),
        gather_1=Cpt(cpt_cls, '', index=1),
        gather_2=Cpt(cpt_cls, '', index=2),
        gather_3=Cpt(cpt_cls, '', index=3),
        gather_4=Cpt(cpt_cls, '', index=4),
        gather_5=Cpt(cpt_cls, '', index=5),
        gather_6=Cpt(cpt_cls, '', index=6),
        gather_7=Cpt(cpt_cls, '', index=7),
        gather_8=Cpt(cpt_cls, '', index=8),
    )


class CommonOverlayPlugin(Device):
    ...


class CommonAttributePlugin(Device):
    ...


class CommonROIStatPlugin(Device):
    ...


class CommonGatherPlugin(Device):
    ...


class PluginVersions_V191(PluginVersions, version=(1, 9, 1), version_of=PluginVersions):
    ColorConvPlugin = new_plugins.ColorConvPlugin
    CommonOverlayPlugin = CommonOverlayPlugin
    HDF5Plugin = new_plugins.HDF5Plugin
    JPEGPlugin = new_plugins.JPEGPlugin
    MagickPlugin = new_plugins.MagickPlugin
    NetCDFPlugin = new_plugins.NetCDFPlugin
    NexusPlugin = new_plugins.NexusPlugin
    ProcessPlugin = new_plugins.ProcessPlugin
    ROIPlugin = new_plugins.ROIPlugin
    StatsPlugin = new_plugins.StatsPlugin
    TIFFPlugin = new_plugins.TIFFPlugin
    TransformPlugin = new_plugins.TransformPlugin


class PluginVersions_V20(PluginVersions, version=(2, 0), version_of=PluginVersions):
    ColorConvPlugin = new_plugins.ColorConvPlugin_V20
    CommonOverlayPlugin = _make_common_overlay('CommonOverlayPlugin_V20', (2, 0))
    HDF5Plugin = new_plugins.HDF5Plugin_V20
    JPEGPlugin = new_plugins.JPEGPlugin_V20
    MagickPlugin = new_plugins.MagickPlugin_V20
    NetCDFPlugin = new_plugins.NetCDFPlugin_V20
    NexusPlugin = new_plugins.NexusPlugin_V20
    ProcessPlugin = new_plugins.ProcessPlugin_V20
    ROIPlugin = new_plugins.ROIPlugin_V20
    StatsPlugin = new_plugins.StatsPlugin_V20
    TIFFPlugin = new_plugins.TIFFPlugin_V20
    TransformPlugin = new_plugins.TransformPlugin_V20


class PluginVersions_V21(PluginVersions, version=(2, 1), version_of=PluginVersions):
    ColorConvPlugin = new_plugins.ColorConvPlugin_V20
    CommonOverlayPlugin = _make_common_overlay('CommonOverlayPlugin_V21', (2, 1))
    HDF5Plugin = new_plugins.HDF5Plugin_V21
    JPEGPlugin = new_plugins.JPEGPlugin_V21
    MagickPlugin = new_plugins.MagickPlugin_V21
    NetCDFPlugin = new_plugins.NetCDFPlugin_V21
    NexusPlugin = new_plugins.NexusPlugin_V21
    ProcessPlugin = new_plugins.ProcessPlugin_V20
    ROIPlugin = new_plugins.ROIPlugin_V20
    StatsPlugin = new_plugins.StatsPlugin_V20
    TIFFPlugin = new_plugins.TIFFPlugin_V21
    TransformPlugin = new_plugins.TransformPlugin_V21


class PluginVersions_V22(PluginVersions, version=(2, 2), version_of=PluginVersions):
    CircularBuffPlugin = new_plugins.CircularBuffPlugin_V22
    ColorConvPlugin = new_plugins.ColorConvPlugin_V22
    CommonAttributePlugin = _make_common_attribute('CommonAttributePlugin_V22', (2, 2))
    CommonOverlayPlugin = _make_common_overlay('CommonOverlayPlugin_V22', (2, 2))
    CommonROIStatPlugin = _make_common_roistat('CommonROIStatPlugin_V22', (2, 2))
    HDF5Plugin = new_plugins.HDF5Plugin_V22
    JPEGPlugin = new_plugins.JPEGPlugin_V22
    MagickPlugin = new_plugins.MagickPlugin_V22
    NetCDFPlugin = new_plugins.NetCDFPlugin_V22
    NexusPlugin = new_plugins.NexusPlugin_V22
    ProcessPlugin = new_plugins.ProcessPlugin_V22
    ROIPlugin = new_plugins.ROIPlugin_V22
    StatsPlugin = new_plugins.StatsPlugin_V22
    TIFFPlugin = new_plugins.TIFFPlugin_V22
    TransformPlugin = new_plugins.TransformPlugin_V22


class PluginVersions_V23(PluginVersions, version=(2, 3), version_of=PluginVersions):
    CircularBuffPlugin = new_plugins.CircularBuffPlugin_V22
    ColorConvPlugin = new_plugins.ColorConvPlugin_V22
    CommonAttributePlugin = _make_common_attribute('CommonAttributePlugin_V23', (2, 3))
    CommonOverlayPlugin = _make_common_overlay('CommonOverlayPlugin_V23', (2, 3))
    CommonROIStatPlugin = _make_common_roistat('CommonROIStatPlugin_V23', (2, 3))
    HDF5Plugin = new_plugins.HDF5Plugin_V22
    JPEGPlugin = new_plugins.JPEGPlugin_V22
    MagickPlugin = new_plugins.MagickPlugin_V22
    NetCDFPlugin = new_plugins.NetCDFPlugin_V22
    NexusPlugin = new_plugins.NexusPlugin_V22
    ProcessPlugin = new_plugins.ProcessPlugin_V22
    ROIPlugin = new_plugins.ROIPlugin_V22
    StatsPlugin = new_plugins.StatsPlugin_V22
    TIFFPlugin = new_plugins.TIFFPlugin_V22
    TransformPlugin = new_plugins.TransformPlugin_V22


class PluginVersions_V24(PluginVersions, version=(2, 4), version_of=PluginVersions):
    CircularBuffPlugin = new_plugins.CircularBuffPlugin_V22
    ColorConvPlugin = new_plugins.ColorConvPlugin_V22
    CommonAttributePlugin = _make_common_attribute('CommonAttributePlugin_V24', (2, 4))
    CommonOverlayPlugin = _make_common_overlay('CommonOverlayPlugin_V24', (2, 4))
    CommonROIStatPlugin = _make_common_roistat('CommonROIStatPlugin_V24', (2, 4))
    HDF5Plugin = new_plugins.HDF5Plugin_V22
    JPEGPlugin = new_plugins.JPEGPlugin_V22
    MagickPlugin = new_plugins.MagickPlugin_V22
    NetCDFPlugin = new_plugins.NetCDFPlugin_V22
    NexusPlugin = new_plugins.NexusPlugin_V22
    ProcessPlugin = new_plugins.ProcessPlugin_V22
    ROIPlugin = new_plugins.ROIPlugin_V22
    StatsPlugin = new_plugins.StatsPlugin_V22
    TIFFPlugin = new_plugins.TIFFPlugin_V22
    TransformPlugin = new_plugins.TransformPlugin_V22


class PluginVersions_V25(PluginVersions, version=(2, 5), version_of=PluginVersions):
    CircularBuffPlugin = new_plugins.CircularBuffPlugin_V22
    ColorConvPlugin = new_plugins.ColorConvPlugin_V22
    CommonAttributePlugin = _make_common_attribute('CommonAttributePlugin_V25', (2, 5))
    CommonOverlayPlugin = _make_common_overlay('CommonOverlayPlugin_V25', (2, 5))
    CommonROIStatPlugin = _make_common_roistat('CommonROIStatPlugin_V25', (2, 5))
    HDF5Plugin = new_plugins.HDF5Plugin_V25
    JPEGPlugin = new_plugins.JPEGPlugin_V22
    MagickPlugin = new_plugins.MagickPlugin_V22
    NetCDFPlugin = new_plugins.NetCDFPlugin_V22
    NexusPlugin = new_plugins.NexusPlugin_V22
    ProcessPlugin = new_plugins.ProcessPlugin_V22
    ROIPlugin = new_plugins.ROIPlugin_V22
    StatsPlugin = new_plugins.StatsPlugin_V25
    TIFFPlugin = new_plugins.TIFFPlugin_V22
    TransformPlugin = new_plugins.TransformPlugin_V22


class PluginVersions_V26(PluginVersions, version=(2, 6), version_of=PluginVersions):
    CircularBuffPlugin = new_plugins.CircularBuffPlugin_V26
    ColorConvPlugin = new_plugins.ColorConvPlugin_V26
    CommonAttributePlugin = _make_common_attribute('CommonAttributePlugin_V26', (2, 6))
    CommonOverlayPlugin = _make_common_overlay('CommonOverlayPlugin_V26', (2, 6))
    CommonROIStatPlugin = _make_common_roistat('CommonROIStatPlugin_V26', (2, 6))
    HDF5Plugin = new_plugins.HDF5Plugin_V26
    JPEGPlugin = new_plugins.JPEGPlugin_V26
    MagickPlugin = new_plugins.MagickPlugin_V26
    NetCDFPlugin = new_plugins.NetCDFPlugin_V26
    NexusPlugin = new_plugins.NexusPlugin_V26
    ProcessPlugin = new_plugins.ProcessPlugin_V26
    ROIPlugin = new_plugins.ROIPlugin_V26
    StatsPlugin = new_plugins.StatsPlugin_V26
    TIFFPlugin = new_plugins.TIFFPlugin_V26
    TransformPlugin = new_plugins.TransformPlugin_V26


class PluginVersions_V31(PluginVersions, version=(3, 1), version_of=PluginVersions):
    CircularBuffPlugin = new_plugins.CircularBuffPlugin_V31
    ColorConvPlugin = new_plugins.ColorConvPlugin_V31
    CommonAttributePlugin = _make_common_attribute('CommonAttributePlugin_V31', (3, 1))
    CommonGatherPlugin = _make_common_gather('CommonGatherPlugin_V31', (3, 1))
    CommonOverlayPlugin = _make_common_overlay('CommonOverlayPlugin_V31', (3, 1))
    CommonROIStatPlugin = _make_common_roistat('CommonROIStatPlugin_V31', (3, 1))
    FFTPlugin = new_plugins.FFTPlugin_V31
    HDF5Plugin = new_plugins.HDF5Plugin_V31
    JPEGPlugin = new_plugins.JPEGPlugin_V31
    NetCDFPlugin = new_plugins.NetCDFPlugin_V31
    NexusPlugin = new_plugins.NexusPlugin_V31
    ProcessPlugin = new_plugins.ProcessPlugin_V31
    ROIPlugin = new_plugins.ROIPlugin_V31
    ScatterPlugin = new_plugins.ScatterPlugin_V31
    StatsPlugin = new_plugins.StatsPlugin_V31
    TIFFPlugin = new_plugins.TIFFPlugin_V31
    TransformPlugin = new_plugins.TransformPlugin_V31


class PluginVersions_V32(PluginVersions, version=(3, 2), version_of=PluginVersions):
    CircularBuffPlugin = new_plugins.CircularBuffPlugin_V31
    ColorConvPlugin = new_plugins.ColorConvPlugin_V31
    CommonAttributePlugin = _make_common_attribute('CommonAttributePlugin_V32', (3, 2))
    CommonGatherPlugin = _make_common_gather('CommonGatherPlugin_V32', (3, 2))
    CommonOverlayPlugin = _make_common_overlay('CommonOverlayPlugin_V32', (3, 2))
    CommonROIStatPlugin = _make_common_roistat('CommonROIStatPlugin_V32', (3, 2))
    FFTPlugin = new_plugins.FFTPlugin_V31
    HDF5Plugin = new_plugins.HDF5Plugin_V32
    JPEGPlugin = new_plugins.JPEGPlugin_V31
    NetCDFPlugin = new_plugins.NetCDFPlugin_V31
    NexusPlugin = new_plugins.NexusPlugin_V31
    ProcessPlugin = new_plugins.ProcessPlugin_V31
    ROIPlugin = new_plugins.ROIPlugin_V31
    ScatterPlugin = new_plugins.ScatterPlugin_V32
    StatsPlugin = new_plugins.StatsPlugin_V32
    TIFFPlugin = new_plugins.TIFFPlugin_V31
    TransformPlugin = new_plugins.TransformPlugin_V31


class PluginVersions_V33(PluginVersions, version=(3, 3), version_of=PluginVersions):
    CircularBuffPlugin = new_plugins.CircularBuffPlugin_V33
    ColorConvPlugin = new_plugins.ColorConvPlugin_V33
    CommonAttributePlugin = _make_common_attribute('CommonAttributePlugin_V33', (3, 3))
    CommonGatherPlugin = _make_common_gather('CommonGatherPlugin_V33', (3, 3))
    CommonOverlayPlugin = _make_common_overlay('CommonOverlayPlugin_V33', (3, 3))
    CommonROIStatPlugin = _make_common_roistat('CommonROIStatPlugin_V33', (3, 3))
    FFTPlugin = new_plugins.FFTPlugin_V33
    HDF5Plugin = new_plugins.HDF5Plugin_V33
    JPEGPlugin = new_plugins.JPEGPlugin_V33
    NetCDFPlugin = new_plugins.NetCDFPlugin_V33
    NexusPlugin = new_plugins.NexusPlugin_V33
    ProcessPlugin = new_plugins.ProcessPlugin_V33
    ROIPlugin = new_plugins.ROIPlugin_V33
    ScatterPlugin = new_plugins.ScatterPlugin_V33
    StatsPlugin = new_plugins.StatsPlugin_V33
    TIFFPlugin = new_plugins.TIFFPlugin_V33
    TimeSeriesPlugin = new_plugins.TimeSeriesPlugin_V33
    TransformPlugin = new_plugins.TransformPlugin_V33


class PluginVersions_V34(PluginVersions, version=(3, 4), version_of=PluginVersions):
    CircularBuffPlugin = new_plugins.CircularBuffPlugin_V34
    CodecPlugin = new_plugins.CodecPlugin_V34
    ColorConvPlugin = new_plugins.ColorConvPlugin_V34
    CommonAttributePlugin = _make_common_attribute('CommonAttributePlugin_V34', (3, 4))
    CommonGatherPlugin = _make_common_gather('CommonGatherPlugin_V34', (3, 4))
    CommonOverlayPlugin = _make_common_overlay('CommonOverlayPlugin_V34', (3, 4))
    CommonROIStatPlugin = _make_common_roistat('CommonROIStatPlugin_V34', (3, 4))
    FFTPlugin = new_plugins.FFTPlugin_V34
    HDF5Plugin = new_plugins.HDF5Plugin_V34
    JPEGPlugin = new_plugins.JPEGPlugin_V34
    NetCDFPlugin = new_plugins.NetCDFPlugin_V34
    NexusPlugin = new_plugins.NexusPlugin_V34
    ProcessPlugin = new_plugins.ProcessPlugin_V34
    ROIPlugin = new_plugins.ROIPlugin_V34
    ScatterPlugin = new_plugins.ScatterPlugin_V34
    StatsPlugin = new_plugins.StatsPlugin_V34
    TIFFPlugin = new_plugins.TIFFPlugin_V34
    TimeSeriesPlugin = new_plugins.TimeSeriesPlugin_V34
    TransformPlugin = new_plugins.TransformPlugin_V34
