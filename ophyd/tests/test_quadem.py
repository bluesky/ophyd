import logging
import pytest

from ophyd import QuadEM, Component as Cpt, Signal
from ophyd.areadetector.plugins import ImagePlugin, StatsPlugin
from ophyd.ophydobj import Kind
from .conftest import using_fake_epics_pv


logger = logging.getLogger(__name__)


@pytest.fixture(scope='function')
@using_fake_epics_pv
def quadem():
    class FakeStats(StatsPlugin):
        plugin_type = Cpt(Signal, value=StatsPlugin._plugin_type)
        nd_array_port = Cpt(Signal, value='NSLS_EM')

    class FakeImage(ImagePlugin):
        plugin_type = Cpt(Signal, value=ImagePlugin._plugin_type)
        nd_array_port = Cpt(Signal, value='NSLS_EM')

    class FakeQuadEM(QuadEM):
        image = Cpt(FakeImage, 'image1:')
        current1 = Cpt(FakeStats, 'Current1:')
        current2 = Cpt(FakeStats, 'Current2:')
        current3 = Cpt(FakeStats, 'Current3:')
        current4 = Cpt(FakeStats, 'Current4:')
        sum_all = Cpt(FakeStats, 'SumAll:')

    em = FakeQuadEM('quadem:', name='quadem')

    ''' Beware: Ugly Hack below

        tl;dr
        Set Signal._read_pv = Signal._write_pv in order for
        set_and_wait() to succeed in calls from Device.stage()

        The raison d'etre here is a limitation of FakeEpicsPV,
        or rather a limitation of the test harness:
            Since the QuadEM is based on areadetector, it uses
            EpicsSignalWithRBV in several places. The test harness
            monkey-patches epics.PV with FakeEpicsPV, which means
            that get/put are routed to two different pvs, which in turn,
            means that set_and_wait() will never be successful for
            EpicsSignalWithRBVs... :-(
    '''

    for sig in em.stage_sigs:
        sig = getattr(em, sig)
        sig._read_pv = sig._write_pv

    for k in ['image', *['current{}'.format(j) for j in range(1, 5)],
              'sum_all']:
        cc = getattr(em, k)
        for sig in cc.stage_sigs:
            sig = getattr(cc, sig)
            sig._read_pv = sig._write_pv
        cc.enable._read_pv = cc.enable._write_pv
        cc.enable._write_pv.enum_strs = ['Disabled', 'Enabled']
        cc.enable.put('Enabled')
        cc.port_name._read_pv.put(k.upper())
    ''' End: Ugly Hack '''

    em.wait_for_connection()

    return em


def test_connected(quadem):
    assert quadem.connected


@using_fake_epics_pv
def test_scan_point(quadem):
    assert quadem._staged.value == 'no'

    quadem.stage()
    assert quadem._staged.value == 'yes'

    quadem.trigger()
    quadem.unstage()
    assert quadem._staged.value == 'no'


@using_fake_epics_pv
def test_reading(quadem):
    assert 'current1.mean_value' in quadem.read_attrs

    desc = quadem.describe()
    desc_keys = list(desc['quadem_current1_mean_value'].keys())
    assert (set(desc_keys) == set(['dtype', 'precision', 'shape', 'source',
                                   'units', 'lower_ctrl_limit',
                                   'upper_ctrl_limit']))

    vals = quadem.read()
    assert 'quadem_current1_mean_value' in vals
    assert (set(('value', 'timestamp')) ==
            set(vals['quadem_current1_mean_value'].keys()))

    rc = quadem.read_configuration()
    dc = quadem.describe_configuration()

    assert quadem.averaging_time.name in rc
    assert quadem.integration_time.name in rc

    assert rc.keys() == dc.keys()


@using_fake_epics_pv
def test_hints(quadem):

    desc = quadem.describe()
    f_hints = quadem.hints['fields']
    assert len(f_hints) > 0
    for k in f_hints:
        assert k in desc

    def clear_hints(dev):
        for c in dev.component_names:
            c = getattr(dev, c)
            c.kind &= ~(Kind.hinted & ~Kind.normal)
            if hasattr(c, 'component_names'):
                clear_hints(c)

    clear_hints(quadem)

    quadem.current1.mean_value.kind = Kind.hinted

    assert quadem.hints == {'fields': ['quadem_current1_mean_value']}
