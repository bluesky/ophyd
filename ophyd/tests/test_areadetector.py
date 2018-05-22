import time
import logging
import pytest
from io import StringIO
from pathlib import PurePath, Path
from ophyd.ophydobj import Kind
from ophyd import (SimDetector, SingleTrigger, Component,
                   DynamicDeviceComponent)
from ophyd.areadetector.plugins import (ImagePlugin, StatsPlugin,
                                        ColorConvPlugin,
                                        ProcessPlugin, OverlayPlugin,
                                        ROIPlugin, TransformPlugin,
                                        NetCDFPlugin, TIFFPlugin, JPEGPlugin,
                                        HDF5Plugin,
                                        MagickPlugin)

from ophyd.areadetector.filestore_mixins import (
    FileStoreTIFF, FileStoreIterativeWrite,
    FileStoreHDF5)

# we do not have nexus installed on our test IOC
# from ophyd.areadetector.plugins import NexusPlugin
from ophyd.areadetector.plugins import PluginBase
from ophyd.areadetector.util import stub_templates
from ophyd.device import (Component as Cpt, )
import uuid
import os

logger = logging.getLogger(__name__)

prefix = 'XF:31IDA-BI{Cam:Tbl}'
ad_path = '/epics/support/areaDetector/1-9-1/ADApp/Db/'


class DummyFS:
    def __init__(self):
        self.resource = {}
        self.datum = {}
        self.datum_by_resource = {}

    def insert_resource(self, spec, resource_path, resource_kwargs, root=None,
                        path_semantics='posix', uid=None, run_start=None,
                        ignore_duplicate_error=False):
        self.resource[uid] = {'spec': spec,
                              'resource_path': resource_path,
                              'root': root,
                              'resource_kwargs': resource_kwargs,
                              'uid': uid,
                              'path_semantics': path_semantics}
        self.datum_by_resource[uid] = []
        return uid

    def register_resource(self, spec, root, rpath, rkwargs,
                          path_semantics='posix', run_start=None):

        uid = str(uuid.uuid4())
        return self.insert_resource(spec, rpath, rkwargs, root=root,
                                    path_semantics=path_semantics,
                                    uid=uid, run_start=run_start)

    def register_datum(self, resource_uid, datum_kwargs):
        datum_id = str(uuid.uuid4())
        return self.insert_datum(resource_uid, datum_id, datum_kwargs)

    def insert_datum(self, resource, datum_id, datum_kwargs,
                     ignore_duplicate_error=False):
        datum = {'resource': resource,
                 'datum_id': datum_id,
                 'datum_kwargs': datum_kwargs}
        self.datum_by_resource[resource].append(datum)
        self.datum[datum_id] = datum
        return datum_id


# lifted from soft-matter/pims source
def _recursive_subclasses(cls):
    "Return all subclasses (and their subclasses, etc.)."
    # Source: http://stackoverflow.com/a/3862957/1221924
    return (cls.__subclasses__() +
            [g for s in cls.__subclasses__()
             for g in _recursive_subclasses(s)])


def test_basic():
    class MyDetector(SingleTrigger, SimDetector):
        tiff1 = Cpt(TIFFPlugin, 'TIFF1:')

    det = MyDetector(prefix, name='test')
    det.wait_for_connection()
    det.stage()
    st = det.trigger()
    while not st.done:
        time.sleep(.1)
    det.unstage()


def test_stubbing():
    try:
        for line in stub_templates(ad_path):
            logger.debug('Stub line: %s', line)
    except OSError:
        # self.fail('AreaDetector db path needed to run test')
        pass


def test_detector():
    det = SimDetector(prefix, name='test')

    det.find_signal('a', f=StringIO())
    det.find_signal('a', use_re=True, f=StringIO())
    det.find_signal('a', case_sensitive=True, f=StringIO())
    det.find_signal('a', use_re=True, case_sensitive=True, f=StringIO())
    det.component_names
    det.report

    cam = det.cam

    cam.image_mode.put('Single')
    # plugins don't live on detectors now:
    # det.image1.enable.put('Enable')
    cam.array_callbacks.put('Enable')

    det.get()
    st = det.trigger()
    repr(st)
    det.read()

    # values = tuple(det.gain_xy.get())
    cam.gain_xy.put(cam.gain_xy.get(), wait=True)

    # fail when only specifying x
    with pytest.raises(ValueError):
        cam.gain_xy.put((0.0, ), wait=True)

    det.describe()
    det.report


def test_tiff_plugin():
    # det = AreaDetector(prefix)
    class TestDet(SimDetector):
        p = Cpt(TIFFPlugin, 'TIFF1:')

    det = TestDet(prefix, name='test')
    plugin = det.p

    plugin.file_template.put('%s%s_%3.3d.tif')

    plugin.array_pixels
    plugin


def test_hdf5_plugin():

    class MyDet(SimDetector):
        p = Cpt(HDF5Plugin, suffix='HDF1:')

    d = MyDet(prefix, name='d')
    d.p.file_path.put('/tmp')
    d.p.file_name.put('--')
    d.p.warmup()
    d.stage()
    print(d.p.read_configuration())
    d.p.describe_configuration()
    d.unstage()


def test_subclass():
    class MyDetector(SimDetector):
        tiff1 = Cpt(TIFFPlugin, 'TIFF1:')

    det = MyDetector(prefix, name='test')
    det.wait_for_connection()

    print(det.describe())
    print(det.tiff1.capture.describe())


def test_getattr():
    class MyDetector(SimDetector):
        tiff1 = Cpt(TIFFPlugin, 'TIFF1:')

    det = MyDetector(prefix, name='test')
    assert getattr(det, 'tiff1.name') == det.tiff1.name
    assert getattr(det, 'tiff1') is det.tiff1
    # raise
    # TODO subclassing issue


def test_invalid_plugins():
    class MyDetector(SingleTrigger, SimDetector):
        tiff1 = Cpt(TIFFPlugin, 'TIFF1:')
        stats1 = Cpt(StatsPlugin, 'Stats1:')

    det = MyDetector(prefix, name='test')
    det.wait_for_connection()
    det.tiff1.nd_array_port.put(det.cam.port_name.get())
    det.stats1.nd_array_port.put('AARDVARK')

    with pytest.raises(RuntimeError):
        det.stage()

    with pytest.raises(RuntimeError):
        det.validate_asyn_ports()

    assert ['AARDVARK'] == det.missing_plugins()


def test_validete_plugins_no_portname():
    class MyDetector(SingleTrigger, SimDetector):
        roi1 = Cpt(ROIPlugin, 'ROI1:')
        over1 = Cpt(OverlayPlugin, 'Over1:')

    det = MyDetector(prefix, name='test')

    det.roi1.nd_array_port.put(det.cam.port_name.get())
    det.over1.nd_array_port.put(det.roi1.port_name.get())

    det.validate_asyn_ports()


def test_get_plugin_by_asyn_port():
    class MyDetector(SingleTrigger, SimDetector):
        tiff1 = Cpt(TIFFPlugin, 'TIFF1:')
        stats1 = Cpt(StatsPlugin, 'Stats1:')
        roi1 = Cpt(ROIPlugin, 'ROI1:')

    det = MyDetector(prefix, name='test')

    det.tiff1.nd_array_port.put(det.cam.port_name.get())
    det.roi1.nd_array_port.put(det.cam.port_name.get())
    det.stats1.nd_array_port.put(det.roi1.port_name.get())

    det.validate_asyn_ports()

    assert det.tiff1 is det.get_plugin_by_asyn_port(det.tiff1.port_name.get())
    assert det.cam is det.get_plugin_by_asyn_port(det.cam.port_name.get())
    assert det.roi1 is det.get_plugin_by_asyn_port(det.roi1.port_name.get())


def test_read_configuration_smoke():
    class MyDetector(SingleTrigger, SimDetector):
        stats1 = Cpt(StatsPlugin, 'Stats1:')
        proc1 = Cpt(ProcessPlugin, 'Proc1:')
        roi1 = Cpt(ROIPlugin, 'ROI1:')

    det = MyDetector(prefix, name='test')
    det.proc1.nd_array_port.put(det.cam.port_name.get())
    det.roi1.nd_array_port.put(det.proc1.port_name.get())
    det.stats1.nd_array_port.put(det.roi1.port_name.get())
    # smoke test
    det.stage()
    conf = det.stats1.read_configuration()
    desc = det.stats1.describe_configuration()
    det.unstage()
    for k in conf:
        assert k in desc

    assert len(conf) > 0
    assert len(conf) == len(desc)
    assert set(conf) == set(desc)


def test_str_smoke():
    class MyDetector(SingleTrigger, SimDetector):
        stats1 = Cpt(StatsPlugin, 'Stats1:')
        proc1 = Cpt(ProcessPlugin, 'Proc1:')
        roi1 = Cpt(ROIPlugin, 'ROI1:')

    det = MyDetector(prefix, name='test')
    det.read_attrs = ['stats1']
    det.stats1.read_attrs = ['mean_value']
    det.stats1.mean_value.kind = Kind.hinted

    str(det)


def test_default_configuration_smoke():
    class MyDetector(SimDetector):
        imageplugin = Cpt(ImagePlugin, ImagePlugin._default_suffix)
        statsplugin = Cpt(StatsPlugin, StatsPlugin._default_suffix)
        colorconvplugin = Cpt(ColorConvPlugin, ColorConvPlugin._default_suffix)
        processplugin = Cpt(ProcessPlugin, ProcessPlugin._default_suffix)
        overlayplugin = Cpt(OverlayPlugin, OverlayPlugin._default_suffix)
        roiplugin = Cpt(ROIPlugin, ROIPlugin._default_suffix)
        transformplugin = Cpt(TransformPlugin, TransformPlugin._default_suffix)
        netcdfplugin = Cpt(NetCDFPlugin, NetCDFPlugin._default_suffix)
        tiffplugin = Cpt(TIFFPlugin, TIFFPlugin._default_suffix)
        jpegplugin = Cpt(JPEGPlugin, JPEGPlugin._default_suffix)
        # nexusplugin = Cpt(NexusPlugin, NexusPlugin._default_suffix)
        hdf5plugin = Cpt(HDF5Plugin, HDF5Plugin._default_suffix)
        magickplugin = Cpt(MagickPlugin, MagickPlugin._default_suffix)

    d = MyDetector(prefix, name='d')
    d.stage()
    {n: getattr(d, n).read_configuration() for n in d.component_names}
    {n: getattr(d, n).describe_configuration() for n in d.component_names}
    d.unstage()


@pytest.mark.parametrize('plugin',
                         _recursive_subclasses(PluginBase))
def test_default_configuration_attrs(plugin):
    for k in plugin._default_configuration_attrs:
        assert hasattr(plugin, k)
        assert isinstance(getattr(plugin, k),
                          (Component, DynamicDeviceComponent))


@pytest.mark.parametrize('root,wpath,rpath,check_files',
                         ((None, '/data/%Y/%m/%d', None, False),
                          (None, '/data/%Y/%m/%d', None, False),
                          ('/data', '%Y/%m/%d', None, False),
                          ('/data', '/data/%Y/%m/%d', '%Y/%m/%d', False),
                          ('/', '/data/%Y/%m/%d', None, False),
                          ('/tmp/data', '/data/%Y/%m/%d', '%Y/%m/%d', True)
                          ))
def test_fstiff_plugin(root, wpath, rpath, check_files):
    fs = DummyFS()
    fs2 = DummyFS()
    if check_files:
        fh = pytest.importorskip('databroker.assets.handlers')

    class FS_tiff(TIFFPlugin, FileStoreTIFF,
                  FileStoreIterativeWrite):
        pass

    class MyDetector(SingleTrigger, SimDetector):
        tiff1 = Cpt(FS_tiff, 'TIFF1:',
                    write_path_template=wpath,
                    read_path_template=rpath,
                    root=root, reg=fs)
    target_root = root or '/'
    det = MyDetector(prefix, name='det')
    det.read_attrs = ['tiff1']
    det.tiff1.read_attrs = []

    det.stage()
    st = det.trigger()
    while not st.done:
        time.sleep(.1)
    reading = det.read()
    for name, d in det.collect_asset_docs():
        getattr(fs2, 'insert_{name}'.format(name=name))(**d)
    det.describe()
    det.unstage()

    datum_id = reading['det_image']['value']

    res_uid = fs.datum[datum_id]['resource']
    res_doc = fs.resource[res_uid]
    assert res_doc == fs2.resource[res_uid]
    assert fs.datum[datum_id] == fs2.datum[datum_id]

    assert res_doc['root'] == target_root
    assert not PurePath(res_doc['resource_path']).is_absolute()
    if check_files:
        time.sleep(5)  # Give AD some time to finish writing.
        path = PurePath(res_doc['root']) / PurePath(res_doc['resource_path'])
        handler = fh.AreaDetectorTiffHandler(str(path) + os.path.sep,
                                             **res_doc['resource_kwargs'])
        for fn in handler.get_file_list(datum['datum_kwargs'] for datum in
                                        fs.datum_by_resource[res_uid]):
            assert Path(fn).exists()


@pytest.mark.parametrize('root,wpath,rpath,check_files',
                         ((None, '/data/%Y/%m/%d', None, False),
                          (None, '/data/%Y/%m/%d', None, False),
                          ('/data', '%Y/%m/%d', None, False),
                          ('/data', '/data/%Y/%m/%d', '%Y/%m/%d', False),
                          ('/', '/data/%Y/%m/%d', None, False),
                          ('/tmp/data', '/data/%Y/%m/%d', '%Y/%m/%d', True)
                          ))
def test_fshdf_plugin(root, wpath, rpath, check_files):
    pytest.skip('hdf5 plugin is busted with docker images')
    fs = DummyFS()
    if check_files:
        fh = pytest.importorskip('databroker.assets.handlers')

    class FS_hdf(HDF5Plugin, FileStoreHDF5,
                 FileStoreIterativeWrite):
        pass

    class MyDetector(SingleTrigger, SimDetector):
        hdf1 = Cpt(FS_hdf, 'HDF1:',
                   write_path_template=wpath,
                   read_path_template=rpath,
                   root=root, reg=fs)
    target_root = root or '/'
    det = MyDetector(prefix, name='det')
    det.read_attrs = ['hdf1']
    det.hdf1.read_attrs = []
    det.cam.acquire_time.put(.1)
    det.hdf1.warmup()
    time.sleep(3)

    det.stage()

    time.sleep(1)

    st = det.trigger()

    count = 0
    while not st.done:
        time.sleep(.1)

        count += 1
        if count > 100:
            raise Exception("timedout")
    reading = det.read()
    det.describe()
    det.unstage()
    res_uid = fs.datum[reading['det_image']['value']]['resource']
    res_doc = fs.resource[res_uid]
    assert res_doc['root'] == target_root
    assert not PurePath(res_doc['resource_path']).is_absolute()
    if check_files:
        time.sleep(.1)
        path = PurePath(res_doc['root']) / PurePath(res_doc['resource_path'])
        handler = fh.AreaDetectorHDF5Handler(str(path),
                                             **res_doc['resource_kwargs'])
        for fn in handler.get_file_list(datum['datum_kwargs'] for datum in
                                        fs.datum_by_resource[res_uid]):
            assert Path(fn).exists()


def test_many_connect():
    import gc
    fs = DummyFS()

    class FS_hdf(HDF5Plugin, FileStoreHDF5,
                 FileStoreIterativeWrite):
        pass

    class MyDetector(SingleTrigger, SimDetector):
        hdf1 = Cpt(FS_hdf, 'HDF1:',
                   write_path_template='',
                   read_path_template='',
                   root='/', reg=fs)

    def tester():
        det = MyDetector(prefix, name='det')
        print('made detector')
        try:
            print('*'*25)
            print('about to murder socket')
            det.cam.acquire._read_pv._caproto_pv.circuit_manager._disconnected()
            print('murdered socket')
            print('*'*25)
        except AttributeError:
            # must be pyepics
            pass
        del det
        gc.collect()

    for j in range(5):
        print(j)
        tester()
