from ophyd import Device, Signal, Kind, Component


# A object's kind only matters when we read its _parent_.
# When the signal does into a Device, that device will only read it on read()
# not on read_configuration(), but we can still call both methods on `sig`
# _directly_ if we want to.
normal_sig = Signal(name='normal_sig', value=3)
assert normal_sig.kind == Kind.NORMAL
assert 'normal_sig' in normal_sig.read()
assert 'normal_sig' in normal_sig.read_configuration()

# Same with a sig set up this way
config_sig = Signal(name='config_sig', value=5, kind=Kind.CONFIGURATION)
assert config_sig.kind == Kind.CONFIGURATION
assert 'config_sig' in config_sig.read()
assert 'config_sig' in config_sig.read_configuration()


class A(Device):
    normal_sig = Component(Signal)
    config_sig = Component(Signal, kind=Kind.CONFIGURATION)
    omitted_sig = Component(Signal, kind=Kind.OMIT)

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
    a_config = Component(A, kind=Kind.CONFIGURATION)
    a_omitted = Component(A, kind=Kind.OMIT)


b = B(name='b')


assert ['b_a_default_normal_sig'] == list(b.read())
# Notice that a_default comes along for the ride here. If you ask a Device for
# its normal readings it will also give you its configuration. (You need
# complete configurational metadata for the EventDescriptor!)
assert ['b_a_default_config_sig',
        'b_a_config_config_sig'] == list(b.read_configuration())
# Notice that it tacks CONFIGURATION on when you try to set the kind to NORMAL.
assert (Kind.NORMAL | Kind.CONFIGURATION) == B(name='b', kind=Kind.NORMAL).kind
# And the same if you try to set it after __init__
b.a_default.kind = Kind.NORMAL
assert b.a_default.kind == (Kind.NORMAL | Kind.CONFIGURATION)
# However, just taking CONFIGURATION alone without Event-wise readings is fine.
b.a_default.kind = Kind.CONFIGURATION
assert b.a_default.kind == Kind.CONFIGURATION
assert [] == list(b.read())  # Now we get no Event-wise readings from a_default
assert ['b_a_default_config_sig',
        'b_a_config_config_sig'] == list(b.read_configuration())
