
import logging
import pytest
from io import StringIO

from ophyd import (SimDetector, SingleTrigger, Component,
                   DynamicDeviceComponent)
from ophyd.areadetector.plugins import (ImagePlugin, StatsPlugin,
                                        ColorConvPlugin,
                                        ProcessPlugin, OverlayPlugin,
                                        ROIPlugin, TransformPlugin,
                                        NetCDFPlugin, TIFFPlugin, JPEGPlugin,
                                        HDF5Plugin,
                                        MagickPlugin)
# we do not have nexus installed on our test IOC
# from ophyd.areadetector.plugins import NexusPlugin
from ophyd.areadetector.plugins import PluginBase
from ophyd.areadetector.util import stub_templates
from ophyd.device import (Component as Cpt, )

logger = logging.getLogger(__name__)

prefix = 'XF:31IDA-BI{Cam:Tbl}'
ad_path = '/epics/support/areaDetector/1-9-1/ADApp/Db/'


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

    det = MyDetector(prefix)
    det.wait_for_connection()
    det.stage()
    det.trigger()
    det.unstage()


def test_stubbing():
    try:
        for line in stub_templates(ad_path):
            logger.debug('Stub line: %s', line)
    except OSError:
        # self.fail('AreaDetector db path needed to run test')
        pass


def test_detector():
    det = SimDetector(prefix)

    det.find_signal('a', f=StringIO())
    det.find_signal('a', use_re=True, f=StringIO())
    det.find_signal('a', case_sensitive=True, f=StringIO())
    det.find_signal('a', use_re=True, case_sensitive=True, f=StringIO())
    det.signal_names
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

    det = TestDet(prefix)
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

    det = MyDetector(prefix)
    det.wait_for_connection()

    print(det.describe())
    print(det.tiff1.capture.describe())


def test_getattr():
    class MyDetector(SimDetector):
        tiff1 = Cpt(TIFFPlugin, 'TIFF1:')

    det = MyDetector(prefix)
    assert getattr(det, 'tiff1.name') == det.tiff1.name
    assert getattr(det, 'tiff1') is det.tiff1
    # raise
    # TODO subclassing issue


def test_invalid_plugins():
    class MyDetector(SingleTrigger, SimDetector):
        tiff1 = Cpt(TIFFPlugin, 'TIFF1:')
        stats1 = Cpt(StatsPlugin, 'Stats1:')

    det = MyDetector(prefix)
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

    det = MyDetector(prefix)

    det.roi1.nd_array_port.put(det.cam.port_name.get())
    det.over1.nd_array_port.put(det.roi1.port_name.get())

    det.validate_asyn_ports()

def test_get_plugin_by_asyn_port():
    class MyDetector(SingleTrigger, SimDetector):
        tiff1 = Cpt(TIFFPlugin, 'TIFF1:')
        stats1 = Cpt(StatsPlugin, 'Stats1:')
        roi1 = Cpt(ROIPlugin, 'ROI1:')

    det = MyDetector(prefix)

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
    {n: getattr(d, n).read_configuration() for n in d.signal_names}
    {n: getattr(d, n).describe_configuration() for n in d.signal_names}
    d.unstage()

@pytest.mark.parametrize('plugin',
                         _recursive_subclasses(PluginBase))
def test_default_configuration_attrs(plugin):
    for k in plugin._default_configuration_attrs:
        assert hasattr(plugin, k)
        assert isinstance(getattr(plugin, k),
                          (Component, DynamicDeviceComponent))


from . import main
is_main = (__name__ == '__main__')
main(is_main)
