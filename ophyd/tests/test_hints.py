import pytest
from ophyd import Device, Component, Signal, MotorBundle
from ophyd.sim import SynAxis


def test_device_hints():
    # Default hints is empty dict.
    # assert {} == Device('', name='dev').hints

    # User-specified empty dict is acceptable.
    assert {} == Device('', name='dev', hints={}).hints

    # User-specified empty list of fields is acceptable.
    h = {'fields': []}
    assert h == Device('', name='dev', hints=h).hints

    # Item in fields not matching a name raises at initialization time.
    h = {'fields': ['not_a_valid_attr']}
    with pytest.raises(ValueError):
        Device('', name='dev', hints=h)

    # User-provided name works.
    class Dongle(Device):
        a = Component(Signal)
        b = Component(Signal)

    h = {'fields': ['dev_a']}
    assert h == Dongle(name='dev', hints=h).hints

    # Class-provided default works.
    class Dongle(Device):
        _default_hints = {'fields': ['a']}
        a = Component(Signal)
        b = Component(Signal)

    h = {'fields': ['dev_a']}
    assert h == Dongle(name='dev').hints

    # User can override class default.
    h = {'fields': ['dev_b']}
    assert h == Dongle(name='dev', hints=h).hints

    # Class provided default not matching a name raises as initialization time.
    # TODO The metaclass could catch this at definition time....
    class Dongle(Device):
        _default_hints = {'fields': ['c']}
        a = Component(Signal)
        b = Component(Signal)
    with pytest.raises(ValueError):
        Device('', name='dev', hints=h)


def test_motor_bundle_hints():
    class Bundle(MotorBundle):
        a = Component(SynAxis)
        b = Component(SynAxis)

    assert {'fields': ['dev_a', 'dev_b']} == Bundle(name='dev').hints


def test_pseudopos_hints(hw):
    assert len(hw.pseudo3x3.hints['fields']) == 3
    assert len(hw.pseudo1x3.hints['fields']) == 1
