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
    # A signal should record its own hints
    assert len(Dongle(name='dev').b.hints.get('fields')) > 1

def test_motor_bundle_hints():
    class Bundle(MotorBundle):
        a = Component(SynAxis, kind=Kind.hinted)
        b = Component(SynAxis, kind=Kind.hinted)
        c = Component(SynAxis, kind=Kind.normal)

    assert {'fields': ['dev_a', 'dev_b']} == Bundle(name='dev').hints
    assert {'fields': ['dev_c']} == Bundle(name='dev').c.hints


def test_pseudopos_hints(hw):
    assert len(hw.pseudo3x3.hints['fields']) == 3
    assert len(hw.pseudo1x3.hints['fields']) == 1


def test_hints_are_lazy():

    class Stuff(Device):
        sig = Component(Signal, lazy=True)

    class Thing(Device):
        hinted = Component(Stuff, kind=Kind.hinted, lazy=True)
        normal = Component(Stuff, lazy=True)
        config = Component(Stuff, kind=Kind.config, lazy=True)
        omitted = Component(Stuff, kind=Kind.omitted, lazy=True)

    class ThingHaver(Device):
        t = Component(Thing, lazy=True)

    th = ThingHaver(name='t')

    # Lazy Component not instantiated.
    assert not th._signals
    # This instantiates only the things it needs to.
    th.hints
    assert 't' in th._signals
    assert 'hinted' in th.t._signals
    assert 'normal' in th.t._signals
    assert 'config' not in th.t._signals
    assert 'omitted' not in th.t._signals
