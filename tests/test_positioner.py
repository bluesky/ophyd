

import time
import logging
import unittest
from copy import copy
from unittest.mock import Mock

import epics
from ophyd import (SoftPositioner, PVPositioner, EpicsMotor)
from ophyd import (EpicsSignal, EpicsSignalRO)
from ophyd import (Component as C)

logger = logging.getLogger(__name__)


def setUpModule():
    pass


def tearDownModule():
    logger.debug('Cleaning up')


class PositionerTests(unittest.TestCase):
    sim_pv = 'XF:31IDA-OP{Tbl-Ax:X1}Mtr'

    def test_positioner(self):
        p = SoftPositioner(name='test', egu='egu', limits=(-10, 10))

        position_callback = Mock()
        started_motion_callback = Mock()
        finished_motion_callback = Mock()

        self.assertEqual(p.egu, 'egu')
        self.assertEqual(p.limits, (0, 0))

        p.subscribe(position_callback, event_type=p.SUB_READBACK)
        p.subscribe(started_motion_callback, event_type=p.SUB_START)
        p.subscribe(finished_motion_callback, event_type=p.SUB_DONE)

        target_pos = 0
        p.move(target_pos, timeout=2, wait=True)
        self.assertFalse(p.moving)
        self.assertEqual(p.position, target_pos)

        position_callback.assert_called_once_with(obj=p, value=target_pos,
                                                  sub_type=p.SUB_READBACK,
                                                  timestamp=unittest.mock.ANY)
        started_motion_callback.assert_called_once_with(obj=p,
                                                        sub_type=p.SUB_START,
                                                        timestamp=unittest.mock.ANY)
        finished_motion_callback.assert_called_once_with(obj=p,
                                                         sub_type=p.SUB_DONE,
                                                         value=None,
                                                         timestamp=unittest.mock.ANY)
        position_callback.reset_mock()
        started_motion_callback.reset_mock()
        finished_motion_callback.reset_mock()

        target_pos = 1
        res = p.move(target_pos, wait=False)

        self.assertTrue(res.done)
        self.assertEqual(res.error, 0)
        self.assertGreater(res.elapsed, 0)
        self.assertEqual(p.position, target_pos)
        position_callback.assert_called_once_with(obj=p, value=target_pos,
                                                  sub_type=p.SUB_READBACK,
                                                  timestamp=unittest.mock.ANY)
        started_motion_callback.assert_called_once_with(obj=p,
                                                        sub_type=p.SUB_START,
                                                        timestamp=unittest.mock.ANY)
        finished_motion_callback.assert_called_once_with(obj=p,
                                                         sub_type=p.SUB_DONE,
                                                         value=None,
                                                         timestamp=unittest.mock.ANY)

        repr(res)
        str(res)
        repr(p)
        str(p)

        p.stop()

        p.position

        pc = copy(p)
        self.assertEqual(pc.egu, p.egu)
        self.assertEqual(pc.limits, p.limits)

    def test_epicsmotor(self):
        m = EpicsMotor(self.sim_pv, name='epicsmotor')
        print('epicsmotor', m)
        m.wait_for_connection()

        m.limits
        m.check_value(0)

        m.stop()
        logger.debug('Move to 0.0')
        m.move(0.0, timeout=5, wait=True)
        time.sleep(0.1)
        self.assertEqual(m.position, 0.0)

        logger.debug('Move to 0.1')
        m.move(0.1, timeout=5, wait=True)
        time.sleep(0.1)
        self.assertEqual(m.position, 0.1)

        logger.debug('Move to 0.1, again')
        m.move(0.1, timeout=5, wait=True)
        time.sleep(0.1)
        self.assertEqual(m.position, 0.1)

        logger.debug('Move to 0.0')
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
