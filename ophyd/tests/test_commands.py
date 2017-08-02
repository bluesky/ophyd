
import logging
import unittest
# from unittest.mock import Mock
from contextlib import contextmanager

import ophyd.commands
from ophyd import EpicsMotor
from ophyd.commands import (mov, movr, set_pos, wh_pos, set_lm)
from ophyd.commands import (log_pos, log_pos_diff, log_pos_mov,
                            get_all_positioners, get_logbook, setup_ophyd)
from .config import motor_recs

logger = logging.getLogger(__name__)
mtr = None


def setUpModule():
    global mtr

    setup_ophyd()

    mtr = EpicsMotor(motor_recs[0])
    mtr.wait_for_connection()


def tearDownModule():
    pass


class SimpleOlogClient:
    def log(self, text=None, logbooks=None, tags=None, properties=None,
            attachments=None, verify=True, ensure=False):
        return None

    def find(self, id=None, **kwargs):
        if id != 1:
            return []

        pos = {'objects': ("[EpicsMotor('{0}', name='mtr')]"
                           "".format(motor_recs[0])),
               'values': 'dict(mtr=1.0)',
               }

        entry = dict(properties={'OphydPositioners': pos})
        return [entry]


def _get_logbook():
    return SimpleOlogClient()
    # import pyOlog
    # return Mock(pyOlog.SimpleOlogClient, instance=True)


@contextmanager
def mock_logbook():
    get_logbook = ophyd.commands.get_logbook
    ophyd.commands.get_logbook = _get_logbook
    try:
        yield
    finally:
        ophyd.commands.get_logbook = get_logbook


class Commands(unittest.TestCase):
    def test_move_absolute(self):
        global mtr

        self.assertRaises(TypeError, mov, 'not_a_positioner', 0.0)
        mov(mtr, 0.0)

    def test_move_relative(self):
        global mtr

        self.assertRaises(TypeError, movr, 'not_a_positioner', 0.0)
        mov(mtr, 0.0)

    def test_wh_pos(self):
        global mtr
        self.assertRaises(TypeError, wh_pos, 'not_a_positioner')

        wh_pos()
        wh_pos(mtr)
        wh_pos([mtr] * 10)
        self.assertRaises(TypeError, wh_pos, [mtr, None])

    def test_set_limits(self):
        global mtr
        set_lm(mtr, mtr.limits)
        self.assertRaises(TypeError, set_lm, mtr, None)
        set_lm([mtr, mtr], [mtr.limits, mtr.limits])
        self.assertRaises(TypeError, set_lm, [mtr, mtr], [mtr.limits, None])

    def test_set_position(self):
        global mtr
        set_pos(mtr, mtr.position)
        self.assertRaises(TypeError, set_pos, mtr, None)
        set_pos([mtr, mtr], [mtr.position, mtr.position])

    def test_get_all_positioners(self):
        # TODO: mock up IPython session
        get_all_positioners()

    def test_get_logbook(self):
        # TODO: can't test without IPython session
        get_logbook()
        with mock_logbook():
            get_logbook()

    def test_log_pos(self):
        global mtr
        log_pos()

        with mock_logbook():
            log_pos()
            log_pos(mtr)
            log_pos([mtr, mtr])
            self.assertRaises(TypeError, log_pos, [mtr, None])

    def test_log_pos_diff(self):
        global mtr
        with mock_logbook():
            log_pos_diff(id=1, positioners=[mtr])
            self.assertRaises(ValueError, log_pos_diff, id=2, positioners=[mtr])


from . import main
is_main = (__name__ == '__main__')
main(is_main)
