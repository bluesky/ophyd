from __future__ import print_function

import logging
import unittest
import time
from copy import copy

import epics

from ophyd import EpicsMCA, DxpMCA
from ophyd.controls.mca import add_rois
from ophyd.utils import enum, ReadOnlyError
from .test_signal import FakeEpicsPV
from . import main

MCAMode = enum(PHA=0, MCS=1, List=2)
DxpPresetMode = enum(No_preset=0, Real_time=1, Live_time=2)

logger = logging.getLogger(__name__)


REAL_SCALER = False
devs = ['XF:23ID2-ES{Vortex}mca1', 'XF:23ID2-ES{Vortex}dxp1:']


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
    vtx = EpicsMCA(devs[0],
                   read_attrs=['spectrum', 'rois.roi1.count',
                               'rois.roi2.count']
                   )

    def test_spectrum(self):
        self.assertRaises(ReadOnlyError, MCATests.vtx.spectrum.put, 3.14)
        self.assertRaises(ReadOnlyError, MCATests.vtx.background.put, 3.14)

    def test_read_attrs(self):
        r_attrs = MCATests.vtx.read_attrs
        self.assertEquals(r_attrs, 
                          ['spectrum', 'rois.roi1.count', 'rois.roi2.count'])

    def test_describe(self):
        desc = MCATests.vtx.describe()
        d = desc[MCATests.vtx.prefix + '_spectrum']
        self.assertEquals(d['dtype'], 'number')
        self.assertEquals(d['shape'], [])

        if REAL_SCALER:
            # this will fail until EpicsSignal.describe is fixed!
            self.assertEquals(d['dtype'], 'array')
            self.assertEquals(d['shape'], [4096, ])

    def test_signals(self):
        mca = EpicsMCA(devs[0], name='mca')
        mca.wait_for_connection()
        mca.mode.put(MCAMode.PHA)
        mca.stage()
        mca.start.put(1)
        mca._stop.put(1)
        mca.preset_real_time.put(3.14)
        mca.preset_live_time.put(3.14)
        mca.erase_start.put(1)
        mca.stop()
        mca.unstage()

    def test_rois(self):
        # iterables only
        self.assertRaises(TypeError, add_rois, 1)
        # check range
        self.assertRaises(ValueError, add_rois, [-1, ])
        self.assertRaises(ValueError, add_rois, [32, ])
        # read-only?
        mca = EpicsMCA(devs[0])
        self.assertRaises(ReadOnlyError, mca.rois.roi1.count.put, 3.14)
        self.assertRaises(ReadOnlyError, mca.rois.roi1.net_count.put, 3.14)


class DxpTests(unittest.TestCase):

    def test_signals(self):
        # NOTE: values used below are those currently used at 23id2
        mca = DxpMCA(devs[1], name='mca')
        mca.wait_for_connection()
        mca.preset_mode.put(DxpPresetMode.Real_time)
        mca.stage()
        mca.unstage()

        mca.trigger_peaking_time.put(0.2)
        mca.trigger_threshold.put(0.6)
        mca.trigger_gap_time.put(0.0)
        mca.max_width.put(1.0)
        mca.peaking_time.put(0.25)
        mca.energy_threshold.put(0.35)
        mca.gap_time.put(0.05)

        mca.baseline_cut_percent.put(5.0)
        mca.baseline_cut_enable.put(1)
        mca.baseline_filter_length.put(128)
        mca.baseline_threshold.put(0.20)

        mca.preamp_gain.put(5.5)
        mca.detector_polarity.put(1)
        mca.reset_delay.put(10.0)
        mca.decay_time.put(50.0)
        mca.max_energy.put(2.0)
        mca.adc_percent_rule.put(5.0)

        # read-only
        self.assertRaises(ReadOnlyError, mca.triggers.put, 2)
        self.assertRaises(ReadOnlyError, mca.events.put, 2)
        self.assertRaises(ReadOnlyError, mca.overflows.put, 2)
        self.assertRaises(ReadOnlyError, mca.underflows.put, 2)
        self.assertRaises(ReadOnlyError, mca.input_count_rate.put, 2)
        self.assertRaises(ReadOnlyError, mca.output_count_rate.put, 2)


is_main = (__name__ == '__main__')
main(is_main)
