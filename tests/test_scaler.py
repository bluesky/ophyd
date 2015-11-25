from __future__ import print_function

import logging
import unittest
import time
from copy import copy

import epics

from ophyd.controls import scaler
from ophyd.utils import enum
from ophyd.session import get_session_manager
from .test_signal import FakeEpicsPV

ScalerMode = enum(ONE_SHOT=0, AUTO_COUNT=1)

server = None
logger = logging.getLogger(__name__)
session = get_session_manager()


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

    def test_signal_separate(self):
        sca = scaler.EpicsScaler(scalers[0], name='scaler')
        sca.preset_time = 5.2

        logger.info('Counting in One-Shot mode for %f s...' % sca.preset_time)
        sca.start()
        logger.info('Sleeping...')
        time.sleep(3)
        logger.info('Done sleeping. Stopping counter...')
        sca.stop()

        logger.info('Set mode to AutoCount')
        sca.count_mode = ScalerMode.AUTO_COUNT
        sca.start()
        logger.info('Begin auto-counting (aka "background counting")...')
        time.sleep(2)
        logger.info('Set mode to OneShot')
        sca.count_mode = ScalerMode.ONE_SHOT
        time.sleep(1)
        logger.info('Stopping (aborting) auto-counting.')
        sca.stop()

        logger.info('read() all channels in one-shot mode...')
        vals = sca.read()
        logger.info(vals)

        channels = (1, 3, 5, 6)
        logger.info('read() selected channels %s in one-shot mode...' % list(channels))
        vals = sca.read(channels)
        logger.info(vals)

        sca.report
        sca.read()
        copy(sca)
        repr(sca)
        str(sca)


from . import main
is_main = (__name__ == '__main__')
main(is_main)
