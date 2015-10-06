from __future__ import print_function

import logging
import unittest

import epics
from ophyd.controls.positioner import (EpicsMotor, PVPositioner)
from ophyd.controls.cas import CasMotor
from ophyd.session import get_session_manager

server = None
logger = logging.getLogger(__name__)
session = get_session_manager()


def setUpModule():
    global server

    # epics.PV = FakeEpicsPV
    from . import get_caserver
    server = get_caserver()
    server._pv_idx = 0


def tearDownModule():
    if __name__ == '__main__':
        epics.ca.destroy_context()

    logger.debug('Cleaning up')


class PositionerTests(unittest.TestCase):
    motor = 'XF:31IDA-OP{Tbl-Ax:X1}Mtr'

    def test_positioner(self):
        mrec = EpicsMotor(self.motor)

        logger.info('--> PV Positioner, using put completion and a DONE pv')
        # PV positioner, put completion, done pv
        pos = PVPositioner(mrec.field_pv('VAL'),
                           readback=mrec.field_pv('RBV'),
                           done=mrec.field_pv('MOVN'), done_val=0,
                           stop=mrec.field_pv('STOP'), stop_val=1,
                           put_complete=True,
                           limits=(-2, 2),
                           egu='unknown',
                           )

        def updated(value=None, **kwargs):
            logger.debug('Updated to: %s' % value)

        cas_motor = CasMotor('m1', pos, server=server)
        logger.debug('severity %s' % cas_motor.severity)
        record_name = cas_motor.full_pvname
        for i in range(2):
            epics.caput(record_name, i, wait=True)
            logger.debug('position %s' % pos.position)

        repr(cas_motor)
        str(cas_motor)

        # cas_motor.tweak_forward()
        # cas_motor.tweak_reverse()

        cas = cas_motor
        epics.caput(record_name, -3, wait=True)  # < low lim
        epics.caput(record_name, 3, wait=True)  # > high lim
        epics.caput(record_name, 0, wait=True)  # ok

        cas[cas._fld_readback].value = 1
        cas[cas._fld_tweak_val].value = 1
        cas[cas._fld_tweak_fwd].value = 1
        cas[cas._fld_tweak_rev].value = 1
        cas[cas._fld_egu].value = 'egu'
        cas[cas._fld_moving].value = 0
        cas[cas._fld_done_move].value = 1
        cas[cas._fld_stop].value = 1
        cas[cas._fld_status].value = 1
        cas[cas._fld_low_lim].value = 1
        cas[cas._fld_high_lim].value = 1
        cas[cas._fld_calib_set].value = 1
        cas[cas._fld_limit_viol].value = 1
        return cas_motor


from . import main
is_main = (__name__ == '__main__')
main(is_main)
