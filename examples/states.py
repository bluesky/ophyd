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

        def action(*args, **kwargs):
            print('In %s, doing stuff...' % self.name)
            if args or kwargs:
                print('args = ', args, 'kwargs = ', kwargs)
            time.sleep(1)


        self.subscribe(hello, event_type='entry')
        self.subscribe(gbye, event_type='exit')
        self.subscribe(action, event_type='state')


class Acquiring(StateTest):
    pass

class Idle(StateTest):
    pass

class Suspended(StateTest):
    pass


def test():
    idle = Idle()
    susp = Suspended()
    acq = Acquiring()

    states = [idle, acq, susp]

    fsm = FSM(states=states, initial=idle, verbose=False)

    try:
        while True:
            fsm.state(acq)
    except KeyboardInterrupt:
        print('Caught SIGINT...')
        fsm.state(susp, kw='world')
        fsm.state(idle)
    
if __name__ == '__main__':
    test()
