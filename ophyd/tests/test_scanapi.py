from __future__ import print_function
import logging
import unittest

import numpy as np
from numpy.testing import assert_array_equal

from ophyd.controls import EpicsMotor
from ophyd.session import get_session_manager
from .config import motor_recs


server = None
logger = logging.getLogger(__name__)
session = get_session_manager()


def setUpModule():
    pass


def tearDownModule():
    pass


class ScanAPI(unittest.TestCase):
    def test_1d(self):
        pass


from . import main
is_main = (__name__ == '__main__')
main(is_main)
