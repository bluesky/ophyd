from ophyd import Device, Signal, Kind, Component, ALL_COMPONENTS, kind_context
import pytest


def test_standalone_signals():
    # A object's kind only matters when we read its _parent_. It affects
    # whether its parent recursively calls read() and/or read_configuration().
    # When we call read() and/or read_configuration() on the object itself,
    # directly, and its 'kind' setting does not affects its behavior.
    normal_sig = Signal(name='normal_sig', value=3, kind=Kind.NORMAL)
    assert normal_sig.kind == Kind.NORMAL
    assert normal_sig.name not in normal_sig.hints['fields']
    assert 'normal_sig' in normal_sig.read()
    assert 'normal_sig' in normal_sig.read_configuration()

    hinted_sig = Signal(name='hinted_sig', value=3)
    assert hinted_sig.kind == Kind.HINTED
    assert hinted_sig.name in hinted_sig.hints['fields']
    assert 'hinted_sig' in hinted_sig.read()
    assert 'hinted_sig' in hinted_sig.read_configuration()

    # Same with a sig set up this way
    config_sig = Signal(name='config_sig', value=5, kind=Kind.CONFIG)
    assert config_sig.kind == Kind.CONFIG
    assert config_sig.name not in config_sig.hints['fields']
    assert 'config_sig' in config_sig.read()
    assert 'config_sig' in config_sig.read_configuration()

    # Same with a sig set up this way
    omitted_sig = Signal(name='omitted_sig', value=5, kind=Kind.OMITTED)
    assert omitted_sig.kind == Kind.OMITTED
    assert omitted_sig.name not in omitted_sig.hints['fields']
    assert 'omitted_sig' in omitted_sig.read()
    assert 'omitted_sig' in omitted_sig.read_configuration()

    # But these will be differentiated when we put them into a parent
    # Device and call read() or read_configuraiton() on _that_.


def test_nested_devices():

    class A(Device):
        normal_sig = Component(Signal)
        config_sig = Component(Signal, kind=Kind.CONFIG)
        omitted_sig = Component(Signal, kind=Kind.OMITTED)

    a = A(name='a')

    # When we call read and read_configuration on a, it checks the kind of its
    # components and reads the right ones.
    assert 'a_normal_sig' in a.read()
    assert 'a_config_sig' not in a.read()
    assert 'a_omitted_sig' not in a.read()

    assert 'a_normal_sig' not in a.read_configuration()
    assert 'a_config_sig' in a.read_configuration()
    assert 'a_omitted_sig' not in a.read_configuration()

    # Another layer of nesting!

    class B(Device):
        a_default = Component(A)
        a_config = Component(A, kind=Kind.CONFIG)
        a_omitted = Component(A, kind=Kind.OMITTED)

    b = B(name='b')

    assert ['b_a_default_normal_sig'] == list(b.read())

    # Notice that a_default comes along for the ride here. If you ask
    # a Device for its normal readings it will also give you its
    # configuration. (You need complete configurational metadata for
    # the EventDescriptor!)
    assert ['b_a_default_config_sig',
            'b_a_config_config_sig'] == list(b.read_configuration())
    # Notice that it tacks CONFIG on when you try to set the kind to NORMAL.
    assert (Kind.NORMAL | Kind.CONFIG) == B(name='b', kind=Kind.NORMAL).kind
    # And the same if you try to set it after __init__
    b.a_default.kind = Kind.NORMAL
    assert b.a_default.kind == (Kind.NORMAL | Kind.CONFIG)
    # However, just taking CONFIG alone without Event-wise readings is fine.
    b.a_default.kind = Kind.CONFIG
    assert b.a_default.kind == Kind.CONFIG
    # Now we get no Event-wise readings from a_default
    assert [] == list(b.read())
    assert ['b_a_default_config_sig',
            'b_a_config_config_sig'] == list(b.read_configuration())


def test_strings():
    sig = Signal(name='sig', kind='normal')
    assert sig.kind == Kind.NORMAL


def test_kind_context():
    class Thing(Device):

        with kind_context('omitted') as Cpt:
            a = Cpt(Signal)

    thing = Thing(name='thing')
    assert thing.a.kind == Kind.OMITTED


# Test back-compatibility. The expected values in these tests match the
# behaviors from before the Kind feature was introduced --- modulo the _order_.


def test_behavior_if_nothing_is_specified():

    class Thing(Device):
        a = Component(Signal)
        b = Component(Signal)

    t = Thing(name='t')
    assert set('ab') == set(t.read_attrs)
    assert set() == set(t.configuration_attrs)


def test_class_default_attrs_both_none():

    # Test various values of _default_read_attrs and
    # _default_configuration_attrs

    class Thing(Device):
        _default_read_attrs = None
        _default_configuration_attrs = None
        a = Component(Signal)
        b = Component(Signal)

    t = Thing(name='t')
    assert set('ab') == set(t.read_attrs)
    assert set() == set(t.configuration_attrs)
    assert ['t_a', 't_b'] == list(t.describe())
    assert set() == set(t.describe_configuration())

    class ThingHaver(Device):
        _default_read_attrs = None
        _default_configuration_attrs = None
        a = Component(Thing)
        b = Component(Thing)

    th = ThingHaver(name='th')
    assert set(['a', 'b'] +['a.a', 'a.b', 'b.a', 'b.b']) == set(th.read_attrs)

    # THIS IS ACTUALLY _NOT_ BACKWARD-COMPATIBLE BEHAVIOR!
    # But we consider the former behavior a bug. Unlike a Signal, a Device is
    # not allowed to place itself in its parent's read_attrs ONLY. It must also
    # be in configuration_attrs if it is in read_attrs. (Under the hood, this
    # is enforced in the setter of the Device's `kind` property, which OR's the
    # kind value with Kind.CONFIG if said vlaue includes Kind.NORMAL.
    assert set('ab') == set(th.configuration_attrs)

    assert ['th_a_a', 'th_a_b', 'th_b_a', 'th_b_b'] == list(th.describe())
    assert [] == list(t.describe_configuration())


def test_default_read_attrs_empty_and_configuration_attrs_none():

    class Thing(Device):
        _default_read_attrs = []
        _default_configuration_attrs = None
        a = Component(Signal)
        b = Component(Signal)

    t = Thing(name='t')
    assert set() == set(t.read_attrs)
    assert set() == set(t.configuration_attrs)

    class ThingHaver(Device):
        _default_read_attrs = []
        _default_configuration_attrs = None
        a = Component(Thing)
        b = Component(Thing)

    th = ThingHaver(name='th')
    assert set() == set(th.read_attrs)
    assert [] == list(th.describe())
    assert set('ab') == set(th.configuration_attrs)
    assert [] == list(th.describe_configuration())


def test_default_read_attrs_none_and_configuration_attrs_empty():

    class Thing(Device):
        _default_read_attrs = None
        _default_configuration_attrs = []
        a = Component(Signal)
        b = Component(Signal)

    t = Thing(name='t')
    assert set('ab') == set(t.read_attrs)
    assert set() == set(t.configuration_attrs)

    class ThingHaver(Device):
        _default_read_attrs = None
        _default_configuration_attrs = []
        a = Component(Thing)
        b = Component(Thing)

    th = ThingHaver(name='th')
    assert set(['a', 'b'] + ['a.a', 'a.b', 'b.a', 'b.b']) == set(th.read_attrs)
    assert ['th_a_a', 'th_a_b', 'th_b_a', 'th_b_b'] == list(th.describe())
    assert set('ab') == set(th.configuration_attrs)
    assert [] == list(th.describe_configuration())


def test_default_attrs_both_empty():

    class Thing(Device):
        _default_read_attrs = []
        _default_configuration_attrs = []
        a = Component(Signal)
        b = Component(Signal)

    t = Thing(name='t')
    assert set() == set(t.read_attrs)
    assert set() == set(t.configuration_attrs)

    class ThingHaver(Device):
        _default_read_attrs = []
        _default_configuration_attrs = []
        a = Component(Thing)
        b = Component(Thing)

    th = ThingHaver(name='th')
    assert set() == set(th.read_attrs)
    assert [] == list(th.describe())
    assert set() == set(th.configuration_attrs)
    assert [] == list(t.describe_configuration())


def test_all_components_escape_hatch():

    class Thing(Device):
        _default_read_attrs = ['a']
        _default_configuration_attrs = ['b']
        a = Component(Signal)
        b = Component(Signal)

    class ThingEscapeHatch(Thing):
        _default_read_attrs = ALL_COMPONENTS
        _default_configuration_attrs = []
        c = Component(Signal)


    t = ThingEscapeHatch(name='t')
    assert set('abc') == set(t.read_attrs)
    assert set() == set(t.configuration_attrs)


def test_default_attrs_nonempty_disjoint():

    class Thing(Device):
        _default_read_attrs = ['a']
        _default_configuration_attrs = ['b']
        a = Component(Signal)
        b = Component(Signal)

    t = Thing(name='t')
    assert set('a') == set(t.read_attrs)
    assert set('b') == set(t.configuration_attrs)

    class ThingHaver(Device):
        _default_read_attrs = ['a']
        _default_configuration_attrs = ['b']
        a = Component(Thing)
        b = Component(Thing)

    th = ThingHaver(name='th')
    assert set(['a', 'a.a']) == set(th.read_attrs)
    assert 'b' not in th.read_attrs
    assert ['th_a_a'] == list(th.describe())
    # Here again we have the same break from back-compatability. We are not
    # allowed to put a sub-Device in configuration_attrs that is not also in
    # read_attrs. The old code would have:
    # assert set(['b']) == set(th.configuration_attrs)
    # But now we get:
    assert set(['a', 'b'] + ['a.b', 'b.b']) == set(th.configuration_attrs)
    assert ['th_a_b', 'th_b_b'] == list(th.describe_configuration())


def test_options_via_init():
    ...


def test_back_compat():
    # Test class defaults.
    class Thing(Device):
        _default_read_attrs = ['a']
        _default_configuration_attrs = ['b']
        a = Component(Signal)
        b = Component(Signal)
        c = Component(Signal)

    thing = Thing(name='thing')
    assert ['thing_a'] == list(thing.read())
    # assert ['thing_b'] == list(thing.read_configuration())

    # Test attribute getting and setting.
    assert thing.read_attrs == ['a']
    assert thing.configuration_attrs == ['b']
    thing.read_attrs = ['a', 'b']
    assert ['thing_a', 'thing_b'] == list(thing.read())

    thing = Thing(name='thing', read_attrs=['b'], configuration_attrs=['a'])
    assert ['thing_b'] == list(thing.read())


@pytest.fixture(scope='function')
def thing_haver_haver():
    class Thing(Device):
        a = Component(Signal, kind=Kind.OMITTED)
        b = Component(Signal, kind=Kind.CONFIG)
        c = Component(Signal, kind=Kind.NORMAL)
        d = Component(Signal, kind=Kind.HINTED)

    class ThingHaver(Device):
        A = Component(Thing, kind=Kind.OMITTED)
        B = Component(Thing, kind=Kind.CONFIG)
        C = Component(Thing, kind=Kind.NORMAL)

    class ThingHaverHaver(Device):
        alpha = Component(ThingHaver, kind=Kind.OMITTED)
        beta = Component(ThingHaver, kind=Kind.CONFIG)
        gamma = Component(ThingHaver, kind=Kind.NORMAL)

    return ThingHaverHaver(name='thh')


def test_list_proxy(thing_haver_haver):

    thh = thing_haver_haver
    assert 'gamma' in thh.read_attrs
    assert 'gamma' in list(thh.read_attrs)

    assert 'beta' in thh.configuration_attrs
    assert 'beta' in list(thh.configuration_attrs)

    assert 'alpha' not in thh.read_attrs
    assert 'alpha' not in thh.configuration_attrs

    assert 'alpha' not in list(thh.read_attrs)
    assert 'alpha' not in list(thh.configuration_attrs)

    assert 'gamma.C' in thh.read_attrs
    assert 'gamma.C' in list(thh.read_attrs)

    assert 'gamma.C.c' in list(thh.read_attrs)
    assert 'gamma.C.d' in list(thh.read_attrs)
