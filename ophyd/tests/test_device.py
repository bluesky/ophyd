import logging
import pytest

import numpy as np

from ophyd import (Device, Component, FormattedComponent)
from ophyd.signal import (Signal, AttributeSignal, ArrayAttributeSignal)
from ophyd.utils import ExceptionBundle
from .conftest import AssertTools

logger = logging.getLogger(__name__)


class FakeSignal(Signal):
    def __init__(self, read_pv, *, name=None, parent=None, **kwargs):
        self.read_pv = read_pv
        super().__init__(name=name, parent=parent, **kwargs)

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
    d = Device('test', name='test')

    d.stage()
    old, new = d.configure({})
    assert old == new
    d.unstage()


class TestDevice(AssertTools):
    def test_attrs(self):
        class MyDevice(Device):
            cpt1 = Component(FakeSignal, '1')
            cpt2 = Component(FakeSignal, '2')
            cpt3 = Component(FakeSignal, '3')

        d = MyDevice('prefix', read_attrs=['cpt1'],
                     configuration_attrs=['cpt2'],
                     name='test'
                     )

        d.read()
        self.assertEqual(d.read_attrs, ['cpt1'])
        self.assertEqual(d.configuration_attrs, ['cpt2'])

        self.assertEqual(list(d.read().keys()), [d.cpt1.name])
        self.assertEqual(set(d.read_configuration().keys()),
                         {d.cpt2.name + '_conf'})

        self.assertEqual(list(d.describe().keys()), [d.cpt1.name])
        self.assertEqual(set(d.describe_configuration().keys()),
                         {d.cpt2.name + '_conf', })

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

        self.assertEquals(device.sub1.component_names,
                          ['cpt1', 'cpt2', 'cpt3'])
        self.assertEquals(device.subsub2.component_names,
                          ['cpt1', 'cpt2', 'cpt3', 'cpt4'])

        conf_keys = {'dev_sub1_cpt1_conf',    # from sub1.*
                     # 'dev_sub1_cpt2_conf',  # not in sub1.config_attrs
                     'dev_subsub2_cpt2_conf', # from subsub2.cpt2
                     'dev_subsub2_cpt4_conf', # from subsub2.cpt4
                     'dev_cpt3_conf',         # from cpt3


                     }

        self.assertEquals(set(device.describe_configuration().keys()),
                          conf_keys)
        self.assertEquals(set(device.read_configuration().keys()),
                          conf_keys)

    def test_complexdevice_stop(self):
        class SubSubDevice(Device):
            cpt4 = Component(FakeSignal, '4')

            def stop(self, *, success=False):
                self.stop_called = True
                self.success = success
                if self.prefix.endswith('_raises_'):
                    raise Exception('stop failed for some reason')

        class SubDevice(Device):
            cpt1 = Component(FakeSignal, '1')
            cpt2 = Component(FakeSignal, '2')
            cpt3 = Component(FakeSignal, '3')
            subsub = Component(SubSubDevice, '')

            def stop(self, *, success=False):
                self.stop_called = True
                self.success = success
                super().stop(success=success)

        class MyDevice(Device):
            sub1 = Component(SubDevice, '1')
            sub2 = Component(SubDevice, '_raises_')
            sub3 = Component(SubDevice, '_raises_')
            cpt3 = Component(FakeSignal, '3')

        dev = MyDevice('', name='mydev')
        with pytest.raises(ExceptionBundle) as cm:
            dev.stop()

        ex = cm.value
        self.assertEquals(len(ex.exceptions), 2)
        self.assertTrue(dev.sub1.stop_called)
        self.assertTrue(dev.sub2.stop_called)
        self.assertTrue(dev.sub3.stop_called)
        self.assertFalse(dev.sub1.success)
        self.assertFalse(dev.sub2.success)
        self.assertFalse(dev.sub3.success)

        self.assertTrue(dev.sub1.subsub.stop_called)
        self.assertTrue(dev.sub2.subsub.stop_called)
        self.assertTrue(dev.sub3.subsub.stop_called)
        self.assertFalse(dev.sub1.subsub.success)
        self.assertFalse(dev.sub2.subsub.success)
        self.assertFalse(dev.sub3.subsub.success)

        dev = MyDevice('', name='mydev')
        with pytest.raises(ExceptionBundle) as cm:
            dev.stop(success=True)

        ex = cm.value
        self.assertEquals(len(ex.exceptions), 2)
        self.assertTrue(dev.sub1.stop_called)
        self.assertTrue(dev.sub2.stop_called)
        self.assertTrue(dev.sub3.stop_called)
        self.assertTrue(dev.sub1.success)
        self.assertTrue(dev.sub2.success)
        self.assertTrue(dev.sub3.success)

        self.assertTrue(dev.sub1.subsub.stop_called)
        self.assertTrue(dev.sub2.subsub.stop_called)
        self.assertTrue(dev.sub3.subsub.stop_called)
        self.assertTrue(dev.sub1.subsub.success)
        self.assertTrue(dev.sub2.subsub.success)
        self.assertTrue(dev.sub3.subsub.success)

    def test_name_shadowing(self):
        RESERVED_ATTRS = ['name', 'parent', 'component_names', '_signals',
                          '_sig_attrs',
                          '_sub_devices']

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

        device = MyDevice('prefix:', ch=ch_value, name='test')
        self.assertIs(device.cpt.parent, device)
        self.assertIs(device.ch.parent, device)
        self.assertIs(device._ch, ch_value)
        self.assertEquals(device.ch.read_pv, device.prefix + ch_value)
        self.assertEquals(device.cpt.read_pv,
                          device.prefix + MyDevice.cpt.suffix)

    def test_root(self):
        class MyDevice(Device):
            cpt = Component(FakeSignal, 'suffix')

        d = MyDevice('', name='test')
        assert d.cpt.root == d
        assert d.root == d

    def test_hidden_component(self):
        class MyDevice(Device):
            _hidden_sig = Component(FakeSignal, 'suffix')
        d = MyDevice('', name='test')
        assert '_hidden_sig' in d.component_names
        assert not hasattr(d.get(), '_hidden_sig')


def test_attribute_signal():
    init_value = 33

    class SubDevice(Device):
        @property
        def prop(self):
            return init_value

        @prop.setter
        def prop(self, value):
            pass

    class MyDevice(Device):
        sub1 = Component(SubDevice, '1')
        attrsig = Component(AttributeSignal, 'prop')
        sub_attrsig = Component(AttributeSignal, 'sub1.prop')

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._value = init_value

        @property
        def prop(self):
            return self._value

        @prop.setter
        def prop(self, value):
            self._value = value

    dev = MyDevice('', name='mydev')
    assert (dev.describe()['mydev_attrsig']['source'] == 'PY:mydev.prop')
    assert (dev.describe()['mydev_sub_attrsig']['source'] == 'PY:mydev.sub1.prop')
    assert dev.attrsig.get() == init_value
    dev.attrsig.put(55)
    assert dev.attrsig.get() == 55

    assert dev.sub_attrsig.get() == init_value
    dev.sub_attrsig.put(0)


def test_attribute_signal_attributeerror():
    class MyDevice(Device):
        sig1 = Component(AttributeSignal, 'unknownattribute')
        sig2 = Component(AttributeSignal, '__class__.__name')
        sig3 = Component(AttributeSignal, 'unknown.attribute')

    dev = MyDevice('', name='mydev')
    pytest.raises(AttributeError, dev.sig1.get)
    pytest.raises(AttributeError, dev.sig2.get)
    pytest.raises(AttributeError, dev.sig3.get)
    pytest.raises(AttributeError, getattr, dev.sig3, 'base')


def test_shadowing_bs_interface_raises_typeerror():
    class LegalDevice(Device):
        cpt = Component(FakeSignal, 'cpt')

    with pytest.raises(TypeError):
        class IllegalDevice(Device):
            # 'read' shadows the bluesky interface and should not be allowed
            read = Component(FakeSignal, 'read')


def test_array_attribute_signal():
    init_value = range(10)

    class MyDevice(Device):
        attrsig = Component(ArrayAttributeSignal, 'prop')

        @property
        def prop(self):
            return init_value

    dev = MyDevice('', name='mydev')
    np.testing.assert_array_equal(dev.attrsig.get(), init_value)
    assert isinstance(dev.attrsig.get(), np.ndarray)
    assert isinstance(dev.attrsig.get(), np.ndarray)


def test_signal_names():

    class MyDevice(Device):
        cpt = Component(FakeSignal, 'suffix')

    d = MyDevice('', name='test')
    with pytest.warns(UserWarning):
        signal_names = d.signal_names

    assert signal_names is d.component_names


def test_summary():
    class MyDevice(Device):
        cpt = Component(FakeSignal, 'suffix')

    d = MyDevice('', name='test')
    # smoke tests
    d.summary()
    d.__str__()
    d.__repr__()

def test_labels():
    class MyDevice(Device):
        cpt = Component(FakeSignal, 'suffix')

    d = MyDevice('', name='test', labels={'a', 'b'})
    assert d._ophyd_labels_ == {'a', 'b'}
