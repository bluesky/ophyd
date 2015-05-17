from __future__ import print_function

import time

from ophyd.runengine.state import State, FSM


class StateTest(State):
    def __init__(self):
        State.__init__(self)

        def hello( *args, **kwargs):
            print('Entering %s\n' % kwargs.get('obj').name)

        def gbye(*args, **kwargs):
            print('Leaving %s\n' % kwargs.get('obj').name)

        self.subscribe(hello, event_type='entry', run=False)
        self.subscribe(gbye, event_type='exit', run=False)

class Acquiring(StateTest):
    def state_action(self):
        for i in range(3):
            print('In %s, doing stuff...' % self.name)
            time.sleep(1)


class Idle(StateTest):
    def state_action(self):
        print('In %s, doing stuff...' % self.name)
        time.sleep(1)


class Suspended(StateTest):
    def state_action(self):
        print('In %s, doing stuff...' % self.name)
        time.sleep(1)


def test():
    idle = Idle()
    susp = Suspended()
    acq = Acquiring()

    states = [idle, acq, susp]

    fsm = FSM(states=states, initial=idle)

    try:
        fsm.state = idle
        fsm.state = acq
        fsm.state = susp
        fsm.state = acq
        # try transitions to self. Should skip the on_enter() method
        for i in range(3):
            fsm.state = acq
    except KeyboardInterrupt:
        print('Caught SIGINT...')
        fsm.state = idle
    
if __name__ == '__main__':
    test()
