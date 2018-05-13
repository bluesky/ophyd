from ophyd import (Device, Component, Signal, MotorBundle, Kind)
from ophyd.sim import SynAxis


def test_device_hints():
    # Default hints is 'fields' with an empty list.
    assert {'fields': []} == Device('', name='dev').hints

    # Class-provided default works.
    class Dongle(Device):
        a = Component(Signal, kind=Kind.hinted)
        b = Component(Signal)

    assert {'fields': ['dev_a']} == Dongle(name='dev').hints
    assert {'fields': ['dev_a']} == Dongle(name='dev').hints


def test_motor_bundle_hints():
    class Bundle(MotorBundle):
        a = Component(SynAxis, kind=Kind.hinted)
        b = Component(SynAxis, kind=Kind.hinted)

    assert {'fields': ['dev_a', 'dev_b']} == Bundle(name='dev').hints


def test_pseudopos_hints(hw):
    assert len(hw.pseudo3x3.hints['fields']) == 3
    assert len(hw.pseudo1x3.hints['fields']) == 1
