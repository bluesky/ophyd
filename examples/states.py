from __future__ import print_function

import time

from ophyd.runengine.state import State


class StateTest(State):
    def __init__(self):
        State.__init__(self)

        def hello( *args, **kwargs):
            print('Entering %s' % kwargs.get('obj').name)

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

    idle.change_state(idle)
    idle.change_state(acq)
    acq.change_state(susp)
    susp.change_state(susp)
    susp.change_state(acq)
    acq.change_state(idle)

if __name__ == '__main__':
    test()
