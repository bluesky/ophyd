import time
import logging
import unittest

from ophyd import (Device, Component)
from ophyd.signal import Signal

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
    d = Device('test')

    d.stage()
    old, new = d.configure({})
    assert old == new
    d.unstage()


class DeviceTests(unittest.TestCase):
    def test_attrs(self):
        class MyDevice(Device):
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

    def test_complexdevice(self):
        class SubDevice(Device):
            cpt1 = Component(FakeSignal, '1')
            cpt2 = Component(FakeSignal, '2')
            cpt3 = Component(FakeSignal, '3')

        class SubSubDevice(SubDevice):
            pass

        class MyDevice(Device):
            sub_cpt1 = Component(SubDevice, '1')
            sub_cpt2 = Component(SubSubDevice, '2')
            cpt3 = Component(FakeSignal, '3')

        device = MyDevice('prefix')
        self.assertIs(device.sub_cpt1.parent, device)
        self.assertIs(device.sub_cpt2.parent, device)
        self.assertIs(device.cpt3.parent, device)

        self.assertEquals(device.sub_cpt1.signal_names,
                          ['cpt1', 'cpt2', 'cpt3'])
        self.assertEquals(device.sub_cpt2.signal_names,
                          ['cpt1', 'cpt2', 'cpt3'])

    def test_name_shadowing(self):
        RESERVED_ATTRS = ['name', 'parent', 'signal_names', '_signals',
                          'read_attrs', 'configuration_attrs', 'monitor_attrs',
                          '_sig_attrs', '_sub_devices']

        type('a', (Device,), {'a': None})  # legal class definition
        # Illegal class definitions:
        for attr in RESERVED_ATTRS:
            self.assertRaises(TypeError, type, 'a', (Device,), {attr: None})
