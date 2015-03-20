from ..controls.ophydobj import OphydObject


class State(OphydObject):
    '''Base class for use in FSM pattern (a la GoF State pattern).

       Subclasses must NOT override the change_state method.
       Subclasses MUST override the state_action method.
    '''
    SUB_ENTRY = 'entry'
    SUB_EXIT = 'exit'

    def __init__(self, name=None, transitions=None):
        self._entered = False
        if name is None:
            name = self.__class__.__name__

        self._default_sub = None
        OphydObject.__init__(self, name=name, register=False)

    def state_action(self):
        raise NotImplementedError("Subclasses must implement the state_action method.")

    def on_entry(self):
        if not self._entered:
            self._entered = True
            self._run_subs(sub_type=self.SUB_ENTRY)

    def on_exit(self):
        self._run_subs(sub_type=self.SUB_EXIT)
        self._entered = False

    def change_state(self, next_state):
        if next_state == self:
            self.on_entry()
            self.state_action()
        else:
            self.on_exit()
            next_state.on_entry()
            next_state.state_action()
