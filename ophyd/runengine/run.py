from __future__ import print_function

import time
import threading
import Queue

from ..controls.ophydobj import OphydObject
from ..runengine.state import State, FSM


class Acquiring(State):
    def __init__(self):
        State.__init__(self)


class Suspended(State):
    def __init__(self):
        State.__init__(self)

        def do_stuff(**kwargs):
            print(self._name)
            time.sleep(5)

        self.subscribe(do_stuff, event_type='state', run=False)


class Idle(State):
    def __init__(self):
        State.__init__(self)

        def do_stuff(**kwargs):
            print(self._name)
            time.sleep(1)

        self.subscribe(do_stuff, event_type='state', run=False)


class Run(OphydObject):

    SUB_START_RUN = 'start_run'
    SUB_END_RUN = 'end_run'
    SUB_PAUSE_RUN = 'pause_run'
    SUB_RESUME_RUN = 'resume_run'
    
    SUB_SCAN = 'scan'
    SUB_PERIODIC = 'periodic'
    SUB_SCALER = 'scaler'
    SUB_SIGNAL = 'signal'


    def __init__(self, **kwargs):
        # Blocking-Queue for start/stop/pause/resume commands.
        self._cmdq = Queue.Queue()
        self._STARTED = False
        self._threads = []

        self._idle = Idle()
        self._acq = Acquiring()
        self._suspd = Suspended() 
        self._states = [self._idle, self._acq, self._suspd]
        # Inheritance (multiple) may be a better fit here...
        self._fsm = FSM(states=self._states, initial=self._idle)
        self._curr_state = self._fsm.state

        OphydObject.__init__(self, register=False, **kwargs)
        '''
            Initialize default start_run/end_run/pause_run.
            Users can supplement start_run/end_run or override pause_run.

            User subscriptions to start_run are called *after* the default.
            User subscriptions to end_run are called *before* the default.
        '''
        self.subscribe(self._default_start_run, event_type='start_run')
        self.subscribe(self._default_end_run, event_type='end_run')
        self.subscribe(self._default_pause_run, event_type='pause_run')

    def _default_start_run(self, **kwargs):
        print('start_run')

    def _default_end_run(self, **kwargs):
        print('end_run')

    def _default_pause_run(self, **kwargs):
        print('pause_run')
        while True:
            time.sleep(0.1)

    def subscribe(self, cb, event_type=None):
        # wrap callbacks for each subscription-type in our own special sauce
        if 'scan' in event_type:
            self._acq.subscribe(cb, event_type='state', run=False)
        elif 'periodic' in event_type:
            pass
        elif 'signal' in event_type:
            pass
        elif 'scaler' in event_type:
            pass
        else:
            OphydObject.subscribe(self, cb, event_type=event_type, run=False)
    
    def start(self):
        if not self._STARTED:
            self._STARTED = True
            self._run_subs(sub_type=self.SUB_START_RUN, timestamp=None)

            if self._acq._subs['state']:
                self._cmdq.put(self._acq, block=False)
            else:
                # Run was not given any Acquisition callbacks - nothing to do
                self._run_subs(sub_type=self.SUB_END_RUN, timestamp=None)
                return

            self._run()

    def stop(self):
        self._cmdq.put(self._idle, block=False)

    def pause(self):
        self._cmdq.put(self._suspd, block=False)

    def resume(self):
        self._cmdq.put(self._acq, block=False)

    def _run(self):
        try:

            while True:
                try:
                    # Can use _cmdq's timeout parameter to handle Periodic tasks
                    new_state = self._cmdq.get(block=True, timeout=1.0)
                    print('new_state = ', new_state.name)
                    if isinstance(new_state, State):
                        self._curr_state = new_state
                        self._fsm.state(new_state, run=self)
                    else:
                        raise ValueError('Invalid command: %s' % new_state)
                except Queue.Empty:
                    print('cmdq timed out...')
                    self._fsm.state(self._curr_state, run=self)

                    continue

        except KeyboardInterrupt:
            # Transition to Suspended state? Or, to Stopped?
            # If to Stopped, how should a transition to Suspended be affected?
            # Transition to Suspended for now...
            try:
                self._run_subs(sub_type=self.SUB_PAUSE_RUN, timestamp=None)
            except KeyboardInterrupt:
                self._run_subs(sub_type=self.SUB_RESUME_RUN, timestamp=None)
        finally:
            self._run_subs(sub_type=self.SUB_END_RUN, timestamp=None)

    def reset(self):
        [self._reset_sub(s) for s in self._subs]
