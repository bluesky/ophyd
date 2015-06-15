from __future__ import print_function

from ..controls.ophydobj import OphydObject


class State(OphydObject):
    '''Base class for use in FSM pattern.

       Subclasses MUST override the state_action method.
    '''
    SUB_ENTRY = 'entry'
    SUB_EXIT = 'exit'
    SUB_STATE = 'state'

    def __init__(self, name=None, transitions=None):
        self._entered = False
        if name is None:
            name = self.__class__.__name__
        else:
            self.name = name

        self._default_sub = None
        OphydObject.__init__(self, name=name, register=False)

    def subscribe(self, cb, event_type=None):
        OphydObject.subscribe(self, cb, event_type=event_type, run=False)

    def state_action(self, *args, **kwargs):
        self._run_subs(sub_type=self.SUB_STATE, *args, **kwargs) 

    def on_entry(self, *args, **kwargs):
        if not self._entered:
            self._entered = True
            self._run_subs(sub_type=self.SUB_ENTRY, *args, **kwargs)

    def on_exit(self, *args, **kwargs):
        self._run_subs(sub_type=self.SUB_EXIT, *args, **kwargs)
        self._entered = False


class FSM(object):
    def __init__(self, states=None, initial=None, verbose=True):
        self._verbose = verbose
        self._states = states
        self._state = initial
        self.state(initial)

    @property
    def state(self):
        return self._state.name

    def state(self, state, *args, **kwargs):
        if self._verbose:
            print('Current state = ', self._state, ', new state = ', state)
        # Is this a transition to the same state?
        if state == self._state:
            self._state.on_entry(*args, **kwargs)
            self._state.state_action(*args, **kwargs)
        else:
            self._state.on_exit(*args, **kwargs)
            state.on_entry(*args, **kwargs)
            self._state = state
            self._state.state_action(*args, **kwargs)
