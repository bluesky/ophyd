from ophyd.status import StatusBase


def _setup_st():
    state = {}

    def cb():
        state['done'] = True

    return state, cb


def test_status_post():
    st = StatusBase()
    state, cb = _setup_st()

    assert 'done' not in state
    st.add_callback(cb)
    assert 'done' not in state
    st._finished()
    assert 'done' in state
    assert state['done']


def test_status_pre():
    st = StatusBase()
    state, cb = _setup_st()

    st._finished()

    assert 'done' not in state
    st.add_callback(cb)
    assert 'done' in state
    assert state['done']

def test_and():
    st1 = StatusBase()
    st2 = StatusBase()
    st3 = st1 & st2
    # make sure deep recursion works
    st4 = st1 & st3
    st5 = st3 & st4
    state1, cb1 = _setup_st()
    state2, cb2 = _setup_st()
    state3, cb3 = _setup_st()
    state4, cb4 = _setup_st()
    state5, cb5 = _setup_st()
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
