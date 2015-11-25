from __future__ import print_function
import logging
import unittest

import numpy as np
from numpy.testing import assert_array_equal

import epics

from ophyd.controls import EpicsMotor
from ophyd.userapi import mov
from ophyd.session import get_session_manager
from .config import motor_recs


server = None
logger = logging.getLogger(__name__)
session = get_session_manager()


def setUpModule():
    pass


def tearDownModule():
    pass


class CliAPI(unittest.TestCase):
    def test_mov(self):
        mrec = motor_recs[0]

        try:
            mov('not_a_positioner', 0.0)
        except TypeError:
            pass
        else:
            self.fail('Non-positioner argument worked')

        m = EpicsMotor(mrec)
        mov(m, 0.0)


from . import main
is_main = (__name__ == '__main__')
main(is_main)
