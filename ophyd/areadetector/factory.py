from .. import Component as Cpt
from . import (SingleTrigger, ImagePlugin, StatsPlugin, TransformPlugin,
               ROIPlugin, ProcessPlugin, HDF5Plugin, TIFFPlugin)
from .filestore_mixins import (FileStoreTIFFIterativeWrite,
                               FileStoreHDF5IterativeWrite)


class TIFFPluginWithFileStore(TIFFPlugin, FileStoreTIFFIterativeWrite):
    ...

class HDF5PluginWithFileStore(HDF5Plugin, FileStoreHDF5IterativeWrite):
    ...


def assemble_AD(hardware, pv, name, *,
                write_path_template, root, fs, read_path_template=None):
    """
    Assemble AreaDetector components with commonly useful defaults.

    Parameters
    ----------
    hardware : class
        e.g., ``SimDetector``
    pv : string
    name : string
    fs : FileStore
    write_path_template : string
        e.g., ``/PATH/TO/DATA/%Y/%m/%d/``
    root : string
        subset of write_path_template, e.g. ``/PATH/TO``, indicating which
        parts of the path are only incidental (not semantic) and need not be
        retained if the files are moved
    read_path_template : string, optional
        Use this if the path where the files will be read is different than the
        path where they are written, due to different mounts. None by default.

    Returns
    -------
    detector : Device
        instance of a custom-built class pre-configured with commonly useful
        defaults
    """
    plugins = dict(
        hdf5 = Cpt(HDF5PluginWithFileStore,
                   suffix='HDF1:',
                   write_path_template=write_path_template,
                   root=root,
                   fs=fs),

        image = Cpt(ImagePlugin, 'image1:'),

        proc1 = Cpt(ProcessPlugin, 'Proc1:'),

        roi1 = Cpt(ROIPlugin, 'ROI1:'),
        roi2 = Cpt(ROIPlugin, 'ROI2:'),
        roi3 = Cpt(ROIPlugin, 'ROI3:'),
        roi4 = Cpt(ROIPlugin, 'ROI4:'),

        stats1 = Cpt(StatsPlugin, 'Stats1:'),
        stats2 = Cpt(StatsPlugin, 'Stats2:'),
        stats3 = Cpt(StatsPlugin, 'Stats3:'),
        stats4 = Cpt(StatsPlugin, 'Stats4:'),
        stats5 = Cpt(StatsPlugin, 'Stats5:'),

        tiff = Cpt(TIFFPluginWithFileStore,
                   suffix='TIFF:',
                   write_path_template=write_path_template,
                   root=root,
                   fs=fs),

        trans1 = Cpt(TransformPlugin, 'Trans1:'),
    )
    cls = type('FactoryBuiltDetector', (SingleTrigger, hardware), plugins)
    instance = cls(pv, name=name)
    instance.read_attrs = ['hdf5']

    # Do not enable the plugins when staged.
    # Users can reinstate auto-enabling easily by calling, for example,
    # `instance.hdf5.ensure_enabled()`.
    for attr in plugins:
        getattr(instance, attr).stage_sigs.pop('enabled')
    instance.read_attrs = ['hdf5']
    # TODO add stats totals
    instance.hdf5.read_attrs = []
