from __future__ import print_function

import time
import logging
import unittest
from copy import copy

import epics
from ophyd.controls.positioner import (Positioner, PVPositioner, EpicsMotor)
from ophyd.session import get_session_manager

server = None
logger = logging.getLogger(__name__)
session = get_session_manager()


def setUpModule():
    global server

    # epics.PV = FakeEpicsPV


def tearDownModule():
    if __name__ == '__main__':
        epics.ca.destroy_context()

    logger.debug('Cleaning up')


class PositionerTests(unittest.TestCase):
    sim_pv = 'XF:31IDA-OP{Tbl-Ax:X1}Mtr'

    def test_positioner(self):
        p = Positioner(name='test')

        def cb_pos(value=None, **kwargs):
            pass

        p.subscribe(cb_pos)

        p.move(0, wait=True)
        self.assertFalse(p.moving)
        res = p.move(1, wait=False)

        self.assertTrue(res.done)
        self.assertEquals(res.error, 0)
        self.assertGreater(res.elapsed, 0)

        repr(res)
        str(res)
        repr(p)
        str(p)

        p.stop()

        p.position

        pc = copy(p)
        self.assertEquals(pc.position, p.position)
        self.assertEquals(pc.moving, p.moving)
        self.assertEquals(pc._timeout, p._timeout)
        self.assertEquals(pc.egu, p.egu)

        p.set_trajectory([1, 2, 3])
        p.move_next()
        p.move_next()
        p.move_next()
        try:
            p.move_next()
        except StopIteration:
            pass

    def test_epicsmotor(self):
        m = EpicsMotor(self.sim_pv)

        m.limits
        m.check_value(0)

        m.stop()
        m.move(0.0, wait=True)
        time.sleep(0.1)
        self.assertEquals(m.position, 0.0)
        m.move(0.1, wait=True)
        time.sleep(0.1)
        self.assertEquals(m.position, 0.1)
        m.move(0.1, wait=True)
        time.sleep(0.1)
        self.assertEquals(m.position, 0.1)
        m.move(0.0, wait=True)
        time.sleep(0.1)
        self.assertEquals(m.position, 0.0)

        repr(m)
        str(m)

        mc = copy(m)
        self.assertEquals(mc.record, m.record)

        res = m.move(0.2, wait=False)

        while not res.done:
            time.sleep(0.1)

        time.sleep(0.1)
        self.assertEquals(m.position, 0.2)

        self.assertTrue(res.done)
        self.assertEquals(res.error, 0)
        self.assertGreater(res.elapsed, 0)

        m.read()
        m.report


class PVPosTest(unittest.TestCase):
    sim_pv = 'XF:31IDA-OP{Tbl-Ax:X1}Mtr'

    fake_motor = {'readback': 'XF:31IDA-OP{Tbl-Ax:FakeMtr}-I',
                  'setpoint': 'XF:31IDA-OP{Tbl-Ax:FakeMtr}-SP',
                  'moving': 'XF:31IDA-OP{Tbl-Ax:FakeMtr}Sts:Moving-Sts',
                  'actuate': 'XF:31IDA-OP{Tbl-Ax:FakeMtr}Cmd:Go-Cmd.PROC',
                  'stop': 'XF:31IDA-OP{Tbl-Ax:FakeMtr}Cmd:Stop-Cmd.PROC',
                  }

    def test_pvpos(self):
        motor_record = self.sim_pv
        mrec = EpicsMotor(motor_record)

        m = PVPositioner(mrec.field_pv('VAL'))
        try:
            m.stop()
        except RuntimeError:
            pass

        m = PVPositioner(mrec.field_pv('VAL'),
                         readback=mrec.field_pv('RBV'),
                         done=mrec.field_pv('MOVN'), done_val=0,
                         stop=mrec.field_pv('STOP'), stop_val=1,
                         )

        m.report
        m.read()

        mrec.move(0.1, wait=True)
        time.sleep(0.1)
        self.assertEquals(m.position, 0.1)

        m.stop()
        m.limits

        repr(m)
        str(m)

        mc = copy(m)
        self.assertEquals(mc.report, m.report)

        m.report
        m.read()

    def test_put_complete(self):
        motor_record = self.sim_pv
        mrec = EpicsMotor(motor_record)

        logger.info('--> PV Positioner, using put completion and a DONE pv')
        # PV positioner, put completion, done pv
        pos = PVPositioner(mrec.field_pv('VAL'),
                           readback=mrec.field_pv('RBV'),
                           done=mrec.field_pv('MOVN'), done_val=0,
                           put_complete=True,
                           )

        pos.report
        pos.read()
        high_lim = pos._setpoint.high_limit
        try:
            pos.check_value(high_lim + 1)
        except ValueError as ex:
            logger.info('Check value for single failed, as expected (%s)' % ex)
        else:
            raise ValueError('check_value should have failed')

        stat = pos.move(1, wait=False)
        logger.info('--> post-move request, moving=%s' % pos.moving)

        while not stat.done:
            logger.info('--> moving... %s error=%s' % (stat, stat.error))
            time.sleep(0.1)

        pos.move(-1, wait=True)
        self.assertFalse(pos.moving)

        logger.info('--> PV Positioner, using put completion and no DONE pv')

        # PV positioner, put completion, no done pv
        pos = PVPositioner(mrec.field_pv('VAL'),
                           readback=mrec.field_pv('RBV'),
                           put_complete=True,
                           )

        stat = pos.move(2, wait=False)
        logger.info('--> post-move request, moving=%s' % pos.moving)

        while not stat.done:
            logger.info('--> moving... %s' % stat)
            time.sleep(0.1)

        pos.move(0, wait=True)
        logger.info('--> synchronous move request, moving=%s' % pos.moving)

        self.assertFalse(pos.moving)

        pos.report
        pos.read()

    def test_pvpositioner(self):
        def callback(sub_type=None, timestamp=None, value=None, **kwargs):
            logger.info('[callback] [%s] (type=%s) value=%s' % (timestamp, sub_type, value))

        def done_moving(value=0.0, **kwargs):
            logger.info('Done moving %s' % (kwargs, ))

        # ensure we start at 0 for this simple test
        fm = self.fake_motor
        epics.caput(fm['setpoint'], 0)
        epics.caput(fm['actuate'], 1)
        time.sleep(2)

        pos = PVPositioner(fm['setpoint'],
                           readback=fm['readback'],
                           act=fm['actuate'], act_val=1,
                           stop=fm['stop'], stop_val=1,
                           done=fm['moving'], done_val=1,
                           put_complete=False,
                           )

        pos.subscribe(callback, event_type=pos.SUB_DONE)

        pos.subscribe(callback, event_type=pos.SUB_READBACK)

        logger.info('---- test #1 ----')
        logger.info('--> move to 1')
        pos.move(1)
        self.assertEquals(pos.position, 1)
        logger.info('--> move to 0')
        pos.move(0)
        self.assertEquals(pos.position, 0)

        logger.info('---- test #2 ----')
        logger.info('--> move to 1')
        pos.move(1, wait=False)
        time.sleep(0.5)
        logger.info('--> stop')
        pos.stop()
        logger.info('--> sleep')
        time.sleep(1)
        logger.info('--> move to 0')
        pos.move(0, wait=False, moved_cb=done_moving)
        logger.info('--> post-move request, moving=%s' % pos.moving)
        time.sleep(2)

        pos.report
        pos.read()
        repr(pos)
        str(pos)


from . import main
is_main = (__name__ == '__main__')
main(is_main)
