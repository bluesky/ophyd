import time
import logging

from ophyd.runengine.fsm import FSM, State


logging.basicConfig(level=logging.DEBUG)


class StateTest(State):
    def __init__(self, **kwargs):
        State.__init__(self, **kwargs)

        def hello( *args, **kwargs):
            logging.debug('Entering %s\n', kwargs.get('obj').name)

        def gbye(*args, **kwargs):
            logging.debug('Leaving %s\n', kwargs.get('obj').name)

        def action(*args, **kwargs):
            logging.debug('In %s, doing stuff...', self.name)
            if args or kwargs:
                logging.debug('args = %s, kwargs = %s', args, kwargs)
            time.sleep(1)


        self.subscribe(hello, event_type='entry')
        self.subscribe(gbye, event_type='exit')
        self.subscribe(action, event_type='state')


class Acquiring(StateTest):
    def __init__(self, **kwargs):
        super(Acquiring, self).__init__(**kwargs)

class Stopped(StateTest):
    def __init__(self, **kwargs):
        super(Stopped, self).__init__(**kwargs)

class Suspended(StateTest):
    def __init__(self, **kwargs):
        super(Suspended, self).__init__(**kwargs)


trigger_map =  [ ['stop', ['acquiring', 'suspended'], 'stopped'],
                 ['pause', 'acquiring', 'suspended'],
                 ['start', ['stopped', 'suspended'], 'acquiring']]

ordered_map = [ 'One', 'Two', 'Three', 'Four']

states = [Stopped(name='stopped'), Acquiring(name='acquiring'), 
          Suspended(name='suspended')]


fsm = FSM(initial='stopped', states=states, trigger_map=trigger_map)
ofsm = FSM(initial='One', states=ordered_map, ordered=True, loop=True)
ofsm2 = FSM(initial='stopped', states=states, ordered=True, loop=True)
ofsm3 = FSM(initial='One', states=ordered_map, ordered=True, loop=False)
ofsm4 = FSM(initial='stopped', states=states, ordered=True, loop=False)
