from __future__ import print_function

import logging
import unittest
import time
from copy import copy

import epics

from ophyd import EpicsMCA
from ophyd.utils import enum, ReadOnlyError
from .test_signal import FakeEpicsPV
from . import main

MCAMode = enum(PHA=0, MCS=1, List=2)

logger = logging.getLogger(__name__)


REAL_SCALER = False
devs = ['XF:23ID2-ES{Vortex}mca1']


def setUpModule():
    if not REAL_SCALER:
        epics._PV = epics.PV
        epics.PV = FakeEpicsPV


def tearDownModule():
    if __name__ == '__main__':
        epics.ca.destroy_context()

    if not REAL_SCALER:
        epics.PV = epics._PV

    logger.debug('Cleaning up')


class MCATests(unittest.TestCase):
    vtx = EpicsMCA(devs[0], rois=range(0, 5),
                   read_attrs=['spectrum', 'roi1.cnt', 'roi2.cnt'])

    def test_spectrum(self):
        self.assertRaises(ReadOnlyError, MCATests.vtx.spectrum.put, 3.14)
        self.assertRaises(ReadOnlyError, MCATests.vtx.background.put, 3.14)

    def test_read_attrs(self):
        r_attrs = MCATests.vtx.read_attrs
        self.assertEquals(r_attrs, ['spectrum', 'roi1.cnt', 'roi2.cnt'])

    def test_describe(self):
        MCATests.vtx.spectrum.read_attrs = ['spectrum']
        desc = MCATests.vtx.describe()
        d = desc[MCATests.vtx.prefix + '_spectrum']
        self.assertEquals(d['dtype'], 'number')
        self.assertEquals(d['shape'], [])

        if REAL_SCALER:
            # this will fail until EpicsSignal.describe is fixed!
            self.assertEquals(d['dtype'], 'array')
            self.assertEquals(d['shape'], [4096, ])

    def test_signals(self):
        mca = EpicsMCA(devs[0], name='mca', rois=[1, 2])
        mca.wait_for_connection()
        mca.mode.put(MCAMode.PHA)
        mca.stage()
        mca.start.put(1)
        mca._stop.put(1)
        mca.preset_time.put(3.14)
        mca.erase_start.put(1)
        mca.stop()
        mca.unstage()

    def test_rois(self):
        # iterables only
        self.assertRaises(TypeError, EpicsMCA, 'foo', rois=1)
        # check range
        self.assertRaises(AssertionError, EpicsMCA, 'bar', rois=[-1, ])
        self.assertRaises(AssertionError, EpicsMCA, 'baz', rois=[32, ])
        # read-only?
        self.assertRaises(ReadOnlyError, MCATests.vtx.roi1.cnt.put, 3.14)
        self.assertRaises(ReadOnlyError, MCATests.vtx.roi1.net_cnt.put, 3.14)


is_main = (__name__ == '__main__')
main(is_main)
