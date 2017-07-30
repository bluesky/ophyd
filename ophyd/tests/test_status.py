from ophyd.status import StatusBase


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
