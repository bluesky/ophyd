from __future__ import print_function

from ..controls.ophydobj import OphydObject


class State(OphydObject):
    '''Base class for use in FSM pattern.

       Subclasses MUST override the state_action method.
    '''
    SUB_ENTRY = 'entry'
    SUB_EXIT = 'exit'

    def __init__(self, name=None, transitions=None):
        self._entered = False
        if name is None:
            name = self.__class__.__name__
        else:
            self.name = name

        self._default_sub = None
        OphydObject.__init__(self, name=name, register=False)

    def state_action(self, *args, **kwargs):
        raise NotImplementedError("Subclasses must implement the state_action method.")

    def on_entry(self, *args, **kwargs):
        if not self._entered:
            self._entered = True
            self._run_subs(sub_type=self.SUB_ENTRY, *args, **kwargs)

    def on_exit(self, *args, **kwargs):
        self._run_subs(sub_type=self.SUB_EXIT, *args, **kwargs)
        self._entered = False


class FSM(object):
    def __init__(self, states=None, initial=None):
        self._states = states
        self._state = initial

    @property
    def state(self):
        return self._state.name

    @state.setter
    def state(self, state, *args, **kwargs):
        print('Current state = ', self._state, ', new state = ', state)
        # Is this a transition to the same state?
        if state == self._state:
            self._state.on_entry()
            self._state.state_action()
        else:
            self._state.on_exit()
            state.on_entry()
            self._state = state
            self._state.state_action()
