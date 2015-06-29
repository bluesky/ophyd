import logging
import copy

from ..controls.ophydobj import OphydObject


logging.basicConfig(level=logging.DEBUG)


class State(OphydObject):
    '''Base class for use in FSM pattern.

       Subclasses MUST override the state_action method.
    '''
    SUB_ENTRY = 'entry'
    SUB_EXIT = 'exit'
    SUB_STATE = 'state'

    def __init__(self, name=None):
        self._entered = False
        if name is None:
            name = self.__class__.__name__

        self._default_sub = None
        OphydObject.__init__(self, name=name, register=False)

    def subscribe(self, cb, event_type=None):
        OphydObject.subscribe(self, cb, event_type=event_type, run=False)

    def __call__(self, *args, **kwargs):
        self._run_subs(sub_type=self.SUB_STATE, *args, **kwargs) 

    def on_entry(self, *args, **kwargs):
        if not self._entered:
            self._entered = True
            self._run_subs(sub_type=self.SUB_ENTRY, *args, **kwargs)

    def on_exit(self, *args, **kwargs):
        self._run_subs(sub_type=self.SUB_EXIT, *args, **kwargs)
        self._entered = False


class Trigger(object):
    def __init__(self, fsm, src, dest, name, ordered=False):
        self._fsm = fsm
        self._src = src
        self._dest = dest
        self._name = name
        self._ordered = ordered
        
    def __call__(self, *args, **kwargs):
        if self._fsm.state in self._src:
            # trigger entry to dest(ination) state
            logging.debug('trig = %s, src = %s, dest = %s', self._name,
                            self._fsm.state, self._dest)
            logging.debug('args = %s, kwargs = %s', args, kwargs)

            # transition out of current state - call the state's on_exit( )
            self._fsm._states[self._fsm.state].on_exit(*args, **kwargs)

            new_state = self._fsm._states[self._dest]

            self._fsm.state = new_state
            new_state.on_entry(*args, **kwargs)
            new_state(*args, **kwargs)

            if self._ordered:
                src = self._src
                self._dest = src[ (src.index(self._fsm.state) + 1) % len(src) ]
        else:
            # FIXME: should print error message and carry on
            raise ValueError('Bad transition from %s to %s via a %s trigger' %
                                (self._fsm.state, self._dest, self._name))


# TODO: docstrings!!!
class FSM(object):
    def __init__(self, initial=None, states=None, trigger_map = None,
                 ordered=False, loop=False):

        self._state_iter = None
        self._states = {}
        if states:
            self.add_states(states)           

        if ordered:
            if len(states) < 2:
                raise ValueError('Cannot have < 2 states in ordered FSM')
            if trigger_map is not None:
                raise ValueError('An orrdered FSM cannot specify a trigger_map')

            # states will get modified - make a copy
            states_cp = copy.copy(states)
            trigger_map = [ ['next_state', states_cp, states_cp[1]], ]
            if not initial:
                initial = states[0]

        # FIXME: listify this
        self.add_states([initial])

        # _state is the current State the machine is in
        self._state = self._states[initial]

        self._triggers = {}
        if trigger_map:
            for trig, src, dest in trigger_map:
                # dest MUST be a single string or State
                self.add_states([dest])

                # src could be a list of source-states
                if not isinstance(src, list):
                    src = [src]
                # assume src is a string
                self.add_states(src)

                if not trig in self._triggers:
                    _trig = None
                    if isinstance(trig, Trigger):
                        # add new Trigger attr to self
                        setattr(self, trig.name, trig)
                        _trig = trig.name
                    else:
                        # trig must be a simple string
                        # create a new Trigger if we don't already have one
                        # first, fixup src list if it contains State objects
                        for i, s in enumerate(src):
                            if isinstance(s, State):
                                src[i] = s.name

                        if isinstance(dest, State):
                            dest = dest.name

                        if ordered and not loop:
                            self._state_iter = src

                        _trig = Trigger(self, src, dest, trig, ordered=ordered)
                        setattr(self, trig, _trig)
                    self._triggers[trig] = _trig

    def __getitem__(self, item):
        return self._states[item]

    def __iter__(self):
        return iter(self._state_iter)

    def add_states(self, states):
        for state in states:
            if not state in self._states:
                if not isinstance(state, State):
                    # assume state was provided as a string
                    state = State(name=state)
                self._states[state.name] = state

    @property
    def state(self):
        return self._state.name

    @state.setter
    def state(self, state):
        self._state = state
