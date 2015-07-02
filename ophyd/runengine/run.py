from __future__ import print_function

import time
import threading
import Queue
import uuid
import functools

from ..controls.ophydobj import OphydObject
from ..runengine.fsm import FSM, State


class Acquiring(State):
    def __init__(self, threads=None):
        self._threads = threads
        State.__init__(self)


class Suspended(State):
    def __init__(self):
        State.__init__(self)

        def do_stuff(**kwargs):
            print(self._name)
            time.sleep(5)

        self.subscribe(do_stuff, event_type='state')


class Idle(State):
    def __init__(self):
        State.__init__(self)

        def do_stuff(**kwargs):
            print(self._name)
            time.sleep(1)

        self.subscribe(do_stuff, event_type='state')


class Event(object):
    def __init__(self, fcn):
        self.seq_num = 0
        self.uuid = str(uuid.uuid4())
        self.desc = None # event descriptor
        self.time = None
        self.data = None
        self.fcn = fcn
        # scaler_events are 2-tuples - (fcn, scale)
        self.scaler_events = []
        functools.update_wrapper(self, fcn)

    def __call__(self, *args, **kwargs):
        self.fcn(*args, **kwargs)

        for callback, scale_factor in self.scaler_events:
            if not (self.seq_num + 1) % scale_factor:
                callback(*args, **kwargs)

        self.seq_num += 1


class Run(OphydObject):
    ''' A state-machine for controlling scans.

        Upon construction, a Run enters the Idle state.
        After configuration with appropriate scan-types,
        a Run can be made to execute a scan by transitioning
        to the Acquiring state via Run.start().
        
        Issuing Run.stop() (or Ctrl-C) will terminate an executing 
        Run and its scan(s). Similarly, Run.pause() will suspend 
        acquisition until Run.resume() or Run.stop() is issued.

        Examples:
        ------------
        Generate a Run that produces only start_run and end_run events:

        run = Run()
        run.start()
        
    '''

    SUB_START_RUN = 'start_run'
    SUB_END_RUN = 'end_run'
    SUB_PAUSE_RUN = 'pause_run'
    SUB_RESUME_RUN = 'resume_run'
    
    SUB_SCAN = 'trajectory_scan'
    SUB_PERIODIC = 'periodic_scan'
    SUB_SCALER = 'scaler_scan'
    SUB_SIGNAL = 'signal_scan'


    def __init__(self, **kwargs):
        # Blocking-Queue for start/stop/pause/resume commands.
        self._cmdq = Queue.Queue()
        self._STARTED = False
        self._threads = {}
        self._thread_ev = threading.Event()
        self._events = {}

        self._idle = Idle()
        self._acq = Acquiring(threads=self._threads)
        # self._acq.subscribe(self._default_acquire, event_type='state')
        self._suspd = Suspended() 
        self._states = [self._idle, self._acq, self._suspd]
        # Inheritance (multiple) may be a better fit here...
        self._fsm = FSM(states=self._states, initial=self._idle.name)
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
        self.subscribe(self._default_resume_run, event_type='resume_run')

    def _default_start_run(self, **kwargs):
        print('start_run')

   def _begin_run(self, *args, **kwargs):
        # TODO: emit begin_run_event
        print('\n\nbegin_run_event\n\n')

    def _end_run(self, status=None, **kwargs):
        # TODO: emit end_run_event
        print('\n\nend_run_event\n\n')
        if status:
            print('status =', status)

    def _trajectory_scan(self, scan):
        for state in scan:
            if not self._thread_ev.is_set():
                scan.next_state(scan)
            else:
                # TODO: make custom exception here.
                # If ScanContexts are catching these, some differentiation
                # is required.
                raise ThreadCancel('\nrun._thread_ev was set\n')

        data = copy.copy(scan.data)
        scan.data_buf.append(data)
        scan.data.clear()

    def _add_event(self, ev_type, cb):
        # NOTE - cb is a Scan object here
        event = Event(self._trajectory_scan, name=ev_type)
        thread = ScanContext(event, cb, self, name=ev_type)
        self._events[event.__name__] = event
        self._threads[thread.name] = thread

    # Need kwargs here to carry "period", "signal", and "scaler" 
    # supplementary arguments ("when", "what signal", "scaling factor").
    def subscribe(self, cb, event_type=None, **kwargs):
        ''' Subscribe to Run events.

            Add callbacks for Run start, stop, pause, resume event
            and add callbacks Scan types: trajectory scans, period scans,
            signal scans, and scaler scans.

        '''
        # wrap callbacks for each subscription-type in our own special sauce
        if 'trajectory_scan' in event_type:
            self._acq.subscribe(cb, event_type='state')
        elif 'periodic_scan' in event_type:
            if 'periodic' not in self._threads:
                period = kwargs.pop('period', None)
                if period is None:
                    raise ValueError('No period specified for Periodic event %s' % cb)

                cb = Event(cb)
                timer = TimerThread(cb, self._thread_ev,
                                period, name='periodic', **kwargs)
                self._events[cb.__name__] = cb
                self._threads[timer.name] = timer
            else:
                raise ValueError('Multiple Periodic events not available')
        elif 'signal_scan' in event_type:
            raise NotImplementedError('Signal events not available yet')
        elif 'scaler_scan' in event_type:
            event = kwargs.pop('event', None)
            if event is None:
                raise ValueError('No event argument provided for %s' % cb)
            scale = kwargs.pop('scale', None)
            if scale is None:
                raise ValueError('No scaling factor given for event %s' % cb)
            scale = int(scale)
            # add the callback to the Event to be scaled
            cb = Event(cb)
            scaled_event = self._events[event.__name__]
            scaled_event.scaler_events.append((cb, scale))
            self._events[cb.__name__] = cb
        else:
            OphydObject.subscribe(self, cb, event_type=event_type, run=False)
    
    def start(self):
        if not self._STARTED:
            self._STARTED = True
            self._run_subs(sub_type=self.SUB_START_RUN, timestamp=None)

            if self._threads:
                for thread in self._threads.itervalues():
                    self._acq.subscribe(thread.start, event_type='state')
            else:
                # Run was not given any Acquisition callbacks - nothing to do
                self._run_subs(sub_type=self.SUB_END_RUN, timestamp=None)
                return

            #self._cmdq.put(self._acq, block=False)
            #self._run()
            self._acq()
            self._wait_threads()

    def stop(self):
        self._cmdq.put(self._idle, block=False)

    def pause(self):
        self._cmdq.put(self._suspd, block=False)

    def resume(self):
        self._cmdq.put(self._acq, block=False)

    def _wait_threads(self):
        try:
            while True:
                for name, thread in self._threads.items():
                    thread.join(timeout=0.01)
                    if not thread.is_alive():
                        self._threads.pop(name)
        except KeyboardInterrupt:
            print('Terminating Run %s' % 101)
            self._thread_ev.set()
            for name, thread in self._threads.items():
                print('Waiting for threads to terminate')
                thread.join(timeout=0.2)
                if not thread.is_alive():
                    self._threads.pop(name)
        finally:
            self._run_subs(sub_type=self.SUB_END_RUN, timestamp=None)


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


class TimerThread(threading.Thread):
    def __init__(self, fcn, event, period, *args, **kwargs):
        self._period = period
        self._event = event
        self._fcn = fcn
        self._args = args
        self._kwargs = kwargs
        super(TimerThread, self).__init__(name=kwargs.pop('name'))
        self.daemon = True

    def start(self, *args, **kwargs):
        # OphydObject _run_subs() will append 'obj' and 'timestamp' kwargs
        self._args += args
        self._kwargs.update(kwargs)
        super(TimerThread, self).start()

    def run(self):
        delta_t = self._period
        shift = 0.0

        while True:
            flag = self._event.wait(timeout=delta_t)
            wake_time = time.time()

            if not flag:
                self._fcn(*self._args, **self._kwargs)

                shift = time.time() - wake_time
                delta_t = self._period - shift
            else:
                print('Abort flag set. %s terminating.' % self.name)
                break
