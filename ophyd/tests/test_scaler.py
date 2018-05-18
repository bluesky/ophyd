

import logging
import time
from copy import copy

from ophyd import scaler
from ophyd.utils import enum
from .conftest import using_fake_epics_pv
from .test_utils import assert_OD_equal_ignore_ts


ScalerMode = enum(ONE_SHOT=0, AUTO_COUNT=1)

logger = logging.getLogger(__name__)


REAL_SCALER = False
scalers = ['XF:23ID2-ES{Sclr:1}']


@using_fake_epics_pv
def test_temp_scaler():
    # TODO fix
    scaler.EpicsScaler(scalers[0], name='test')


@using_fake_epics_pv
def test_scaler_functionality():
    sca = scaler.EpicsScaler(scalers[0], name='scaler',
                             read_attrs=['channels'])
    # hack the fake PV to know the enums
    sca.wait_for_connection()
    if not REAL_SCALER:
        sca.count_mode._read_pv.enum_strs = ['OneShot', 'AutoCount']
        sca.count_mode.put('OneShot')
        # pin the fake PVs by setting them
        attr_map = {getattr(sca, n).name: n for n in sca.configuration_attrs}
        cnf = {attr_map[k]: v['value']
               for k, v in sca.read_configuration().items()}

        sca.configure(cnf)

    sca.preset_time.put(5.2)

    logger.info('Counting in One-Shot mode for %f s...',
                sca.preset_time.get())
    sca.count.put(1)
    logger.info('Sleeping...')
    time.sleep(3)
    logger.info('Done sleeping. Stopping counter...')
    sca.stop()

    logger.info('Set mode to AutoCount')
    sca.count_mode.put(ScalerMode.AUTO_COUNT)
    sca.count.put(1)
    logger.info('Begin auto-counting (aka "background counting")...')
    time.sleep(2)
    logger.info('Set mode to OneShot')
    sca.count_mode.put(ScalerMode.ONE_SHOT)
    time.sleep(1)
    logger.info('Stopping (aborting) auto-counting.')
    sca.stop()

    logger.info('read() all channels in one-shot mode...')
    vals = sca.read()
    logger.info(vals)
    assert 'scaler_channels_chan1' in vals

    sca.report
    sca.read()

    assert copy(sca).prefix == sca.prefix
    assert copy(sca).read_attrs == sca.read_attrs
    assert copy(sca).configuration_attrs == sca.configuration_attrs
    repr(sca)
    str(sca)

    sca.stage()
    old, new = sca.configure({})
    sca.unstage()

    assert_OD_equal_ignore_ts(old, new)

    sca.stage()
    old_preset_time = sca.preset_time.get()
    old, new = sca.configure({'preset_time': 7})
    sca.unstage()

    assert old.pop('scaler_preset_time')['value'] == old_preset_time
    assert new.pop('scaler_preset_time')['value'] == 7
    assert_OD_equal_ignore_ts(old, new)

    sca.hints == {'fields': [sca.channels.name]}


@using_fake_epics_pv
def test_signal_separate():
    sca = scaler.EpicsScaler(scalers[0], name='scaler',
                             read_attrs=['channels.chan1'])
    sca.wait_for_connection()
    data = sca.read()
    assert 'scaler_channels_chan1' in data
    assert 'scaler_channels_chan2' not in data


@using_fake_epics_pv
def smoke_test_scalerCH():
    sca = scaler.ScalerCH(scalers[0])
    sca.wait_for_connection()
    data = sca.read()
    assert 'scaler_channels_chan1' in data
    assert 'scaler_channels_chan2' not in data
