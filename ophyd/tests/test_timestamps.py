import time
import logging
import unittest

from ophyd import (EpicsSignal, EpicsSignalRO, EpicsMotor)

from . import config
logger = logging.getLogger(__name__)


def setUpModule():
    pass


def tearDownModule():
    logger.debug('Cleaning up')


class EpicsSignalTests(unittest.TestCase):
    def test_read_pv_timestamp_no_monitor(self):
        mtr = EpicsMotor(config.motor_recs[0])
        mtr.wait_for_connection()

        sp = EpicsSignal(mtr.user_setpoint.pvname)
        rbv = EpicsSignalRO(mtr.user_readback.pvname)

        rbv_value0 = rbv.get()
        ts0 = rbv.timestamp
        sp.put(sp.value + 0.1, wait=True)
        time.sleep(0.1)

        rbv_value1 = rbv.get()
        ts1 = rbv.timestamp
        self.assertGreater(ts1, ts0)
        self.assertAlmostEqual(rbv_value0 + 0.1, rbv_value1)

        sp.put(sp.value - 0.1, wait=True)

    def test_write_pv_timestamp_no_monitor(self):
        mtr = EpicsMotor(config.motor_recs[0])
        mtr.wait_for_connection()

        sp = EpicsSignal(mtr.user_setpoint.pvname)

        sp_value0 = sp.get()
        ts0 = sp.timestamp
        sp.put(sp_value0 + 0.1, wait=True)
        time.sleep(0.1)

        sp_value1 = sp.get()
        ts1 = sp.timestamp
        self.assertGreater(ts1, ts0)
        self.assertAlmostEqual(sp_value0 + 0.1, sp_value1)

        sp.put(sp.value - 0.1, wait=True)

    def test_read_pv_timestamp_monitor(self):
        mtr = EpicsMotor(config.motor_recs[0])
        mtr.wait_for_connection()

        sp = EpicsSignal(mtr.user_setpoint.pvname, auto_monitor=True)
        rbv = EpicsSignalRO(mtr.user_readback.pvname, auto_monitor=True)

        rbv_value0 = rbv.get()
        ts0 = rbv.timestamp
        sp.put(rbv_value0 + 0.1, wait=True)
        time.sleep(0.2)

        rbv_value1 = rbv.get()
        ts1 = rbv.timestamp
        self.assertGreater(ts1, ts0)
        self.assertAlmostEqual(rbv_value0 + 0.1, rbv_value1)

        sp.put(sp.value - 0.1, wait=True)

    def test_write_pv_timestamp_monitor(self):
        mtr = EpicsMotor(config.motor_recs[0])
        mtr.wait_for_connection()

        sp = EpicsSignal(mtr.user_setpoint.pvname, auto_monitor=True)

        sp_value0 = sp.get()
        ts0 = sp.timestamp
        sp.put(sp_value0 + 0.1, wait=True)
        time.sleep(0.1)

        sp_value1 = sp.get()
        ts1 = sp.timestamp
        self.assertGreater(ts1, ts0)
        self.assertAlmostEqual(sp_value0 + 0.1, sp_value1)

        sp.put(sp.value - 0.1, wait=True)

from . import main
is_main = (__name__ == '__main__')
main(is_main)
