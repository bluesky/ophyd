import logging
from itertools import cycle
from collections import OrderedDict

from ..controls.ophydobj import OphydObject


logging.basicConfig(level=logging.DEBUG)


class State(OphydObject):
    '''Base class for use in FSM pattern.
    '''
    SUB_ENTRY = 'entry'
    SUB_EXIT = 'exit'
    SUB_STATE = 'state'

    def __init__(self, name=None, state_cb=None, entry_cb=None, exit_cb=None):
        self._entered = False
        if name is None:
            name = self.__class__.__name__

        self._default_sub = None
        super(State, self).__init__(name=name, register=False)

        if state_cb:
            self.subscribe(state_cb)

        if entry_cb:
            self.subscribe(entry_cb, event_type='entry')

        if exit_cb:
            self.subscribe(exit_cb, event_type='exit')

    def subscribe(self, cb, event_type='state'):
        super(State, self).subscribe(cb, event_type=event_type, run=False)

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

    @property
    def name(self):
        return self._name

    def __call__(self, *args, **kwargs):
        if self._fsm.state in self._src or self._fsm.state == '_initial':
            # trigger entry to dest(ination) state
            logging.debug('trig = %s, src = %s, dest = %s', self._name,
                            self._fsm.state, self._dest)

            # transition out of current state - call the state's on_exit( )
            self._fsm[self._fsm.state].on_exit(*args, **kwargs)

            new_state = self._fsm[self._dest]

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
        self._initial = None
        self._states = OrderedDict()

        if states:
            self._add_states(states)

        if ordered:
            if len(states) < 2:
                raise ValueError('Cannot have < 2 states in ordered FSM')
            if trigger_map is not None:
                raise ValueError('An ordered FSM cannot specify a trigger_map')

            dest = None
            if initial in states:
                dest = states[(states.index(initial) + 1) % len(states)]
                self._initial = self._states[initial]
            else:
                dest = states[0]
            trigger_map = [ ['next_state', states, dest], ]

        if not initial:
            initial = '_initial'
            self._add_states([initial])
            self._initial = self._states[initial]

        self._triggers = {}
        if trigger_map:
            for trig, src, dest in trigger_map:
                # dest MUST be a single string or State
                self._add_states([dest])

                # src could be a list of source-states
                if not isinstance(src, list):
                    src = [src]
                # assume src is a string
                self._add_states(src)

                if not trig in self._triggers:
                    _trig = None
                    if isinstance(trig, Trigger):
                        # add new Trigger attr to self
                        if not hasattr(self, trig):
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

                        if ordered:
                            self._state_iter = src if not loop else cycle(src)

                        _trig = Trigger(self, src, dest, trig, ordered=ordered)
                        if not hasattr(self, trig):
                            setattr(self, trig, _trig)

                    self._triggers[trig] = _trig

        # _state is the current State the machine is in
        self._state = self._states[initial]

    def __getitem__(self, item):
        return self._states[item]

    def __iter__(self):
        return iter(self._state_iter)

    def _add_states(self, states):
        for state in states:
            if not state in self._states:
                if not isinstance(state, State):
                    # assume state was provided as a string
                    state = State(name=state)
                self._states[state.name] = state

    def reset(self):
        # FSM.reset() only make sense for an 'ordered' FSM
        if hasattr(self, 'next_state'):
            keys = self._states.keys()
            self.next_state._dest = keys[(keys.index(self._initial.name) + 1) %
                                         len(keys)]

            self.state = self._initial
        else:
            raise ValueError('Only ordered state machines can be reset')

    @property
    def state(self):
        return self._state.name

    @state.setter
    def state(self, state):
        self._state = state
