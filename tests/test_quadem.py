import logging
import pytest

import epics
from ophyd import QuadEM
from ophyd.utils import ReadOnlyError
from .test_signal import FakeEpicsPV


logger = logging.getLogger(__name__)

def setup_module(module):
    epics._PV = epics.PV
    epics.PV = FakeEpicsPV

    logger.info('setup_module complete')

def teardown_module(module):
    if __name__ == '__main__':
        epics.ca.destroy_context()

    epics.PV = epics._PV
    logger.info('Cleaning up')

@pytest.fixture(scope='function')
def quadem():
    em = QuadEM('quadem:', name='quadem')
    em.wait_for_connection()

    return em

def test_connected(quadem):
    assert quadem.connected

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

def test_reading(quadem):
    assert 'current1.mean_value' in quadem.read_attrs

    desc = quadem.describe()
    desc_keys = list(desc['quadem_current1_mean_value'].keys())
    assert set(desc_keys) == \
           set(['dtype', 'precision', 'shape', 'source', 'units'])

    vals = quadem.read()
    assert 'quadem_current1_mean_value' in vals
    assert set(('value', 'timestamp')) == \
           set(vals['quadem_current1_mean_value'].keys())

def test_readonly(quadem):
    ro_attrs = ['model', 'firmware', 'hvs_readback', 'hvv_readback',
                'hvi_readback', 'sample_time', 'num_average', 'num_averaged',
                'num_acquired', 'read_data', 'ring_overflows']

    for attr in ro_attrs:
        pytest.raises(ReadOnlyError, getattr(quadem, attr).put, 3,14)

# non-EpicsSignalRO class attributes
def test_attrs(quadem):
    cpt_attrs = ['acquire_mode', 'acquire', 'read_format', 'em_range',
                 'ping_pong', 'integration_time', 'num_channels', 'geometry',
                 'resolution', 'bias_state', 'bias_interlock', 'bias_voltage',
                 'values_per_read', 'averaging_time', 'num_acquire',
                 'trigger_mode', 'reset', 'position_offset_x', 'position_offset_y',
                 'position_offset_calc_x', 'position_offset_calc_y',
                 'position_scale_x', 'position_scale_y']

    for attr in cpt_attrs:
        cpt = getattr(quadem, attr)
        cpt.put(3.14)
        cpt.get()

    ddcpt_attrs = ['current_names', 'current_offsets', 'current_offset_calcs',
                   'current_scales']

    for attr in ddcpt_attrs:
        for i in range(1,5):
            cpt = getattr(quadem, attr + '.ch{}'.format(i))
            cpt.put(3.14)
            cpt.get()
