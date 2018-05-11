import pytest
from ophyd import (Device, Component, Signal, MotorBundle, Kind,
                   HintedComponent as HCpt)
from ophyd.sim import SynAxis


def test_device_hints():
    # Default hints is 'fields' with an empty list.
    assert {'fields': []} == Device('', name='dev').hints

    # Class-provided default works.
    class Dongle(Device):
        a = Component(Signal, kind=Kind.HINTED)
        b = Component(Signal)

    # Convenience Component is equivalent.
    class Dongle(Device):
        a = HCpt(Signal)
        b = Component(Signal)

    assert {'fields': ['dev_a']} == Dongle(name='dev').hints
    assert {'fields': ['dev_a']} == Dongle(name='dev').hints

def test_motor_bundle_hints():
    class Bundle(MotorBundle):
        a = HCpt(SynAxis)
        b = HCpt(SynAxis)

    assert {'fields': ['dev_a', 'dev_b']} == Bundle(name='dev').hints


def test_pseudopos_hints(hw):
    assert len(hw.pseudo3x3.hints['fields']) == 3
    assert len(hw.pseudo1x3.hints['fields']) == 1
