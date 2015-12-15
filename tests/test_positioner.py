from __future__ import print_function

import time
import logging
import unittest
from copy import copy

import epics
from ophyd.controls import (Positioner, PVPositioner, EpicsMotor)
from ophyd.controls import (EpicsSignal, EpicsSignalRO)
from ophyd.controls import (Component as C)

logger = logging.getLogger(__name__)


def setUpModule():
    pass


def tearDownModule():
    logger.debug('Cleaning up')


class PositionerTests(unittest.TestCase):
    sim_pv = 'XF:31IDA-OP{Tbl-Ax:X1}Mtr'

    def test_positioner(self):
        p = Positioner(name='test', egu='egu')

        def cb_pos(value=None, **kwargs):
            pass

        self.assertEquals(p.egu, 'egu')
        self.assertEquals(p.limits, (0, 0))

        p.subscribe(cb_pos)

        p.move(0, timeout=2, wait=True)
        self.assertFalse(p.moving)
        res = p.move(1, wait=False)

        self.assertTrue(res.done)
        self.assertEqual(res.error, 0)
        self.assertGreater(res.elapsed, 0)

        repr(res)
        str(res)
        repr(p)
        str(p)

        p.stop()

        p.position

        pc = copy(p)
        self.assertEqual(pc._timeout, p._timeout)
        self.assertEqual(pc.egu, p.egu)

    def test_epicsmotor(self):
        m = EpicsMotor(self.sim_pv, name='epicsmotor')
        print('epicsmotor', m)
        m.wait_for_connection()

        m.limits
        m.check_value(0)

        m.stop()
        m.move(0.0, timeout=5, wait=True)
        time.sleep(0.1)
        self.assertEqual(m.position, 0.0)
        m.move(0.1, timeout=5, wait=True)
        time.sleep(0.1)
        self.assertEqual(m.position, 0.1)
        m.move(0.1, timeout=5, wait=True)
        time.sleep(0.1)
        self.assertEqual(m.position, 0.1)
        m.move(0.0, timeout=5, wait=True)
        time.sleep(0.1)
        self.assertEqual(m.position, 0.0)

        repr(m)
        str(m)

        mc = copy(m)
        self.assertEqual(mc.prefix, m.prefix)

        res = m.move(0.2, wait=False)

        while not res.done:
            time.sleep(0.1)

        time.sleep(0.1)
        self.assertEqual(m.position, 0.2)

        self.assertTrue(res.done)
        self.assertEqual(res.error, 0)
        self.assertGreater(res.elapsed, 0)

        m.read()
        m.report


from . import main
is_main = (__name__ == '__main__')
main(is_main)
