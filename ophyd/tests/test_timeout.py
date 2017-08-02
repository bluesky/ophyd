import time
import logging
import unittest

from ophyd import (Device, Component, FormattedComponent)
from ophyd.signal import Signal
from ophyd import EpicsSignal

logger = logging.getLogger(__name__)


class TimeoutTests(unittest.TestCase):
    def test_timeout(self):
        class SubSubDevice(Device):
            cpt5 = Component(EpicsSignal, '5')

        class SubDevice(Device):
            cpt4 = Component(EpicsSignal, '4')
            subsub1 = Component(SubSubDevice, 'sub_')

        class MyDevice(Device):
            sub1 = Component(EpicsSignal, '1')
            sub2 = Component(SubDevice, '_')
            cpt3 = Component(EpicsSignal, '3')

        device = MyDevice('prefix:', name='dev')
        with self.assertRaises(TimeoutError) as cm:
            device.wait_for_connection(timeout=1e-6)

        ex_msg = str(cm.exception)
        self.assertIn('dev.sub1', ex_msg)
        self.assertIn('dev.sub2.cpt4', ex_msg)
        self.assertIn('dev.sub2.subsub1.cpt5', ex_msg)
        self.assertIn('dev.cpt3', ex_msg)

        self.assertIn('prefix:1', ex_msg)
        self.assertIn('prefix:_4', ex_msg)
        self.assertIn('prefix:_sub_5', ex_msg)
        self.assertIn('prefix:3', ex_msg)
