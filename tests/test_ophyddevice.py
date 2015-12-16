import time
import logging
import unittest

from ophyd.controls import (OphydDevice, Component)
from ophyd.controls.signal import Signal

logger = logging.getLogger(__name__)


class FakeSignal(Signal):
    def __init__(self, read_pv, *, name=None, parent=None):
        self.read_pv = read_pv
        super().__init__(name=name, parent=parent)

    def get(self):
        return self.name


def setUpModule():
    pass


def tearDownModule():
    logger.debug('Cleaning up')


def test_device_state():
    d = OphydDevice('test')

    d.stage()
    old, new = d.configure()
    d.unstage()


class DeviceTests(unittest.TestCase):
    def test_attrs(self):
        class MyDevice(OphydDevice):
            cpt1 = Component(FakeSignal, '1')
            cpt2 = Component(FakeSignal, '2')
            cpt3 = Component(FakeSignal, '3')

        d = MyDevice('prefix', read_attrs=['cpt1'],
                     configuration_attrs=['cpt2'],
                     monitor_attrs=['cpt3']
                     )

        d.read()
        self.assertEqual(d.read_attrs, ['cpt1'])
        self.assertEqual(d.configuration_attrs, ['cpt2'])
        self.assertEqual(d.monitor_attrs, ['cpt3'])

        self.assertEqual(list(d.read().keys()), [d.cpt1.name])
        self.assertEqual(list(d.read_configuration().keys()), [d.cpt2.name])

        self.assertEqual(list(d.describe().keys()), [d.cpt1.name])
        self.assertEqual(list(d.describe_configuration().keys()),
                         [d.cpt2.name])
