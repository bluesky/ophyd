import pytest

from ophyd.docs import get_device_info


def test_get_device_info_scaler():
    # `get_device_info` done by name, due to how sphinx directives work:
    info = get_device_info("ophyd.scaler", "EpicsScaler")
    assert len(info)

    # A list of component information dictionaries:
    components_by_attr = {item["attr"]: item for item in info}
    assert "count_mode" in components_by_attr
    assert "channels (DDC)" in components_by_attr

    # And detailed nested component information for a DDC:
    nested = components_by_attr["channels (DDC)"]["nested_components"]
    nested_components_by_attr = {item["attr"]: item for item in nested}
    assert "chan1" in nested_components_by_attr


@pytest.mark.parametrize(
    "module, class_name",
    [
        pytest.param("ophyd.areadetector.base", "ADBase"),
        pytest.param("ophyd.areadetector.cam", "PcoDetectorIO"),
        pytest.param("ophyd.areadetector.cam", "PcoDetectorSimIO"),
        pytest.param("ophyd.areadetector.common_plugins", "CommonAttributePlugin"),
        pytest.param("ophyd.areadetector.common_plugins", "CommonGatherPlugin"),
        pytest.param("ophyd.areadetector.common_plugins", "CommonOverlayPlugin"),
        pytest.param("ophyd.areadetector.common_plugins", "CommonPlugins"),
        pytest.param("ophyd.areadetector.common_plugins", "CommonROIStatPlugin"),
        pytest.param("ophyd.areadetector.detectors", "DetectorBase"),
        pytest.param("ophyd.areadetector.plugins", "AttrPlotPlugin"),
        pytest.param("ophyd.areadetector.plugins", "AttributeNPlugin"),
        pytest.param("ophyd.areadetector.plugins", "AttributePlugin"),
        pytest.param("ophyd.areadetector.plugins", "CircularBuffPlugin"),
        pytest.param("ophyd.areadetector.plugins", "CodecPlugin"),
        pytest.param("ophyd.areadetector.plugins", "FFTPlugin"),
        pytest.param("ophyd.areadetector.plugins", "GatherNPlugin"),
        pytest.param("ophyd.areadetector.plugins", "Overlay"),
        pytest.param("ophyd.areadetector.plugins", "PluginBase"),
        pytest.param("ophyd.areadetector.plugins", "PosPlugin"),
        pytest.param("ophyd.areadetector.plugins", "PvaPlugin"),
        pytest.param("ophyd.areadetector.plugins", "ROIStatNPlugin"),
        pytest.param("ophyd.areadetector.plugins", "ROIStatPlugin"),
        pytest.param("ophyd.areadetector.plugins", "ScatterPlugin"),
        pytest.param("ophyd.areadetector.plugins", "TimeSeriesNPlugin"),
        pytest.param("ophyd.areadetector.plugins", "TimeSeriesPlugin"),
        pytest.param("ophyd.epics_motor", "EpicsMotor"),
        pytest.param("ophyd.epics_motor", "MotorBundle"),
        pytest.param("ophyd.flyers", "AreaDetectorTimeseriesCollector"),
        pytest.param("ophyd.flyers", "WaveformCollector"),
        pytest.param("ophyd.mca", "EpicsDXP"),
        pytest.param("ophyd.mca", "EpicsDXPBaseSystem"),
        pytest.param("ophyd.mca", "EpicsDXPLowLevel"),
        pytest.param("ophyd.mca", "EpicsDXPLowLevelParameter"),
        pytest.param("ophyd.mca", "EpicsDXPMapping"),
        pytest.param("ophyd.mca", "EpicsMCACallback"),
        pytest.param("ophyd.mca", "EpicsMCARecord"),
        pytest.param("ophyd.mca", "ROI"),
        pytest.param("ophyd.mca", "SoftDXPTrigger"),
        pytest.param("ophyd.pseudopos", "PseudoPositioner"),
        pytest.param("ophyd.pseudopos", "PseudoSingle"),
        pytest.param("ophyd.pv_positioner", "PVPositioner"),
        pytest.param("ophyd.quadem", "QuadEMPort"),
        pytest.param("ophyd.scaler", "EpicsScaler"),
        pytest.param("ophyd.scaler", "ScalerCH"),
        pytest.param("ophyd.scaler", "ScalerChannel"),
        pytest.param("ophyd.sim", "ABDetector"),
        pytest.param("ophyd.sim", "DetWithConf"),
        pytest.param("ophyd.sim", "DetWithCountTime"),
        pytest.param("ophyd.sim", "DirectImage"),
        pytest.param("ophyd.sim", "Syn2DGauss"),
        pytest.param("ophyd.sim", "SynAxis"),
        pytest.param("ophyd.sim", "SynGauss"),
        pytest.param("ophyd.tests.test_sim", "Sample"),
        pytest.param("ophyd.tests.test_sim", "SampleNested"),
    ],
)
def test_get_device_info_smoke(module, class_name):
    get_device_info(module, class_name)
