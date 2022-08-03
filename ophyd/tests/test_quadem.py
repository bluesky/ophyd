import logging

import pytest

from ophyd import Kind, QuadEM
from ophyd.areadetector.plugins import ImagePlugin, StatsPlugin
from ophyd.sim import clear_fake_device, make_fake_device

logger = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def quadem():
    FakeQuadEM = make_fake_device(QuadEM)
    em = FakeQuadEM("quadem:", name="quadem")
    clear_fake_device(em)

    em.conf.port_name.put("NSLS_EM")

    for k in ["image", "current1", "current2", "current3", "current4", "sum_all"]:
        cc = getattr(em, k)

        if isinstance(cc, ImagePlugin):
            cc.plugin_type.sim_put(ImagePlugin._plugin_type)
            cc.nd_array_port.sim_put("NSLS_EM")
        elif isinstance(cc, StatsPlugin):
            cc.plugin_type.sim_put(StatsPlugin._plugin_type)
            cc.nd_array_port.sim_put("NSLS_EM")
        else:
            cc.plugin_type.sim_put("unknown")

        cc.enable.sim_set_enum_strs(["Disabled", "Enabled"])
        cc.enable.put("Enabled")
        cc.port_name.sim_put(k.upper())

    em.wait_for_connection()

    return em


def test_connected(quadem):
    assert quadem.connected


def test_scan_point(quadem):
    assert quadem._staged.value == "no"

    quadem.stage()
    assert quadem._staged.value == "yes"

    quadem.trigger()
    quadem.unstage()
    assert quadem._staged.value == "no"


def test_reading(quadem):
    assert "current1.mean_value" in quadem.read_attrs

    vals = quadem.read()
    assert "quadem_current1_mean_value" in vals
    assert set(("value", "timestamp")) == set(vals["quadem_current1_mean_value"].keys())

    rc = quadem.read_configuration()
    dc = quadem.describe_configuration()

    assert quadem.averaging_time.name in rc
    assert quadem.integration_time.name in rc

    assert rc.keys() == dc.keys()


def test_hints(quadem):

    desc = quadem.describe()
    f_hints = quadem.hints["fields"]
    assert len(f_hints) > 0
    for k in f_hints:
        assert k in desc

    def clear_hints(dev):
        for c in dev.component_names:
            c = getattr(dev, c)
            c.kind &= ~(Kind.hinted & ~Kind.normal)
            if hasattr(c, "component_names"):
                clear_hints(c)

    clear_hints(quadem)

    quadem.current1.mean_value.kind = Kind.hinted

    assert quadem.hints == {"fields": ["quadem_current1_mean_value"]}
