from __future__ import print_function

import logging
import unittest
import time
from copy import copy

import epics

from ophyd import scaler
from ophyd.utils import enum
from .test_signal import FakeEpicsPV
from .test_utils import assert_OD_equal_ignore_ts


ScalerMode = enum(ONE_SHOT=0, AUTO_COUNT=1)

logger = logging.getLogger(__name__)


REAL_SCALER = False
scalers = ['XF:23ID2-ES{Sclr:1}']


def setUpModule():
    global server

    if not REAL_SCALER:
        epics._PV = epics.PV
        epics.PV = FakeEpicsPV


def tearDownModule():
    if __name__ == '__main__':
        epics.ca.destroy_context()
    epics.PV = epics._PV

    logger.debug('Cleaning up')


class SignalTests(unittest.TestCase):
    real_scaler = False

    def test_temp_scaler(self):
        # TODO fix
        scaler.EpicsScaler(scalers[0])

    def test_scaler_functionality(self):
        sca = scaler.EpicsScaler(scalers[0], name='scaler',
                                 read_attrs=['channels'])
        # hack the fake PV to know the enums
        if not REAL_SCALER:
            sca.count_mode._read_pv.enum_strs = ['OneShot', 'AutoCount']
        sca.wait_for_connection()

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
        self.assertIn('scaler_channels_chan1', vals)

        sca.report
        sca.read()

        self.assertEquals(copy(sca).prefix, sca.prefix)
        self.assertEquals(copy(sca).read_attrs, sca.read_attrs)
        self.assertEquals(copy(sca).configuration_attrs,
                          sca.configuration_attrs)
        self.assertEquals(copy(sca).monitor_attrs, sca.monitor_attrs)
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


    def test_signal_separate(self):
        sca = scaler.EpicsScaler(scalers[0], name='scaler',
                                 read_attrs=['channels.chan1'])
        sca.wait_for_connection()
        data = sca.read()
        self.assertIn('scaler_channels_chan1', data)
        self.assertNotIn('scaler_channels_chan2', data)


from . import main
is_main = (__name__ == '__main__')
main(is_main)
