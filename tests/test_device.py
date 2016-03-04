import time
import logging
import unittest

from ophyd import (Device, Component, FormattedComponent)
from ophyd.signal import Signal
from ophyd.utils import ExceptionBundle

logger = logging.getLogger(__name__)


class FakeSignal(Signal):
    def __init__(self, read_pv, *, name=None, parent=None):
        self.read_pv = read_pv
        super().__init__(name=name, parent=parent)

    def get(self):
        return self.name

    def describe_configuration(self):
        return {self.name + '_conf': {'source': 'SIM:test'}}

    def read_configuration(self):
        return {self.name + '_conf': {'value': 0}}


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
        self.assertEqual(set(d.read_configuration().keys()),
                         {d.cpt2.name, d.cpt2.name + '_conf'})

        self.assertEqual(list(d.describe().keys()), [d.cpt1.name])
        self.assertEqual(set(d.describe_configuration().keys()),
                         {d.cpt2.name, d.cpt2.name + '_conf'})

    def test_complexdevice(self):
        class SubDevice(Device):
            cpt1 = Component(FakeSignal, '1')
            cpt2 = Component(FakeSignal, '2')
            cpt3 = Component(FakeSignal, '3')

        class SubSubDevice(SubDevice):
            cpt4 = Component(FakeSignal, '4')

        class MyDevice(Device):
            sub1 = Component(SubDevice, '1')
            subsub2 = Component(SubSubDevice, '2')
            cpt3 = Component(FakeSignal, '3')

        device = MyDevice('prefix', name='dev')
        device.configuration_attrs = ['sub1',
                                      'subsub2.cpt2',
                                      'subsub2.cpt4',
                                      'cpt3']
        device.sub1.read_attrs = ['cpt2']
        device.sub1.configuration_attrs = ['cpt1']

        self.assertIs(device.sub1.parent, device)
        self.assertIs(device.subsub2.parent, device)
        self.assertIs(device.cpt3.parent, device)

        self.assertEquals(device.sub1.signal_names,
                          ['cpt1', 'cpt2', 'cpt3'])
        self.assertEquals(device.subsub2.signal_names,
                          ['cpt1', 'cpt2', 'cpt3', 'cpt4'])

        conf_keys = {'dev_sub1_cpt1_conf',    # from sub1.*
                     # 'dev_sub1_cpt2_conf',  # not in sub1.config_attrs
                     'dev_subsub2_cpt2_conf', # from subsub2.cpt2
                     'dev_subsub2_cpt4_conf', # from subsub2.cpt4
                     'dev_cpt3_conf',         # from cpt3

                     'dev_sub1_cpt1',         # from sub1.*
                     'dev_sub1_cpt2',         # from sub1.*
                                              #  (and sub1.read_attrs)
                     'dev_subsub2_cpt2',      # from subsub2.cpt2
                     'dev_subsub2_cpt4',      # from subsub2.cpt4
                     'dev_cpt3'               # from cpt3
                     }

        self.assertEquals(set(device.describe_configuration().keys()),
                          conf_keys)
        self.assertEquals(set(device.read_configuration().keys()),
                          conf_keys)

    def test_complexdevice_stop(self):
        class SubSubDevice(Device):
            cpt4 = Component(FakeSignal, '4')

            def stop(self):
                self.stop_called = True

                if self.prefix.endswith('_raises_'):
                    raise Exception('stop failed for some reason')

        class SubDevice(Device):
            cpt1 = Component(FakeSignal, '1')
            cpt2 = Component(FakeSignal, '2')
            cpt3 = Component(FakeSignal, '3')
            subsub = Component(SubSubDevice, '')

            def stop(self):
                self.stop_called = True
                super().stop()

        class MyDevice(Device):
            sub1 = Component(SubDevice, '1')
            sub2 = Component(SubDevice, '_raises_')
            sub3 = Component(SubDevice, '_raises_')
            cpt3 = Component(FakeSignal, '3')

        dev = MyDevice('', name='mydev')
        with self.assertRaises(ExceptionBundle) as cm:
            dev.stop()

        ex = cm.exception
        self.assertEquals(len(ex.exceptions), 2)
        self.assertTrue(dev.sub1.stop_called)
        self.assertTrue(dev.sub2.stop_called)
        self.assertTrue(dev.sub3.stop_called)
        self.assertTrue(dev.sub1.subsub.stop_called)
        self.assertTrue(dev.sub2.subsub.stop_called)
        self.assertTrue(dev.sub3.subsub.stop_called)

    def test_name_shadowing(self):
        RESERVED_ATTRS = ['name', 'parent', 'signal_names', '_signals',
                          'read_attrs', 'configuration_attrs', 'monitor_attrs',
                          '_sig_attrs', '_sub_devices']

        type('a', (Device,), {'a': None})  # legal class definition
        # Illegal class definitions:
        for attr in RESERVED_ATTRS:
            self.assertRaises(TypeError, type, 'a', (Device,), {attr: None})

    def test_formatted_component(self):
        FC = FormattedComponent

        class MyDevice(Device):
            cpt = Component(FakeSignal, 'suffix')
            ch = FC(FakeSignal, '{self.prefix}{self._ch}')

            def __init__(self, prefix, ch='a', **kwargs):
                self._ch = ch
                super().__init__(prefix, **kwargs)

        ch_value = '_test_'

        device = MyDevice('prefix:', ch=ch_value)
        self.assertIs(device.cpt.parent, device)
        self.assertIs(device.ch.parent, device)
        self.assertIs(device._ch, ch_value)
        self.assertEquals(device.ch.read_pv, device.prefix + ch_value)
        self.assertEquals(device.cpt.read_pv,
                          device.prefix + MyDevice.cpt.suffix)


    def test_root(self):
        class MyDevice(Device):
            cpt = Component(FakeSignal, 'suffix')

        d = MyDevice('')
        assert d.cpt.root == d
        assert d.root == d

    def test_contains(self):
        class MyDevice(Device):
            cpt = Component(FakeSignal, 'suffix')
            cpt3 = Component(FakeSignal, 'suffix')

        class AnotherDevice(Device):
            cpt = Component(MyDevice, '')
            cpt2 = Component(MyDevice, '')

        d = MyDevice('')
        assert d.cpt in d
        assert not d in d.cpt
        ad = AnotherDevice('')
        assert ad.cpt in ad
        assert ad.cpt.cpt in ad
        assert not ad in ad.cpt.cpt
        assert not ad in ad.cpt

        assert ad.common_ancestor(ad.cpt) is ad
        assert ad.cpt.common_ancestor(ad.cpt.cpt) is ad.cpt
        assert ad.cpt.cpt3.common_ancestor(ad.cpt2.cpt3) is ad
        assert ad.common_ancestor(ad) is ad
        assert ad.cpt2.common_ancestor(ad.cpt2) is ad.cpt2
