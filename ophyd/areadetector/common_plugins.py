from ..device import Component as Cpt
from ..device import Device, create_device_from_components
from ..ophydobj import OphydObject, select_version
from . import plugins


class CommonPlugins(Device, version_type="ADCore"):
    ...


class CommonOverlayPlugin(Device, version_type="ADCore"):
    ...


class CommonAttributePlugin(Device, version_type="ADCore"):
    ...


class CommonROIStatPlugin(Device, version_type="ADCore"):
    ...


class CommonGatherPlugin(Device, version_type="ADCore"):
    ...


def _get_bases(cls, version):
    mixin_cls = select_version(cls, version)
    base_cls = select_version(plugins.PluginBase, version)
    if issubclass(mixin_cls, base_cls):
        return (mixin_cls,)

    return (mixin_cls, base_cls)


def _make_common_numbered(clsname, version, cpt_cls_base, bases, attr_prefix):
    try:
        cpt_cls = select_version(cpt_cls_base, version)
    except ValueError:
        return

    base_cls_base, plugin_base = bases
    bases = (base_cls_base,) + _get_bases(plugin_base, version)

    return create_device_from_components(
        name=clsname,
        base_class=bases,
        class_kwargs={"version_of": base_cls_base, "version": version},
        **{f"{attr_prefix}_{j}": Cpt(cpt_cls, f"{j}:") for j in range(1, 9)},
    )


def _make_common_gather(clsname, version):
    base_cls_base = plugins.GatherPlugin
    cpt_cls_base = plugins.GatherNPlugin

    try:
        cpt_cls = select_version(cpt_cls_base, version)
    except ValueError:
        return

    bases = (CommonGatherPlugin,) + _get_bases(base_cls_base, version)

    return create_device_from_components(
        name=clsname,
        base_class=bases,
        class_kwargs={"version_of": CommonGatherPlugin, "version": version},
        **{f"gather_{j}": Cpt(cpt_cls, "", index=j) for j in range(1, 9)},
    )


versions = [
    (1, 9, 1),
    (2, 0),
    (2, 1),
    (2, 2),
    (2, 3),
    (2, 4),
    (2, 5),
    (2, 6),
    (3, 1),
    (3, 2),
    (3, 3),
    (3, 4),
]


for version in versions:
    ver_string = "".join(str(_) for _ in version)
    _make_common_numbered(
        f"CommonOverlayPlugin_V{ver_string}",
        version,
        plugins.Overlay,
        (
            CommonOverlayPlugin,
            plugins.OverlayPlugin,
        ),
        "overlay",
    )
    _make_common_numbered(
        f"CommonAttributePlugin_V{ver_string}",
        version,
        plugins.AttributeNPlugin,
        (CommonAttributePlugin, plugins.AttributePlugin),
        "attr",
    )
    _make_common_numbered(
        f"CommonROIStatPlugin_V{ver_string}",
        version,
        plugins.ROIStatNPlugin,
        (CommonROIStatPlugin, plugins.ROIStatPlugin),
        "attr",
    )

    _make_common_gather(f"CommonGatherPlugin_V{ver_string}", version)


all_plugins = [
    ("attr1", CommonAttributePlugin, "Attr1:"),
    ("cb1", plugins.CircularBuffPlugin, "CB1:"),
    ("cc1", plugins.ColorConvPlugin, "CC1:"),
    ("cc2", plugins.ColorConvPlugin, "CC2:"),
    ("codec1", plugins.CodecPlugin, "Codec1:"),
    ("codec2", plugins.CodecPlugin, "Codec2:"),
    ("fft1", plugins.FFTPlugin, "FFT1:"),
    ("gather1", CommonGatherPlugin, "Gather1:"),
    ("hdf1", plugins.HDF5Plugin, "HDF1:"),
    ("jpeg1", plugins.JPEGPlugin, "JPEG1:"),
    ("kafka1", plugins.KafkaPlugin, "KAFKA1:"),
    ("magick1", plugins.MagickPlugin, "Magick1:"),
    ("netcdf1", plugins.NetCDFPlugin, "netCDF1:"),
    ("nexus1", plugins.NexusPlugin, "Nexus1:"),
    ("over1", CommonOverlayPlugin, "Over1:"),
    ("proc1", plugins.ProcessPlugin, "Proc1:"),
    ("proc1_tiff", plugins.TIFFPlugin, "Proc1:TIFF:"),
    ("roi1", plugins.ROIPlugin, "ROI1:"),
    ("roi2", plugins.ROIPlugin, "ROI2:"),
    ("roi3", plugins.ROIPlugin, "ROI3:"),
    ("roi4", plugins.ROIPlugin, "ROI4:"),
    ("roistat1", CommonROIStatPlugin, "ROIStat1:"),
    ("scatter1", plugins.ScatterPlugin, "Scatter1:"),
    ("stats1", plugins.StatsPlugin, "Stats1:"),
    ("stats1_ts", plugins.TimeSeriesPlugin, "Stats1:TS:"),
    ("stats2", plugins.StatsPlugin, "Stats2:"),
    ("stats2_ts", plugins.TimeSeriesPlugin, "Stats2:TS:"),
    ("stats3", plugins.StatsPlugin, "Stats3:"),
    ("stats3_ts", plugins.TimeSeriesPlugin, "Stats3:TS:"),
    ("stats4", plugins.StatsPlugin, "Stats4:"),
    ("stats4_ts", plugins.TimeSeriesPlugin, "Stats4:TS:"),
    ("stats5", plugins.StatsPlugin, "Stats5:"),
    ("stats5_ts", plugins.TimeSeriesPlugin, "Stats5:TS:"),
    ("tiff1", plugins.TIFFPlugin, "TIFF1:"),
    ("trans1", plugins.TransformPlugin, "Trans1:"),
]


common_plugins = {}


for version in versions:
    local_plugins = {}
    for attr, cls, suffix in all_plugins:
        if attr == "magick1" and version > (3, 0):
            continue
        elif attr.endswith("_ts") and version < (3, 3):
            continue
        elif attr == "fft1" and version < (3, 0):
            continue
        elif attr == "proc1_tiff" and version < (3, 3):
            continue
        elif attr == "attr1" and version < (2, 2):
            continue

        try:
            cls = select_version(cls, version)
        except ValueError:
            continue

        local_plugins[attr] = Cpt(cls, suffix)

    ver_string = "".join(str(_) for _ in version)
    class_name = f"CommonPlugins_V{ver_string}"

    common_plugins[class_name] = create_device_from_components(
        name=class_name,
        base_class=CommonPlugins,
        class_kwargs=dict(version=version, version_of=CommonPlugins),
        **local_plugins,
    )


versioned_plugins = {}


class PluginNamespace(OphydObject, version_type="ADCore"):
    """
    This is intended to be used with select_versions.

    This provides namespaces of plugins for a given version of Area Detector.

    Examples
    --------
    Access the StatsPlugin for Area Detector version 3.4.

    >>> select_version(PluginNamespace, (3, 4)).StatsPlugin
    ophyd.areadetector.plugins.StatsPlugin_V34
    """

    # This is implemented as an OphydObject in order to leverage OphydObject's
    # version-resolution class keyword arguments. But it should *not* be used
    # as a Device or Signal. It should be used with select_version as in the
    # example in the docstring.
    ...


for version in versions:
    local_plugins = {}
    for _, cls, _ in all_plugins:
        try:
            local_plugins[cls.__name__] = select_version(cls, version)
        except ValueError:
            continue
    ver_string = "".join(str(_) for _ in version)
    class_name = f"PluginNamespace_V{ver_string}"
    versioned_plugins[class_name] = type(
        class_name,
        (PluginNamespace,),
        local_plugins,
        version=version,
        version_of=PluginNamespace,
    )


globals().update(**common_plugins, **versioned_plugins)
del local_plugins
del version
del class_name
del suffix
del ver_string
del attr
del cls


__all__ = ["PluginNamespace", "CommonPlugins"]
