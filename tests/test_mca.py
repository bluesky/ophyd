from __future__ import print_function

import logging
import unittest
import time
from copy import copy

import epics

from ophyd import EpicsMCA, EpicsDXP
from ophyd.mca import add_rois
from ophyd.utils import enum, ReadOnlyError
from .test_signal import FakeEpicsPV
from . import main

MCAMode = enum(PHA='PHA', MCS='MCS', List='List')
DxpPresetMode = enum(No_preset='No preset',
                     Real_time='Real time',
                     Live_time='Live time')

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
        dxp = EpicsDXP(devs[1], name='dxp')
        dxp.wait_for_connection()
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
        self.assertRaises(ReadOnlyError, dxp.triggers.put, 2)
        self.assertRaises(ReadOnlyError, dxp.events.put, 2)
        self.assertRaises(ReadOnlyError, dxp.overflows.put, 2)
        self.assertRaises(ReadOnlyError, dxp.underflows.put, 2)
        self.assertRaises(ReadOnlyError, dxp.input_count_rate.put, 2)
        self.assertRaises(ReadOnlyError, dxp.output_count_rate.put, 2)


is_main = (__name__ == '__main__')
main(is_main)
