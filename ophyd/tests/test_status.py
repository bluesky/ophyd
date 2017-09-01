from unittest.mock import Mock
from ophyd import Device
from ophyd.status  import StatusBase, SubscriptionStatus


def _setup_st():
    st = StatusBase()
    state = {}

    def cb():
        state['done'] = True
    repr(st)
    return st, state, cb



def test_status_post():
    st, state, cb = _setup_st()

    assert 'done' not in state
    st.finished_cb = cb
    assert 'done' not in state
    st._finished()
    assert 'done' in state
    assert state['done']


def test_status_pre():
    st, state, cb = _setup_st()

    st._finished()

    assert 'done' not in state
    st.finished_cb = cb
    assert 'done' in state
    assert state['done']


def test_subscription_status():
    #Arbitrary device
    d = Device("Tst:Prefix")
    #Mock callback
    m = Mock()

    #Full fake callback signature
    def cb(*args, done=False, **kwargs):
        #Run mock callback
        m()
        #Return finished or not
        return done

    status = SubscriptionStatus(d, cb, event_type=d.SUB_ACQ_DONE)

    #Run callbacks but do not mark as complete
    d._run_subs(sub_type=d.SUB_ACQ_DONE, done=False)
    assert m.called
    assert not status.done and not status.success

    #Run callbacks and mark as complete
    d._run_subs(sub_type=d.SUB_ACQ_DONE, done=True)
    assert status.done and status.success

