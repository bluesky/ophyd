from unittest.mock import Mock
from ophyd import Device
from ophyd.status import StatusBase, SubscriptionStatus, UseNewProperty
import pytest


def _setup_state_and_cb():
    state = {}

    def cb():
        state['done'] = True
    return state, cb


def test_status_post():
    st = StatusBase()
    state, cb = _setup_state_and_cb()

    assert 'done' not in state
    st.add_callback(cb)
    assert 'done' not in state
    st._finished()
    assert 'done' in state
    assert state['done']


def test_status_legacy_finished_cb():
    st = StatusBase()
    state1, cb1 = _setup_state_and_cb()
    state2, cb2 = _setup_state_and_cb()

    # The old setter works for adding one callback.
    with pytest.warns(UserWarning):
        st.finished_cb = cb1
    # The new getter works.
    st.callbacks == set([cb1])
    # And the old getter works so long as there is just one callback set.
    with pytest.warns(UserWarning):
        assert st.finished_cb is cb1
    # As before, the old setter cannot be updated once set.
    with pytest.raises(UseNewProperty):
        st.finished_cb = cb2
    # But, using the new method, we can add another callback.
    st.add_callback(cb2)
    # Once we have two callbacks, the getter does not work.
    with pytest.raises(UseNewProperty):
        st.finished_cb
    # But the new getter does.
    st.callbacks == set([cb1, cb2])

    assert 'done' not in state1
    assert 'done' not in state2
    st._finished()
    assert 'done' in state1
    assert 'done' in state2


def test_status_pre():
    st = StatusBase()
    state, cb = _setup_state_and_cb()

    st._finished()

    assert 'done' not in state
    st.add_callback(cb)
    assert 'done' in state
    assert state['done']


def test_subscription_status():
    # Arbitrary device
    d = Device("Tst:Prefix", name='test')
    # Mock callback
    m = Mock()

    # Full fake callback signature
    def cb(*args, done=False, **kwargs):
        # Run mock callback
        m()
        # Return finished or not
        return done

    status = SubscriptionStatus(d, cb, event_type=d.SUB_ACQ_DONE)

    # Run callbacks but do not mark as complete
    d._run_subs(sub_type=d.SUB_ACQ_DONE, done=False)
    assert m.called
    assert not status.done and not status.success

    # Run callbacks and mark as complete
    d._run_subs(sub_type=d.SUB_ACQ_DONE, done=True)
    assert status.done and status.success


def test_and():
    st1 = StatusBase()
    st2 = StatusBase()
    st3 = st1 & st2
    # make sure deep recursion works
    st4 = st1 & st3
    st5 = st3 & st4
    state1, cb1 = _setup_state_and_cb()
    state2, cb2 = _setup_state_and_cb()
    state3, cb3 = _setup_state_and_cb()
    state4, cb4 = _setup_state_and_cb()
    state5, cb5 = _setup_state_and_cb()
    st1.add_callback(cb1)
    st2.add_callback(cb2)
    st3.add_callback(cb3)
    st4.add_callback(cb4)
    st5.add_callback(cb5)
    st1._finished()
    assert 'done' in state1
    assert 'done' not in state2
    assert 'done' not in state3
    assert 'done' not in state4
    assert 'done' not in state5
    st2._finished()
    assert 'done' in state3
    assert 'done' in state4
    assert 'done' in state5
    assert st3.left is st1
    assert st3.right is st2
    assert st4.left is st1
    assert st4.right is st3
    assert st5.left is st3
    assert st5.right is st4
