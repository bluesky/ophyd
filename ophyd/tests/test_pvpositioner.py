import time
import logging
from copy import copy

from ophyd import (PVPositioner, PVPositionerPC, EpicsMotor)
from ophyd import (EpicsSignal, EpicsSignalRO)
from ophyd import (Component as C)
from ophyd import get_cl
from ophyd.ophydobj import Kind
from .conftest import AssertTools

logger = logging.getLogger(__name__)


def setUpModule():
    logging.getLogger('ophyd.pv_positioner').setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)


def tearDownModule():
    logger.debug('Cleaning up')
    logging.getLogger('ophyd.pv_positioner').setLevel(logging.INFO)
    logger.setLevel(logging.INFO)


class TestPVPos(AssertTools):
    sim_pv = 'XF:31IDA-OP{Tbl-Ax:X1}Mtr'
    # sim_pv = 'sim:mtr1'

    fake_motor = {'readback': 'XF:31IDA-OP{Tbl-Ax:FakeMtr}-I',
                  'setpoint': 'XF:31IDA-OP{Tbl-Ax:FakeMtr}-SP',
                  'moving': 'XF:31IDA-OP{Tbl-Ax:FakeMtr}Sts:Moving-Sts',
                  'actuate': 'XF:31IDA-OP{Tbl-Ax:FakeMtr}Cmd:Go-Cmd.PROC',
                  'stop': 'XF:31IDA-OP{Tbl-Ax:FakeMtr}Cmd:Stop-Cmd.PROC',
                  }

    def test_not_subclassed(self):
        # can't instantiate it on its own
        self.assertRaises(TypeError, PVPositioner, 'prefix')
        self.assertRaises(TypeError, PVPositionerPC, 'prefix')

    def test_no_setpoint_or_readback(self):
        class MyPositioner(PVPositioner):
            pass

        self.assertRaises(ValueError, MyPositioner)

    def test_setpoint_but_no_done(self):
        class MyPositioner(PVPositioner):
            setpoint = C(EpicsSignal, '.VAL')

        self.assertRaises(ValueError, MyPositioner)

    def test_pvpos(self):
        motor_record = self.sim_pv
        mrec = EpicsMotor(motor_record, name='pvpos_mrec')
        print('mrec', mrec.describe())
        mrec.wait_for_connection()

        class MyPositioner(PVPositioner):
            '''Setpoint, readback, done, stop. No put completion'''
            setpoint = C(EpicsSignal, '.VAL')
            readback = C(EpicsSignalRO, '.RBV')
            done = C(EpicsSignalRO, '.MOVN')
            stop_signal = C(EpicsSignal, '.STOP')

            stop_value = 1
            done_value = 0

        m = MyPositioner(motor_record, name='pos_no_put_compl')
        m.wait_for_connection()

        m.read()

        mrec.move(0.1, wait=True)
        time.sleep(0.1)
        self.assertEqual(m.position, 0.1)

        m.stop()
        m.limits

        repr(m)
        str(m)

        mc = copy(m)
        self.assertEqual(mc.describe(), m.describe())

        m.read()

    def test_put_complete_setpoint_only(self):
        motor_record = self.sim_pv
        # mrec = EpicsMotor(motor_record, name='pcomplete_mrec')
        # print('mrec', mrec.describe())
        # mrec.wait_for_connection()

        logger.info('--> PV Positioner, using put completion and a DONE pv')

        class MyPositioner(PVPositionerPC):
            '''Setpoint only'''
            setpoint = C(EpicsSignal, '.VAL')

        pos = MyPositioner(motor_record, name='pc_setpoint_done')
        print(pos.describe())
        pos.wait_for_connection()

        pos.read()
        high_lim = pos.setpoint.high_limit
        try:
            pos.check_value(high_lim + 1)
        except ValueError as ex:
            logger.info('Check value for single failed, as expected (%s)', ex)
        else:
            raise ValueError('check_value should have failed')

        stat = pos.move(1, wait=False)
        logger.info('--> post-move request, moving=%s', pos.moving)

        while not stat.done:
            logger.info('--> moving... %s error=%s', stat, stat.error)
            time.sleep(0.1)

        pos.move(-1, wait=True)
        self.assertFalse(pos.moving)

    def test_put_complete_setpoint_readback_done(self):
        class MyPositioner(PVPositionerPC):
            '''Setpoint, readback, done, stop. Put completion'''
            setpoint = C(EpicsSignal, '.VAL')
            readback = C(EpicsSignalRO, '.RBV')
            done = C(EpicsSignalRO, '.MOVN')
            done_value = 0

        motor_record = self.sim_pv
        pos = MyPositioner(motor_record, name='pos_no_put_compl',
                           settle_time=0.1, timeout=25.0)
        print(pos.describe())
        pos.wait_for_connection()

        self.assertEqual(pos.settle_time, 0.1)
        self.assertEqual(pos.timeout, 25.0)
        pos.read()
        high_lim = pos.setpoint.high_limit
        try:
            pos.check_value(high_lim + 1)
        except ValueError as ex:
            logger.info('Check value for single failed, as expected (%s)', ex)
        else:
            raise ValueError('check_value should have failed')

        stat = pos.move(1, wait=False)
        self.assertEqual(stat.timeout, pos.timeout)
        logger.info('--> post-move request, moving=%s', pos.moving)

        while not stat.done:
            logger.info('--> moving... %s error=%s', stat, stat.error)
            time.sleep(0.1)

        pos.move(-1, wait=True)
        self.assertFalse(pos.moving)

    def test_put_complete_setpoint_readback(self):
        class MyPositioner(PVPositionerPC):
            '''Setpoint, readback, put completion. No done pv.'''
            setpoint = C(EpicsSignal, '.VAL')
            readback = C(EpicsSignalRO, '.RBV')

        motor_record = self.sim_pv
        pos = MyPositioner(motor_record, name='pos_put_compl')
        print(pos.describe())
        pos.wait_for_connection()

        stat = pos.move(2, wait=False)
        logger.info('--> post-move request, moving=%s', pos.moving)

        while not stat.done:
            logger.info('--> moving... %s', stat)
            time.sleep(0.1)

        pos.move(0, wait=True)
        logger.info('--> synchronous move request, moving=%s', pos.moving)

        time.sleep(0.1)
        print('read', pos.read())
        self.assertFalse(pos.moving)

    def test_pvpositioner_with_fake_motor(self):
        def callback(sub_type=None, timestamp=None, value=None, **kwargs):
            logger.info('[callback] [%s] (type=%s) value=%s', timestamp,
                        sub_type, value)

        def done_moving(value=0.0, **kwargs):
            logger.info('Done moving %s', kwargs)
        cl = get_cl()
        # ensure we start at 0 for this simple test
        fm = self.fake_motor
        cl.caput(fm['setpoint'], 0.05)
        time.sleep(0.5)
        cl.caput(fm['actuate'], 1)
        time.sleep(0.5)
        cl.caput(fm['setpoint'], 0)
        time.sleep(0.5)
        cl.caput(fm['actuate'], 1)
        time.sleep(0.5)

        class MyPositioner(PVPositioner):
            '''Setpoint, readback, no put completion. No done pv.'''
            setpoint = C(EpicsSignal, fm['setpoint'])
            readback = C(EpicsSignalRO, fm['readback'])
            actuate = C(EpicsSignal, fm['actuate'])
            stop_signal = C(EpicsSignal, fm['stop'])
            done = C(EpicsSignal, fm['moving'])

            actuate_value = 1
            stop_value = 1
            done_value = 1

        pos = MyPositioner('', name='pv_pos_fake_mtr')
        print('fake mtr', pos.describe())
        pos.wait_for_connection()

        pos.subscribe(callback, event_type=pos.SUB_DONE)
        pos.subscribe(callback, event_type=pos.SUB_READBACK)

        logger.info('---- test #1 ----')
        logger.info('--> move to 1')
        pos.move(1, timeout=5)
        self.assertEqual(pos.position, 1)
        logger.info('--> move to 0')
        pos.move(0, timeout=5)
        self.assertEqual(pos.position, 0)

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
        logger.info('--> post-move request, moving=%s', pos.moving)
        time.sleep(2)

        pos.read()
        repr(pos)
        str(pos)

    def test_pvpositioner_pc_with_actuate(self):
        # TODO
        self.skipTest('TODO')

    def test_hints(self):
        fm = self.fake_motor

        class MyPositioner(PVPositioner):
            '''Setpoint, readback, no put completion. No done pv.'''
            setpoint = C(EpicsSignal, fm['setpoint'])
            readback = C(EpicsSignalRO, fm['readback'])
            actuate = C(EpicsSignal, fm['actuate'])
            stop_signal = C(EpicsSignal, fm['stop'])
            done = C(EpicsSignal, fm['moving'])

            actuate_value = 1
            stop_value = 1
            done_value = 1

        motor = MyPositioner('', name='pv_pos_fake_mtr')

        desc = motor.describe()
        f_hints = motor.hints['fields']
        assert len(f_hints) > 0
        for k in f_hints:
            assert k in desc

        motor.readback.kind = Kind.hinted
        assert motor.hints == {'fields': ['pv_pos_fake_mtr_readback']}

        assert motor.hints['fields'] == f_hints
