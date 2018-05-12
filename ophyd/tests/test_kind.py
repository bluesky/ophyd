from ophyd import Device, Signal, Kind, Component, RESPECT_KIND, kind_context


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


def test_standalone_signals():
    # A object's kind only matters when we read its _parent_. It affects
    # whether its parent recursively calls read() and/or read_configuration().
    # When we call read() and/or read_configuration() on the object itself,
    # directly, and its 'kind' setting does not affects its behavior.
    normal_sig = Signal(name='normal_sig', value=3)
    assert normal_sig.kind == Kind.NORMAL
    assert 'normal_sig' in normal_sig.read()
    assert 'normal_sig' in normal_sig.read_configuration()

    # Same with a sig set up this way
    config_sig = Signal(name='config_sig', value=5, kind=Kind.CONFIG)
    assert config_sig.kind == Kind.CONFIG
    assert 'config_sig' in config_sig.read()
    assert 'config_sig' in config_sig.read_configuration()

    # Same with a sig set up this way
    omitted_sig = Signal(name='omitted_sig', value=5, kind=Kind.OMITTED)
    assert omitted_sig.kind == Kind.OMITTED
    assert 'omitted_sig' in omitted_sig.read()
    assert 'omitted_sig' in omitted_sig.read_configuration()

    # But these will be differentiated when we put them into a parent
    # Device and call read() or read_configuraiton() on _that_.


def test_nested_devices():

    class A(Device):
        _default_read_attrs = RESPECT_KIND
        _default_configuration_attrs = RESPECT_KIND
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
        _default_read_attrs = RESPECT_KIND
        _default_configuration_attrs = RESPECT_KIND
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


def test_convenience_wrappers_of_component():
    # Convenience wrappers of Component are helpful for big Devices. The
    # default kind of Component must be NORMAL for back-compatibility, but for
    # big Devices OmmittedComponent is likely more useful.
    from ophyd import OmittedComponent as OCpt

    class Thing(Device):
        _default_read_attrs = RESPECT_KIND
        _default_configuration_attrs = RESPECT_KIND
        a = OCpt(Signal)
        b = OCpt(Signal)

    thing = Thing(name='thing')
    assert {} == thing.read()
    assert {} == thing.read_configuration()

    thing.a.kind = Kind.NORMAL
    assert ['thing_a'] == list(thing.read())


def test_strings():
    sig = Signal(name='sig', kind='normal')
    assert sig.kind == Kind.NORMAL


def test_kind_context():
    class Thing(Device):
        _default_read_attrs = RESPECT_KIND
        _default_configuration_attrs = RESPECT_KIND

        with kind_context('omitted') as Cpt:
            a = Cpt(Signal)

    thing = Thing(name='thing')
    assert thing.a.kind == Kind.OMITTED