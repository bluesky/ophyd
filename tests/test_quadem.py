import logging
import pytest

import epics
from ophyd import QuadEM
from .test_signal import using_fake_epics_pv


logger = logging.getLogger(__name__)


@pytest.fixture(scope='function')
@using_fake_epics_pv
def quadem():
    em = QuadEM('quadem:', name='quadem')
    em.wait_for_connection()

    return em


def test_connected(quadem):
    assert quadem.connected


@using_fake_epics_pv
def test_scan_point(quadem):
    assert quadem._staged.value == 'no'

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
    for sig in quadem.stage_sigs:
        sig._read_pv = sig._write_pv

    for sig in quadem.image.stage_sigs:
        sig._read_pv = sig._write_pv
    quadem.image.enable._read_pv = quadem.image.enable._write_pv

    for sig in quadem.current1.stage_sigs:
        sig._read_pv = sig._write_pv
    quadem.current1.enable._read_pv = quadem.current1.enable._write_pv

    for sig in quadem.current2.stage_sigs:
        sig._read_pv = sig._write_pv
    quadem.current2.enable._read_pv = quadem.current2.enable._write_pv

    for sig in quadem.current3.stage_sigs:
        sig._read_pv = sig._write_pv
    quadem.current3.enable._read_pv = quadem.current3.enable._write_pv

    for sig in quadem.current4.stage_sigs:
        sig._read_pv = sig._write_pv
    quadem.current4.enable._read_pv = quadem.current4.enable._write_pv
    ''' End: Ugly Hack '''

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
                                   'units']))

    vals = quadem.read()
    assert 'quadem_current1_mean_value' in vals
    assert (set(('value', 'timestamp')) ==
            set(vals['quadem_current1_mean_value'].keys()))
