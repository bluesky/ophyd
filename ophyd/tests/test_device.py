import logging
from unittest.mock import Mock

import numpy as np
import pytest

from ophyd import Component, Device, FormattedComponent
from ophyd.device import (
    ComponentWalk,
    create_device_from_components,
    do_not_wait_for_lazy_connection,
    required_for_connection,
    wait_for_lazy_connection,
)
from ophyd.signal import (
    ArrayAttributeSignal,
    AttributeSignal,
    ReadOnlyError,
    Signal,
    SignalRO,
)
from ophyd.utils import ExceptionBundle

logger = logging.getLogger(__name__)


class FakeSignal(Signal):
    def __init__(self, read_pv, *, name=None, parent=None, **kwargs):
        self.read_pv = read_pv
        super().__init__(name=name, parent=parent, **kwargs)
        self._waited_for_connection = False
        self._subscriptions = []

    def wait_for_connection(self):
        self._waited_for_connection = True

    def subscribe(self, method, event_type, **kw):
        self._subscriptions.append((method, event_type, kw))

    def get(self):
        return self.name

    def describe_configuration(self):
        return {self.name + "_conf": {"source": "SIM:test"}}

    def read_configuration(self):
        return {self.name + "_conf": {"value": 0}}


def test_device_state():
    d = Device("test", name="test")

    d.stage()
    old, new = d.configure({})
    assert old == new
    d.unstage()


def test_attrs():
    class MyDevice(Device):
        cpt1 = Component(FakeSignal, "1")
        cpt2 = Component(FakeSignal, "2")
        cpt3 = Component(FakeSignal, "3")

    d = MyDevice(
        "prefix", read_attrs=["cpt1"], configuration_attrs=["cpt2"], name="test"
    )

    d.read()
    assert d.read_attrs == ["cpt1"]
    assert d.configuration_attrs == ["cpt2"]

    assert list(d.read().keys()) == [d.cpt1.name]
    assert set(d.read_configuration().keys()) == {d.cpt2.name + "_conf"}

    assert list(d.describe().keys()) == [d.cpt1.name]
    assert set(d.describe_configuration().keys()) == {
        d.cpt2.name + "_conf",
    }


def test_complexdevice():
    class SubDevice(Device):
        cpt1 = Component(FakeSignal, "1")
        cpt2 = Component(FakeSignal, "2")
        cpt3 = Component(FakeSignal, "3")

    class SubSubDevice(SubDevice):
        cpt4 = Component(FakeSignal, "4")

    class MyDevice(Device):
        sub1 = Component(SubDevice, "1")
        subsub2 = Component(SubSubDevice, "2")
        cpt3 = Component(FakeSignal, "3")

    device = MyDevice("prefix", name="dev")
    device.configuration_attrs = ["sub1", "subsub2.cpt2", "subsub2.cpt4", "cpt3"]
    device.sub1.read_attrs = ["cpt2"]
    device.sub1.configuration_attrs = ["cpt1"]

    assert device.sub1.parent is device
    assert device.subsub2.parent is device
    assert device.cpt3.parent is device

    assert device.sub1.component_names == ("cpt1", "cpt2", "cpt3")
    assert device.subsub2.component_names == ("cpt1", "cpt2", "cpt3", "cpt4")

    with pytest.raises(AttributeError):
        device.component_names.remove("sub1")

    conf_keys = {
        "dev_sub1_cpt1_conf",  # from sub1.*
        # 'dev_sub1_cpt2_conf',   # not in sub1.config_attrs
        "dev_subsub2_cpt2_conf",  # from subsub2.cpt2
        "dev_subsub2_cpt4_conf",  # from subsub2.cpt4
        "dev_cpt3_conf",  # from cpt3
    }

    assert set(device.describe_configuration().keys()) == conf_keys
    assert set(device.read_configuration().keys()) == conf_keys


def test_complexdevice_stop():
    class SubSubDevice(Device):
        cpt4 = Component(FakeSignal, "4")

        def stop(self, *, success=False):
            self.stop_called = True
            self.success = success
            if self.prefix.endswith("_raises_"):
                raise Exception("stop failed for some reason")

    class SubDevice(Device):
        cpt1 = Component(FakeSignal, "1")
        cpt2 = Component(FakeSignal, "2")
        cpt3 = Component(FakeSignal, "3")
        subsub = Component(SubSubDevice, "")

        def stop(self, *, success=False):
            self.stop_called = True
            self.success = success
            super().stop(success=success)

    class MyDevice(Device):
        sub1 = Component(SubDevice, "1")
        sub2 = Component(SubDevice, "_raises_")
        sub3 = Component(SubDevice, "_raises_")
        cpt3 = Component(FakeSignal, "3")

    dev = MyDevice("", name="mydev")
    with pytest.raises(ExceptionBundle) as cm:
        dev.stop()

    ex = cm.value
    assert len(ex.exceptions) == 2
    assert dev.sub1.stop_called
    assert dev.sub2.stop_called
    assert dev.sub3.stop_called
    assert not dev.sub1.success
    assert not dev.sub2.success
    assert not dev.sub3.success

    assert dev.sub1.subsub.stop_called
    assert dev.sub2.subsub.stop_called
    assert dev.sub3.subsub.stop_called
    assert not dev.sub1.subsub.success
    assert not dev.sub2.subsub.success
    assert not dev.sub3.subsub.success

    dev = MyDevice("", name="mydev")
    with pytest.raises(ExceptionBundle) as cm:
        dev.stop(success=True)

    ex = cm.value
    assert len(ex.exceptions) == 2
    assert dev.sub1.stop_called
    assert dev.sub2.stop_called
    assert dev.sub3.stop_called
    assert dev.sub1.success
    assert dev.sub2.success
    assert dev.sub3.success

    assert dev.sub1.subsub.stop_called
    assert dev.sub2.subsub.stop_called
    assert dev.sub3.subsub.stop_called
    assert dev.sub1.subsub.success
    assert dev.sub2.subsub.success
    assert dev.sub3.subsub.success


def test_name_shadowing():
    RESERVED_ATTRS = [
        "name",
        "parent",
        "component_names",
        "_signals",
        "_sig_attrs",
        "_sub_devices",
    ]

    type("a", (Device,), {"a": None})  # legal class definition
    # Illegal class definitions:
    for attr in RESERVED_ATTRS:
        with pytest.raises(TypeError):
            type("a", Device, attr=None)


def test_formatted_component():
    FC = FormattedComponent

    class MyDevice(Device):
        cpt = Component(FakeSignal, "suffix")
        ch = FC(FakeSignal, "{self.prefix}{self._ch}")

        def __init__(self, prefix, ch="a", **kwargs):
            self._ch = ch
            super().__init__(prefix, **kwargs)

    ch_value = "_test_"

    device = MyDevice("prefix:", ch=ch_value, name="test")
    assert device.cpt.parent is device
    assert device.ch.parent is device
    assert device._ch is ch_value
    assert device.ch.read_pv == device.prefix + ch_value
    assert device.cpt.read_pv == device.prefix + MyDevice.cpt.suffix


def test_root():
    class MyDevice(Device):
        cpt = Component(FakeSignal, "suffix")

    d = MyDevice("", name="test")
    assert d.cpt.root == d
    assert d.root == d


def test_hidden_component():
    class MyDevice(Device):
        _hidden_sig = Component(FakeSignal, "suffix")

    d = MyDevice("", name="test")
    assert "_hidden_sig" in d.component_names
    assert not hasattr(d.get(), "_hidden_sig")


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
        sub1 = Component(SubDevice, "1")
        attrsig = Component(AttributeSignal, "prop")
        sub_attrsig = Component(AttributeSignal, "sub1.prop", write_access=False)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._value = init_value

        @property
        def prop(self):
            return self._value

        @prop.setter
        def prop(self, value):
            self._value = value

    dev = MyDevice("", name="mydev")
    assert dev.describe()["mydev_attrsig"]["source"] == "PY:mydev.prop"
    assert dev.describe()["mydev_sub_attrsig"]["source"] == "PY:mydev.sub1.prop"
    assert dev.attrsig.get() == init_value
    cb = Mock()
    dev.attrsig.subscribe(cb)
    dev.attrsig.put(55)
    assert dev.attrsig.get() == 55
    assert cb.called
    assert dev.sub_attrsig.get() == init_value
    assert dev.sub_attrsig.read_access
    assert not dev.sub_attrsig.write_access

    with pytest.raises(ReadOnlyError):
        dev.sub_attrsig.put(0)


def test_attribute_signal_attributeerror():
    class MyDevice(Device):
        sig1 = Component(AttributeSignal, "unknownattribute")
        sig2 = Component(AttributeSignal, "__class__.__name")
        sig3 = Component(AttributeSignal, "unknown.attribute")

    dev = MyDevice("", name="mydev")
    pytest.raises(AttributeError, dev.sig1.get)
    pytest.raises(AttributeError, dev.sig2.get)
    pytest.raises(AttributeError, dev.sig3.get)
    pytest.raises(AttributeError, getattr, dev.sig3, "base")


def test_shadowing_bs_interface_raises_typeerror():
    class LegalDevice(Device):
        cpt = Component(FakeSignal, "cpt")

    with pytest.raises(TypeError):

        class IllegalDevice(Device):
            # 'read' shadows the bluesky interface and should not be allowed
            read = Component(FakeSignal, "read")


def test_array_attribute_signal():
    init_value = range(10)

    class MyDevice(Device):
        attrsig = Component(ArrayAttributeSignal, "prop")

        @property
        def prop(self):
            return init_value

    dev = MyDevice("", name="mydev")
    np.testing.assert_array_equal(dev.attrsig.get(), init_value)
    assert isinstance(dev.attrsig.get(), np.ndarray)
    assert isinstance(dev.attrsig.get(), np.ndarray)


def test_signal_names():
    class MyDevice(Device):
        cpt = Component(FakeSignal, "suffix")

    d = MyDevice("", name="test")
    with pytest.warns(UserWarning):
        signal_names = d.signal_names

    assert signal_names is d.component_names


def test_summary():
    class MyDevice(Device):
        cpt = Component(FakeSignal, "suffix")

    d = MyDevice("", name="test")
    # smoke tests
    d.summary()
    d.__str__()
    d.__repr__()


def test_labels():
    class MyDevice(Device):
        cpt = Component(FakeSignal, "suffix")

    d = MyDevice("", name="test", labels={"a", "b"})
    assert d._ophyd_labels_ == {"a", "b"}


def test_device_put():
    class MyDevice(Device):
        a = Component(Signal)
        b = Component(Signal)

    d = MyDevice("", name="test")
    d.put((1, 2))
    assert d.get() == (1, 2)

    devtuple = d.get_device_tuple()
    d.put(devtuple(a=10, b=12))
    assert d.get() == (10, 12)

    with pytest.raises(ValueError):
        d.put((1, 2, 3))


def test_lazy_wait_for_connect():
    class MyDevice(Device):
        lazy_wait_for_connection = False
        cpt = Component(FakeSignal, "suffix", lazy=True)

    d = MyDevice("", name="test")
    with wait_for_lazy_connection(d):
        d.cpt

    assert d.cpt._waited_for_connection


def test_lazy_do_not_wait_for_connect():
    class MyDevice(Device):
        lazy_wait_for_connection = True
        cpt = Component(FakeSignal, "suffix", lazy=True)

    d = MyDevice("", name="test")
    with do_not_wait_for_lazy_connection(d):
        d.cpt

    assert not d.cpt._waited_for_connection


def test_sub_decorator():
    class MyDevice(Device):
        cpt = Component(FakeSignal, "suffix", lazy=True)

        @cpt.sub_default
        def default(self, **kw):
            pass

        @cpt.sub_value
        def value(self, **kw):
            pass

        @cpt.sub_meta
        def metadata(self, **kw):
            pass

        @cpt.sub_default
        @cpt.sub_value
        @cpt.sub_meta
        def multi(self, **kw):
            pass

    d = MyDevice("", name="test")

    subs = set(event_type for method, event_type, kw in d.cpt._subscriptions)
    assert subs == {None, "value", "meta"}
    assert len(MyDevice.multi._subscriptions) == 3


def test_walk_components():
    class SubSubDevice(Device):
        cpt4 = Component(FakeSignal, "4")

    class SubDevice(Device):
        cpt1 = Component(FakeSignal, "1")
        cpt2 = Component(FakeSignal, "2")
        cpt3 = Component(FakeSignal, "3")
        subsub = Component(SubSubDevice, "")

    class MyDevice(Device):
        sub1 = Component(SubDevice, "sub1")
        sub2 = Component(SubDevice, "sub2")
        sub3 = Component(SubDevice, "sub3")
        cpt3 = Component(FakeSignal, "cpt3")

    assert list(MyDevice.walk_components()) == [
        ComponentWalk(ancestors=(MyDevice,), dotted_name="sub1", item=MyDevice.sub1),
        ComponentWalk(
            ancestors=(
                MyDevice,
                SubDevice,
            ),
            dotted_name="sub1.cpt1",
            item=MyDevice.sub1.cls.cpt1,
        ),
        ComponentWalk(
            ancestors=(
                MyDevice,
                SubDevice,
            ),
            dotted_name="sub1.cpt2",
            item=MyDevice.sub1.cls.cpt2,
        ),
        ComponentWalk(
            ancestors=(
                MyDevice,
                SubDevice,
            ),
            dotted_name="sub1.cpt3",
            item=MyDevice.sub1.cls.cpt3,
        ),
        ComponentWalk(
            ancestors=(
                MyDevice,
                SubDevice,
            ),
            dotted_name="sub1.subsub",
            item=MyDevice.sub1.cls.subsub,
        ),
        ComponentWalk(
            ancestors=(
                MyDevice,
                SubDevice,
                SubSubDevice,
            ),
            dotted_name="sub1.subsub.cpt4",
            item=MyDevice.sub1.cls.subsub.cls.cpt4,
        ),
        ComponentWalk(ancestors=(MyDevice,), dotted_name="sub2", item=MyDevice.sub2),
        ComponentWalk(
            ancestors=(
                MyDevice,
                SubDevice,
            ),
            dotted_name="sub2.cpt1",
            item=MyDevice.sub2.cls.cpt1,
        ),
        ComponentWalk(
            ancestors=(
                MyDevice,
                SubDevice,
            ),
            dotted_name="sub2.cpt2",
            item=MyDevice.sub2.cls.cpt2,
        ),
        ComponentWalk(
            ancestors=(
                MyDevice,
                SubDevice,
            ),
            dotted_name="sub2.cpt3",
            item=MyDevice.sub2.cls.cpt3,
        ),
        ComponentWalk(
            ancestors=(
                MyDevice,
                SubDevice,
            ),
            dotted_name="sub2.subsub",
            item=MyDevice.sub2.cls.subsub,
        ),
        ComponentWalk(
            ancestors=(
                MyDevice,
                SubDevice,
                SubSubDevice,
            ),
            dotted_name="sub2.subsub.cpt4",
            item=MyDevice.sub2.cls.subsub.cls.cpt4,
        ),
        ComponentWalk(ancestors=(MyDevice,), dotted_name="sub3", item=MyDevice.sub3),
        ComponentWalk(
            ancestors=(
                MyDevice,
                SubDevice,
            ),
            dotted_name="sub3.cpt1",
            item=MyDevice.sub3.cls.cpt1,
        ),
        ComponentWalk(
            ancestors=(
                MyDevice,
                SubDevice,
            ),
            dotted_name="sub3.cpt2",
            item=MyDevice.sub3.cls.cpt2,
        ),
        ComponentWalk(
            ancestors=(
                MyDevice,
                SubDevice,
            ),
            dotted_name="sub3.cpt3",
            item=MyDevice.sub3.cls.cpt3,
        ),
        ComponentWalk(
            ancestors=(
                MyDevice,
                SubDevice,
            ),
            dotted_name="sub3.subsub",
            item=MyDevice.sub3.cls.subsub,
        ),
        ComponentWalk(
            ancestors=(
                MyDevice,
                SubDevice,
                SubSubDevice,
            ),
            dotted_name="sub3.subsub.cpt4",
            item=MyDevice.sub3.cls.subsub.cls.cpt4,
        ),
        ComponentWalk(ancestors=(MyDevice,), dotted_name="cpt3", item=MyDevice.cpt3),
    ]


@pytest.mark.parametrize("include_lazy", [False, True])
def test_walk_signals(include_lazy):
    class SubSubDevice(Device):
        cpt4 = Component(FakeSignal, "4", lazy=True)

    class SubDevice(Device):
        cpt1 = Component(FakeSignal, "1")
        cpt2 = Component(FakeSignal, "2")
        cpt3 = Component(FakeSignal, "3")
        subsub = Component(SubSubDevice, "")

    class MyDevice(Device):
        sub1 = Component(SubDevice, "sub1")
        sub2 = Component(SubDevice, "sub2")
        sub3 = Component(SubDevice, "sub3")
        cpt3 = Component(FakeSignal, "cpt3")

    print(MyDevice.sub1.cls.cpt1)

    dev = MyDevice("", name="mydev")
    walked_list = list(dev.walk_signals(include_lazy=include_lazy))

    dev.summary()
    expected = [
        ComponentWalk(
            ancestors=(
                dev,
                dev.sub1,
            ),
            dotted_name="sub1.cpt1",
            item=dev.sub1.cpt1,
        ),
        ComponentWalk(
            ancestors=(
                dev,
                dev.sub1,
            ),
            dotted_name="sub1.cpt2",
            item=dev.sub1.cpt2,
        ),
        ComponentWalk(
            ancestors=(
                dev,
                dev.sub1,
            ),
            dotted_name="sub1.cpt3",
            item=dev.sub1.cpt3,
        ),
        ComponentWalk(
            ancestors=(
                dev,
                dev.sub1,
                dev.sub1.subsub,
            ),
            dotted_name="sub1.subsub.cpt4",
            item=dev.sub1.subsub.cpt4,
        ),
        ComponentWalk(
            ancestors=(
                dev,
                dev.sub2,
            ),
            dotted_name="sub2.cpt1",
            item=dev.sub2.cpt1,
        ),
        ComponentWalk(
            ancestors=(
                dev,
                dev.sub2,
            ),
            dotted_name="sub2.cpt2",
            item=dev.sub2.cpt2,
        ),
        ComponentWalk(
            ancestors=(
                dev,
                dev.sub2,
            ),
            dotted_name="sub2.cpt3",
            item=dev.sub2.cpt3,
        ),
        ComponentWalk(
            ancestors=(
                dev,
                dev.sub2,
                dev.sub2.subsub,
            ),
            dotted_name="sub2.subsub.cpt4",
            item=dev.sub2.subsub.cpt4,
        ),
        ComponentWalk(
            ancestors=(
                dev,
                dev.sub3,
            ),
            dotted_name="sub3.cpt1",
            item=dev.sub3.cpt1,
        ),
        ComponentWalk(
            ancestors=(
                dev,
                dev.sub3,
            ),
            dotted_name="sub3.cpt2",
            item=dev.sub3.cpt2,
        ),
        ComponentWalk(
            ancestors=(
                dev,
                dev.sub3,
            ),
            dotted_name="sub3.cpt3",
            item=dev.sub3.cpt3,
        ),
        ComponentWalk(
            ancestors=(
                dev,
                dev.sub3,
                dev.sub3.subsub,
            ),
            dotted_name="sub3.subsub.cpt4",
            item=dev.sub3.subsub.cpt4,
        ),
        ComponentWalk(ancestors=(dev,), dotted_name="cpt3", item=dev.cpt3),
    ]

    if not include_lazy:
        expected = [item for item in expected if "cpt4" not in item.dotted_name]

    assert walked_list == expected


def test_walk_subdevice_classes():
    class SubSubDevice(Device):
        cpt4 = Component(FakeSignal, "4")

    class SubDevice(Device):
        cpt1 = Component(FakeSignal, "1")
        cpt2 = Component(FakeSignal, "2")
        cpt3 = Component(FakeSignal, "3")
        subsub = Component(SubSubDevice, "")

    class MyDevice(Device):
        sub1 = Component(SubDevice, "sub1")
        sub2 = Component(SubDevice, "sub2")
        sub3 = Component(SubDevice, "sub3")
        cpt3 = Component(FakeSignal, "cpt3")

    assert list(MyDevice.walk_subdevice_classes()) == [
        ("sub1", SubDevice),
        ("sub1.subsub", SubSubDevice),
        ("sub2", SubDevice),
        ("sub2.subsub", SubSubDevice),
        ("sub3", SubDevice),
        ("sub3.subsub", SubSubDevice),
    ]


def test_walk_subdevices():
    class SubSubDevice(Device):
        cpt4 = Component(FakeSignal, "4")

    class SubDevice(Device):
        cpt1 = Component(FakeSignal, "1")
        cpt2 = Component(FakeSignal, "2")
        cpt3 = Component(FakeSignal, "3")
        subsub = Component(SubSubDevice, "")

    class MyDevice(Device):
        sub1 = Component(SubDevice, "sub1")
        sub2 = Component(SubDevice, "sub2")
        sub3 = Component(SubDevice, "sub3")
        cpt3 = Component(FakeSignal, "cpt3")

    dev = MyDevice("", name="mydev")
    assert list(dev.walk_subdevices()) == [
        ("sub1", dev.sub1),
        ("sub1.subsub", dev.sub1.subsub),
        ("sub2", dev.sub2),
        ("sub2.subsub", dev.sub2.subsub),
        ("sub3", dev.sub3),
        ("sub3.subsub", dev.sub3.subsub),
    ]


def test_dotted_name():
    from ophyd import Component as Cpt
    from ophyd import Device
    from ophyd.sim import SynSignal

    class Inner(Device):
        x = Cpt(SynSignal)
        y = Cpt(SynSignal)

    class Outer(Device):
        a = Cpt(Inner)
        b = Cpt(Inner)

    o = Outer(name="test")

    assert o.dotted_name == ""
    assert o.a.dotted_name == "a"
    assert o.b.dotted_name == "b"

    assert o.a.x.dotted_name == "a.x"
    assert o.b.x.dotted_name == "b.x"

    assert o.a.y.dotted_name == "a.y"
    assert o.b.y.dotted_name == "b.y"

    assert o.attr_name == ""
    assert o.a.attr_name == "a"
    assert o.b.attr_name == "b"

    assert o.a.x.attr_name == "x"
    assert o.b.x.attr_name == "x"

    assert o.a.y.attr_name == "y"
    assert o.b.y.attr_name == "y"


def test_create_device():
    components = dict(
        cpt1=Component(Signal, value=0),
        cpt2=Component(Signal, value=1),
        cpt3=Component(Signal, value=2),
    )
    Dev = create_device_from_components("Dev", base_class=Device, **components)
    assert Dev.__name__ == "Dev"
    assert Dev.cpt1 is components["cpt1"]
    dev = Dev(name="dev")
    assert dev.cpt1.get() == 0
    assert dev.cpt2.get() == 1
    assert dev.cpt3.get() == 2


def test_create_device_bad_component():
    with pytest.raises(ValueError):
        create_device_from_components("Dev", base_class=Device, bad_component=None)


def test_required_for_connection_on_method_with_subscriptions():
    class MyDevice(Device):
        cpt = Component(Signal, value=0)

        @required_for_connection
        @cpt.sub_value
        def method(self):
            ...

    dev = MyDevice(name="dev")

    with pytest.raises(TimeoutError):
        dev.wait_for_connection(timeout=0.1)

    dev.cpt.put(0)
    dev.wait_for_connection(timeout=0.1)


def test_required_for_connection_on_method():
    class MyDevice(Device):
        @required_for_connection
        def method(self):
            ...

    dev = MyDevice(name="dev")

    # Timeout without it having been called:
    with pytest.raises(TimeoutError):
        dev.wait_for_connection(timeout=0.01)

    # Call and expect no timeout:
    dev.method()
    dev.wait_for_connection(timeout=0.01)


def test_required_for_connection_in_init():
    class MyDevice(Device):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.call_to_connect = required_for_connection(self.method, device=self)

        def method(self):
            print("method called")

    dev = MyDevice(name="dev")

    # Timeout without it having been called:
    with pytest.raises(TimeoutError):
        dev.wait_for_connection(timeout=0.01)

    # Call and expect no timeout:
    dev.call_to_connect()
    dev.wait_for_connection(timeout=0.01)


def test_noneified_component():
    class SubDevice(Device):
        cpt1 = Component(FakeSignal, "1")

    class MyDevice(Device):
        sub1 = Component(SubDevice, "sub1")
        sub2 = Component(SubDevice, "sub2")

    class MyDeviceWithoutSub2(Device):
        sub1 = Component(SubDevice, "sub1")
        sub2 = None

    assert MyDevice.component_names == ("sub1", "sub2")
    assert MyDevice._sub_devices == ["sub1", "sub2"]

    assert MyDeviceWithoutSub2.component_names == ("sub1",)
    assert MyDeviceWithoutSub2._sub_devices == ["sub1"]


@pytest.mark.parametrize(
    "lazy_state, cntx",
    [(False, wait_for_lazy_connection), (True, do_not_wait_for_lazy_connection)],
)
def test_lazy_wait_context(lazy_state, cntx):
    class LocalExcepton(Exception):
        ...

    d = Device(name="d")
    d.lazy_wait_for_connection = lazy_state

    try:
        with cntx(d):
            assert d.lazy_wait_for_connection == (not lazy_state)
            raise LocalExcepton
    except LocalExcepton:
        ...

    assert d.lazy_wait_for_connection is lazy_state


def test_non_Divice_mixin_with_components():
    class Host(Device):
        a = Component(Signal)

    class MixIn:
        b = Component(Signal)

    class Target(Host, MixIn):
        ...

    t = Target(name="target")

    with pytest.raises(RuntimeError):
        t.b


def test_annotated_device():
    class MyDevice(Device):
        cpt1 = Component[Signal](Signal)
        cpt2 = Component[SignalRO](SignalRO)
        cpt3 = Component[SignalRO](SignalRO)
        cpt4 = Component(SignalRO)

    dev = MyDevice(name="dev")
    assert isinstance(dev.cpt1, Signal)
    assert isinstance(dev.cpt2, SignalRO)
    assert MyDevice.cpt1._get_class_from_annotation() is Signal
    assert MyDevice.cpt2._get_class_from_annotation() is SignalRO
    assert MyDevice.cpt3._get_class_from_annotation() is SignalRO
    assert MyDevice.cpt3.cls is SignalRO
    assert MyDevice.cpt4._get_class_from_annotation() is None
