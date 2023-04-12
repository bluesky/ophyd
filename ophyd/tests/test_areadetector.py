import datetime
import logging
import os
import shutil
import time
import uuid
from io import StringIO
from pathlib import Path, PurePath
from unittest.mock import Mock

import numpy as np
import pytest

from ophyd import (
    Component,
    Device,
    DynamicDeviceComponent,
    Kind,
    SimDetector,
    SingleTrigger,
    wait,
)
from ophyd.areadetector.base import NDDerivedSignal
from ophyd.areadetector.filestore_mixins import (
    FileStoreHDF5,
    FileStoreIterativeWrite,
    FileStoreTIFF,
)

# we do not have nexus installed on our test IOC
# from ophyd.areadetector.plugins import NexusPlugin
from ophyd.areadetector.plugins import (  # FilePlugin
    ColorConvPlugin,
    HDF5Plugin,
    ImagePlugin,
    JPEGPlugin,
    NetCDFPlugin,
    OverlayPlugin,
    PluginBase,
    ProcessPlugin,
    ROIPlugin,
    StatsPlugin,
    TIFFPlugin,
    TransformPlugin,
)
from ophyd.areadetector.util import stub_templates
from ophyd.device import Component as Cpt
from ophyd.signal import Signal
from ophyd.utils.paths import make_dir_tree

logger = logging.getLogger(__name__)
ad_path = "/epics/support/areaDetector/1-9-1/ADApp/Db/"


class DummyFS:
    def __init__(self):
        self.resource = {}
        self.datum = {}
        self.datum_by_resource = {}

    def insert_resource(
        self,
        spec,
        resource_path,
        resource_kwargs,
        root=None,
        path_semantics="posix",
        uid=None,
        run_start=None,
        ignore_duplicate_error=False,
    ):
        self.resource[uid] = {
            "spec": spec,
            "resource_path": resource_path,
            "root": root,
            "resource_kwargs": resource_kwargs,
            "uid": uid,
            "path_semantics": path_semantics,
        }
        self.datum_by_resource[uid] = []
        return uid

    def register_resource(
        self, spec, root, rpath, rkwargs, path_semantics="posix", run_start=None
    ):

        uid = str(uuid.uuid4())
        return self.insert_resource(
            spec,
            rpath,
            rkwargs,
            root=root,
            path_semantics=path_semantics,
            uid=uid,
            run_start=run_start,
        )

    def register_datum(self, resource_uid, datum_kwargs):
        datum_id = str(uuid.uuid4())
        return self.insert_datum(resource_uid, datum_id, datum_kwargs)

    def insert_datum(
        self, resource, datum_id, datum_kwargs, ignore_duplicate_error=False
    ):
        datum = {
            "resource": resource,
            "datum_id": datum_id,
            "datum_kwargs": datum_kwargs,
        }
        self.datum_by_resource[resource].append(datum)
        self.datum[datum_id] = datum
        return datum_id


# lifted from soft-matter/pims source
def _recursive_subclasses(cls):
    "Return all subclasses (and their subclasses, etc.)."
    # Source: http://stackoverflow.com/a/3862957/1221924
    return cls.__subclasses__() + [
        g for s in cls.__subclasses__() for g in _recursive_subclasses(s)
    ]


@pytest.mark.adsim
def test_basic(cleanup, ad_prefix):
    class MyDetector(SingleTrigger, SimDetector):
        tiff1 = Cpt(TIFFPlugin, "TIFF1:")

    det = MyDetector(ad_prefix, name="test")
    print(det.tiff1.plugin_type)
    cleanup.add(det)

    det.wait_for_connection()

    det.cam.acquire_time.put(0.5)
    det.cam.acquire_period.put(0.5)
    det.cam.num_images.put(1)
    det.cam.image_mode.put(det.cam.ImageMode.SINGLE)
    det.stage()
    st = det.trigger()
    wait(st, timeout=5)
    det.unstage()


@pytest.mark.skipif("not os.path.exists(ad_path)")
def test_stubbing():
    try:
        for line in stub_templates(ad_path):
            logger.debug("Stub line: %s", line)
    except OSError:
        # self.fail('AreaDetector db path needed to run test')
        pass


@pytest.mark.adsim
def test_detector(ad_prefix, cleanup):
    det = SimDetector(ad_prefix, name="test")
    cleanup.add(det)

    det.find_signal("a", f=StringIO())
    det.find_signal("a", use_re=True, f=StringIO())
    det.find_signal("a", case_sensitive=True, f=StringIO())
    det.find_signal("a", use_re=True, case_sensitive=True, f=StringIO())
    det.component_names
    det.report

    cam = det.cam

    cam.image_mode.put("Single")
    # plugins don't live on detectors now:
    # det.image1.enable.put('Enable')
    cam.array_callbacks.put("Enable")

    st = det.trigger()
    repr(st)
    det.read()

    # values = tuple(det.gain_xy.get())
    cam.gain_xy.put(cam.gain_xy.get(), wait=True)

    # fail when only specifying x
    with pytest.raises(ValueError):
        cam.gain_xy.put((0.0,), wait=True)

    det.describe()
    det.report


@pytest.mark.adsim
def test_tiff_plugin(ad_prefix, cleanup):
    # det = AreaDetector(ad_prefix)
    class TestDet(SimDetector):
        p = Cpt(TIFFPlugin, "TIFF1:")

    det = TestDet(ad_prefix, name="test")
    cleanup.add(det)

    plugin = det.p

    plugin.file_template.put("%s%s_%3.3d.tif")

    plugin.array_pixels
    plugin


@pytest.mark.adsim
def test_hdf5_plugin(ad_prefix, cleanup):
    class MyDet(SimDetector):
        p = Cpt(HDF5Plugin, suffix="HDF1:")

    d = MyDet(ad_prefix, name="d")
    cleanup.add(d)

    d.p.file_path.put("/tmp")
    d.p.file_name.put("--")
    d.p.warmup()
    d.stage()
    print(d.p.read_configuration())
    d.p.describe_configuration()
    d.unstage()


@pytest.mark.adsim
def test_subclass(ad_prefix, cleanup):
    class MyDetector(SimDetector):
        tiff1 = Cpt(TIFFPlugin, "TIFF1:")

    det = MyDetector(ad_prefix, name="test")
    cleanup.add(det)
    det.wait_for_connection()

    print(det.describe())
    print(det.tiff1.capture.describe())


@pytest.mark.adsim
def test_getattr(ad_prefix, cleanup):
    class MyDetector(SimDetector):
        tiff1 = Cpt(TIFFPlugin, "TIFF1:")

    det = MyDetector(ad_prefix, name="test")
    cleanup.add(det)
    assert getattr(det, "tiff1.name") == det.tiff1.name
    assert getattr(det, "tiff1") is det.tiff1
    # raise
    # TODO subclassing issue


@pytest.mark.adsim
def test_invalid_plugins(ad_prefix, cleanup):
    class MyDetector(SingleTrigger, SimDetector):
        tiff1 = Cpt(TIFFPlugin, "TIFF1:")
        stats1 = Cpt(StatsPlugin, "Stats1:")

    det = MyDetector(ad_prefix, name="test")
    cleanup.add(det)

    det.wait_for_connection()
    det.tiff1.nd_array_port.put(det.cam.port_name.get())
    det.stats1.nd_array_port.put("AARDVARK")

    with pytest.raises(RuntimeError):
        det.stage()

    with pytest.raises(RuntimeError):
        det.validate_asyn_ports()

    assert ["AARDVARK"] == det.missing_plugins()


@pytest.mark.adsim
def test_validate_plugins_no_portname(ad_prefix, cleanup):
    class MyDetector(SingleTrigger, SimDetector):
        roi1 = Cpt(ROIPlugin, "ROI1:")
        over1 = Cpt(OverlayPlugin, "Over1:")

    det = MyDetector(ad_prefix, name="test")
    cleanup.add(det)

    det.roi1.nd_array_port.put(det.cam.port_name.get())
    det.over1.nd_array_port.put(det.roi1.port_name.get())

    det.validate_asyn_ports()


@pytest.mark.adsim
def test_get_plugin_by_asyn_port(ad_prefix, cleanup):
    class MyDetector(SingleTrigger, SimDetector):
        tiff1 = Cpt(TIFFPlugin, "TIFF1:")
        stats1 = Cpt(StatsPlugin, "Stats1:")
        roi1 = Cpt(ROIPlugin, "ROI1:")

    det = MyDetector(ad_prefix, name="test")
    cleanup.add(det)

    det.tiff1.nd_array_port.put(det.cam.port_name.get())
    det.roi1.nd_array_port.put(det.cam.port_name.get())
    det.stats1.nd_array_port.put(det.roi1.port_name.get())

    det.validate_asyn_ports()

    assert det.tiff1 is det.get_plugin_by_asyn_port(det.tiff1.port_name.get())
    assert det.cam is det.get_plugin_by_asyn_port(det.cam.port_name.get())
    assert det.roi1 is det.get_plugin_by_asyn_port(det.roi1.port_name.get())


@pytest.mark.adsim
def test_get_plugin_by_asyn_port_nested(ad_prefix, cleanup):
    # Support nested plugins
    class PluginGroup(Device):
        tiff1 = Cpt(TIFFPlugin, "TIFF1:")

    class MyDetector(SingleTrigger, SimDetector):
        plugins = Cpt(PluginGroup, "")
        roi1 = Cpt(ROIPlugin, "ROI1:")
        stats1 = Cpt(StatsPlugin, "Stats1:")

    nested_det = MyDetector(ad_prefix, name="nested_test")
    cleanup.add(nested_det)

    nested_det.stats1.nd_array_port.put(nested_det.roi1.port_name.get())
    nested_det.plugins.tiff1.nd_array_port.put(nested_det.cam.port_name.get())
    nested_det.roi1.nd_array_port.put(nested_det.cam.port_name.get())
    nested_det.stats1.nd_array_port.put(nested_det.roi1.port_name.get())

    nested_det.validate_asyn_ports()

    tiff = nested_det.plugins.tiff1
    assert tiff is nested_det.get_plugin_by_asyn_port(tiff.port_name.get())


@pytest.mark.adsim
def test_visualize_asyn_digraph_smoke(ad_prefix, cleanup):
    # setup sim detector
    det = SimDetector(ad_prefix, name="test")
    cleanup.add(det)
    # smoke test
    det.visualize_asyn_digraph()


@pytest.mark.adsim
def test_read_configuration_smoke(ad_prefix, cleanup):
    class MyDetector(SingleTrigger, SimDetector):
        stats1 = Cpt(StatsPlugin, "Stats1:")
        proc1 = Cpt(ProcessPlugin, "Proc1:")
        roi1 = Cpt(ROIPlugin, "ROI1:")

    det = MyDetector(ad_prefix, name="test")
    cleanup.add(det)

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


@pytest.mark.adsim
def test_str_smoke(ad_prefix, cleanup):
    class MyDetector(SingleTrigger, SimDetector):
        stats1 = Cpt(StatsPlugin, "Stats1:")
        proc1 = Cpt(ProcessPlugin, "Proc1:")
        roi1 = Cpt(ROIPlugin, "ROI1:")

    det = MyDetector(ad_prefix, name="test")
    cleanup.add(det)

    det.read_attrs = ["stats1"]
    det.stats1.read_attrs = ["mean_value"]
    det.stats1.mean_value.kind = Kind.hinted

    str(det)


@pytest.mark.parametrize("plugin", _recursive_subclasses(PluginBase))
def test_default_configuration_attrs(plugin):
    configuration_attrs = plugin._default_configuration_attrs
    if configuration_attrs is None:
        pytest.skip("Configuration attrs unset")
    for k in configuration_attrs:
        assert hasattr(plugin, k)
        assert isinstance(getattr(plugin, k), (Component, DynamicDeviceComponent))


@pytest.fixture(scope="function")
def data_paths(request):
    def clean_dirs():
        shutil.rmtree("/tmp/ophyd_AD_test/data1")
        os.unlink("/tmp/ophyd_AD_test/data2")

    try:
        clean_dirs()
    except Exception:
        ...

    now = datetime.datetime.now()

    for year_offset in [-1, 0, 1]:
        make_dir_tree(now.year + year_offset, base_path="/tmp/ophyd_AD_test/data1")

    os.symlink("/tmp/ophyd_AD_test/data1", "/tmp/ophyd_AD_test/data2")
    request.addfinalizer(clean_dirs)


@pytest.mark.adsim
@pytest.mark.parametrize(
    "root,wpath,rpath,check_files",
    (
        (None, "/tmp/ophyd_AD_test/data1/%Y/%m/%d", None, False),
        (None, "/tmp/ophyd_AD_test/data1/%Y/%m/%d", None, False),
        ("/tmp/ophyd_AD_test/data1", "%Y/%m/%d", None, False),
        (
            "/tmp/ophyd_AD_test/data1",
            "/tmp/ophyd_AD_test/data1/%Y/%m/%d",
            "%Y/%m/%d",
            False,
        ),
        ("/", "/tmp/ophyd_AD_test/data1/%Y/%m/%d", None, False),
        (
            "/tmp/ophyd_AD_test/data2",
            "/tmp/ophyd_AD_test/data1/%Y/%m/%d",
            "%Y/%m/%d",
            True,
        ),
    ),
)
def test_fstiff_plugin(data_paths, ad_prefix, root, wpath, rpath, check_files, cleanup):
    fs = DummyFS()
    fs2 = DummyFS()
    if check_files:
        fh = pytest.importorskip("databroker.assets.handlers")

    class FS_tiff(TIFFPlugin, FileStoreTIFF, FileStoreIterativeWrite):
        pass

    class MyDetector(SingleTrigger, SimDetector):
        tiff1 = Cpt(
            FS_tiff,
            "TIFF1:",
            write_path_template=wpath,
            read_path_template=rpath,
            root=root,
            reg=fs,
        )

    target_root = root or "/"
    det = MyDetector(ad_prefix, name="det")
    cleanup.add(det)
    det.read_attrs = ["tiff1"]
    det.tiff1.read_attrs = []

    det.stage()
    st = det.trigger()
    while not st.done:
        time.sleep(0.1)
    reading = det.read()
    for name, d in det.collect_asset_docs():
        getattr(fs2, "insert_{name}".format(name=name))(**d)
    det.describe()
    det.unstage()

    datum_id = reading["det_image"]["value"]

    res_uid = fs.datum[datum_id]["resource"]
    res_doc = fs.resource[res_uid]
    assert res_doc == fs2.resource[res_uid]
    assert fs.datum[datum_id] == fs2.datum[datum_id]

    assert res_doc["root"] == target_root
    assert not PurePath(res_doc["resource_path"]).is_absolute()
    if check_files:
        time.sleep(5)  # Give AD some time to finish writing.
        path = PurePath(res_doc["root"]) / PurePath(res_doc["resource_path"])
        handler = fh.AreaDetectorTiffHandler(
            str(path) + os.path.sep, **res_doc["resource_kwargs"]
        )
        for fn in handler.get_file_list(
            datum["datum_kwargs"] for datum in fs.datum_by_resource[res_uid]
        ):
            assert Path(fn).exists()


@pytest.fixture
def h5py():
    try:
        import h5py
    except ImportError as ex:
        raise pytest.skip("h5py unavailable") from ex

    return h5py


@pytest.mark.adsim
@pytest.mark.xfail
@pytest.mark.parametrize(
    "root,wpath,rpath,check_files",
    (
        (None, "/tmp/ophyd_AD_test/data1/%Y/%m/%d", None, False),
        (None, "/tmp/ophyd_AD_test/data1/%Y/%m/%d", None, False),
        ("/tmp/ophyd_AD_test/data1", "%Y/%m/%d", None, False),
        (
            "/tmp/ophyd_AD_test/data1",
            "/tmp/ophyd_AD_test/data1/%Y/%m/%d",
            "%Y/%m/%d",
            False,
        ),
        ("/", "/tmp/ophyd_AD_test/data1/%Y/%m/%d", None, False),
        (
            "/tmp/ophyd_AD_test/data2",
            "/tmp/ophyd_AD_test/data1/%Y/%m/%d",
            "%Y/%m/%d",
            True,
        ),
    ),
)
def test_fshdf_plugin(
    h5py, data_paths, ad_prefix, root, wpath, rpath, check_files, cleanup
):
    fs = DummyFS()
    if check_files:
        fh = pytest.importorskip("databroker.assets.handlers")

    class FS_hdf(HDF5Plugin, FileStoreHDF5, FileStoreIterativeWrite):
        pass

    class MyDetector(SingleTrigger, SimDetector):
        hdf1 = Cpt(
            FS_hdf,
            "HDF1:",
            write_path_template=wpath,
            read_path_template=rpath,
            root=root,
            reg=fs,
        )

    target_root = root or "/"
    det = MyDetector(ad_prefix, name="det")
    cleanup.add(det)
    det.read_attrs = ["hdf1"]
    det.hdf1.read_attrs = []
    det.cam.acquire_time.put(0.1)
    det.cam.num_images.put(5)
    det.hdf1.warmup()
    time.sleep(3)

    det.stage()

    time.sleep(1)

    st = det.trigger()

    count = 0
    while not st.done:
        time.sleep(0.1)

        count += 1
        if count > 100:
            raise Exception("timedout")
    reading = det.read()
    det.describe()
    det.unstage()
    res_uid = fs.datum[reading["det_image"]["value"]]["resource"]
    res_doc = fs.resource[res_uid]
    assert res_doc["root"] == target_root
    assert not PurePath(res_doc["resource_path"]).is_absolute()
    if check_files:
        time.sleep(5)  # Give AD some time to finish writing.
        path = PurePath(res_doc["root"]) / PurePath(res_doc["resource_path"])
        handler = fh.AreaDetectorHDF5Handler(str(path), **res_doc["resource_kwargs"])
        for fn in handler.get_file_list(
            datum["datum_kwargs"] for datum in fs.datum_by_resource[res_uid]
        ):
            assert Path(fn).exists()


@pytest.mark.adsim
@pytest.mark.xfail
def test_many_connect(ad_prefix, cleanup):
    import ophyd

    pytest.skipif(
        ophyd.get_cl().name == "pyepics",
        "This is exposing race conditions in pyepics which " "cause segfaults.",
    )
    import gc

    fs = DummyFS()

    class FS_hdf(HDF5Plugin, FileStoreHDF5, FileStoreIterativeWrite):
        pass

    class MyDetector(SingleTrigger, SimDetector):
        hdf1 = Cpt(
            FS_hdf,
            "HDF1:",
            write_path_template="",
            read_path_template="",
            root="/",
            reg=fs,
        )

    try:
        from caproto.threading import client
    except ImportError:
        # caproto unavailable on python 3.5
        pass
    else:
        if client.SEARCH_MAX_DATAGRAM_BYTES > 1450:
            # old caproto compatibility - later versions lower to standardish
            # MTU-levels
            client.SEARCH_MAX_DATAGRAM_BYTES = 1450

    def tester():
        det = MyDetector(ad_prefix, name="det")
        print("made detector")
        try:
            print("*" * 25)
            print("about to murder socket")
            det.cam.acquire._read_pv._caproto_pv.circuit_manager._disconnected()
            print("murdered socket")
            print("*" * 25)
        except AttributeError:
            # must be pyepics
            pass
        det.destroy()
        del det
        gc.collect()

    for j in range(5):
        print(j)
        tester()


def test_ndderivedsignal_with_scalars():
    sig = Signal(value=np.zeros(12), name="zeros")
    shaped = NDDerivedSignal(sig, shape=(4, 3), num_dimensions=2, name="shaped")
    shaped.derived_shape == (4, 3)
    shaped.derived_ndims == 2
    assert shaped.get().shape == (4, 3)
    # Describe returns list
    assert shaped.describe()[shaped.name]["shape"] == [4, 3]
    shaped.put(np.ones((4, 3)))
    assert all(sig.get() == np.ones(12))


def test_ndderivedsignal_with_parent():
    class Detector(Device):
        flat_image = Component(Signal, value=np.ones(12))
        width = Component(Signal, value=4)
        height = Component(Signal, value=3)
        ndims = Component(Signal, value=2)
        shaped_image = Component(
            NDDerivedSignal,
            "flat_image",
            shape=("width", "height"),
            num_dimensions="ndims",
        )

    det = Detector(name="det")
    det.shaped_image.get().shape == (4, 3)
    cb = Mock()
    det.shaped_image.subscribe(cb)
    det.width.put(6)
    det.height.put(2)
    assert cb.called
    assert det.shaped_image._readback.shape == (6, 2)


@pytest.mark.adsim
@pytest.mark.parametrize("paths", [("/some/path/here"), ("/here/is/another/")])
def test_posix_path(paths, cleanup, ad_prefix):
    class MyDetector(SingleTrigger, SimDetector):
        tiff1 = Cpt(TIFFPlugin, "TIFF1:")

    det = MyDetector(ad_prefix, name="test")
    print(det.tiff1.plugin_type)
    cleanup.add(det)

    det.wait_for_connection()

    det.tiff1.file_path.put(paths)
    # det.cam.file_path.put(paths)
    det.stage()
    st = det.trigger()
    wait(st, timeout=5)
    det.unstage()


@pytest.mark.adsim
def test_default_configuration_smoke(ad_prefix, cleanup):
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
        # magickplugin = Cpt(MagickPlugin, MagickPlugin._default_suffix)

    d = MyDetector(ad_prefix, name="d")
    cleanup.add(d)
    d.stage()
    {n: getattr(d, n).read_configuration() for n in d.component_names}
    {n: getattr(d, n).describe_configuration() for n in d.component_names}
    d.unstage()
