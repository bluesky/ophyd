import logging
from types import SimpleNamespace

import pytest
from caproto.tests.conftest import run_example_ioc

from ophyd import EpicsDXP, EpicsMCA
from ophyd.mca import Mercury1, SoftDXPTrigger, add_rois
from ophyd.utils import ReadOnlyError, enum

MCAMode = enum(PHA="PHA", MCS="MCS", List="List")
DxpPresetMode = enum(
    No_preset="No preset", Real_time="Real time", Live_time="Live time"
)

logger = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def mca_test_ioc(prefix, request):
    name = "test_signal IOC"
    pvs = dict(mca_prefix=f"{prefix}mca", dxp_prefix=f"{prefix}dxp:")

    process = run_example_ioc(
        "ophyd.tests.mca_ioc",
        request=request,
        pv_to_check=pvs["mca_prefix"],
        args=("--prefix", prefix, "-v"),
    )
    return SimpleNamespace(
        process=process, prefix=prefix, name=name, pvs=pvs, type="caproto"
    )


@pytest.fixture(scope="function")
def mca(cleanup, mca_test_ioc):
    mca = EpicsMCA(mca_test_ioc.pvs["mca_prefix"], name="mca")
    mca.wait_for_connection()
    cleanup.add(mca)
    return mca


@pytest.fixture(scope="function")
def dxp(cleanup, mca_test_ioc):
    dxp = EpicsDXP(mca_test_ioc.pvs["dxp_prefix"], name="dxp")
    dxp.wait_for_connection()
    cleanup.add(dxp)
    return dxp


def test_mca_spectrum(mca):
    with pytest.raises(ReadOnlyError):
        mca.spectrum.put(3.14)
    with pytest.raises(ReadOnlyError):
        mca.background.put(3.14)


def test_mca_read_attrs(mca):
    # default read_attrs
    default_normal_kind = ["preset_real_time", "elapsed_real_time", "spectrum"]
    assert set(default_normal_kind) == set(mca.read_attrs)
    # test passing in custom read_attrs (with dots!)
    r_attrs = ["spectrum", "rois.roi1.count", "rois.roi2.count"]

    mca.read_attrs = r_attrs
    expected = set(r_attrs + ["rois.roi1", "rois.roi2", "rois"])
    assert expected == set(mca.read_attrs)


def test_mca_describe(mca):
    desc = mca.describe()
    d = desc[mca.name + "_spectrum"]

    assert d["dtype"] == "number"
    assert d["shape"] == []


def test_mca_signals(mca):
    mca.mode.put(MCAMode.PHA)
    mca.stage()
    mca.start.put(1)
    mca.stop_signal.put(1)
    mca.preset_real_time.put(3.14)
    mca.preset_live_time.put(3.14)
    mca.erase_start.put(1)
    mca.stop()
    mca.unstage()


def test_rois(mca):
    # iterables only
    with pytest.raises(TypeError):
        add_rois(1)
    # check range
    with pytest.raises(ValueError):
        add_rois(
            [
                -1,
            ]
        )
    with pytest.raises(ValueError):
        add_rois(
            [
                32,
            ]
        )
    # read-only?
    with pytest.raises(ReadOnlyError):
        mca.rois.roi1.count.put(3.14)
    with pytest.raises(ReadOnlyError):
        mca.rois.roi1.net_count.put(3.14)


def test_dxp_signals(dxp):
    # NOTE: values used below are those currently used at 23id2
    dxp.preset_mode.put(DxpPresetMode.Real_time)
    dxp.stage()
    dxp.unstage()

    dxp.trigger_peaking_time.put(0.2)
    dxp.trigger_threshold.put(0.6)
    dxp.trigger_gap_time.put(0.0)
    dxp.max_width.put(1.0)
    dxp.peaking_time.put(0.25)
    dxp.energy_threshold.put(0.35)
    dxp.gap_time.put(0.05)

    dxp.baseline_cut_percent.put(5.0)
    dxp.baseline_cut_enable.put(1)
    dxp.baseline_filter_length.put(128)
    dxp.baseline_threshold.put(0.20)

    dxp.preamp_gain.put(5.5)
    dxp.detector_polarity.put(1)
    dxp.reset_delay.put(10.0)
    dxp.decay_time.put(50.0)
    dxp.max_energy.put(2.0)
    dxp.adc_percent_rule.put(5.0)

    # read-only
    with pytest.raises(ReadOnlyError):
        dxp.triggers.put(2)
    with pytest.raises(ReadOnlyError):
        dxp.events.put(2)
    with pytest.raises(ReadOnlyError):
        dxp.overflows.put(2)
    with pytest.raises(ReadOnlyError):
        dxp.underflows.put(2)
    with pytest.raises(ReadOnlyError):
        dxp.input_count_rate.put(2)
    with pytest.raises(ReadOnlyError):
        dxp.output_count_rate.put(2)


def test_mixin_signals():
    class Mercury(Mercury1, SoftDXPTrigger):
        pass

    mercury = Mercury("Will_Not_Try_To_connect", name="mercury")
    assert "count_time" in mercury.component_names
