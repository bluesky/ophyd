from __future__ import print_function
import logging

from ophyd.controls import OphydDevice

logger = logging.getLogger(__name__)


def setUpModule():
    pass


def tearDownModule():
    logger.debug('Cleaning up')


def test_device_state():
    d = OphydDevice('test')

    d.stage()
    old, new = d.configure()
    d.unstage()
