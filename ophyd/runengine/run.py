from __future__ import print_function

import time
import threading
import Queue
import uuid
import functools
import logging
import os
import getpass
import grp
import traceback

from ..controls.ophydobj import OphydObject
from .fsm import FSM, State
from ..session import register_object
import random


logging.basicConfig(log_level=logging.DEBUG)


class Session(object):
    def get_scan_id(self):
        return random.randint(0, 10000)

    def get_beamline_config(self):
        return {}

    def get_beamline_id(self):
        return 'FUX'


session = Session()

def doc_begin_run(scan_id=None, group=None, owner=None, beamline_config=None,
              beamline_id=None, **kwargs):
    br_doc = {'uid': str(uuid.uuid4()), 'time': time.time()}

    if scan_id is None:
        scan_id = session.get_scan_id()
    br_doc['scan_id'] = scan_id

    if group is None:
        group = grp.getgrgid(os.getgid()).gr_name
    br_doc['group'] = group

    if owner is None:
        owner = getpass.getuser()
    br_doc['owner'] = owner

    if beamline_config is None:
        beamline_config = session.get_beamline_config()
    br_doc['beamline_config'] = beamline_config

    if beamline_id is None:
        beamline_id = session.get_beamline_id()
    br_doc['beamline_id'] = beamline_id

    if kwargs:
        br_doc.update(kwargs)

    return br_doc

def doc_end_run(br_event, state, reason=None):
    er_doc = {'uid': str(uuid.uuid4()), 'time': time.time()}

    er_doc['begin_run_event'] = br_event['uid']

    if state in ('success', 'abort', 'fail'):
        er_doc['completion_state'] = state
    else:
        raise ValueError('Completion state must be one of success|abort|fail')

    if reason is not None:
        er_doc['reason'] = reason

    return er_doc

def doc_descriptor(br_event, sources, **kwargs):
    desc = {'uid': str(uuid.uuid4()), 'time': time.time()}

    desc['begin_run_event'] = br_event['uid']
    desc['keys'] = dict()
    for src in sources.keys():
        name, value = src.describe().popitem()
        desc['keys'][name] = value

    if kwargs:
        desc.update(kwargs)

    return desc

def doc_event(desc, seq_num, elems):
    event = {'uid': str(uuid.uuid4()), 'time': time.time()}

    event['descriptor'] = desc['uid']
    event['seq_num'] = seq_num
    event['data'] = dict()
    [event['data'].update(elem) for elem in elems.values()]

    return event


class Event(object):
    def __init__(self, fcn, run, name=None):
        self.__name__ = name
        self._run = run
        self._dq = Queue.Queue()
        self.seq_num = 0
        self.desc = None # event descriptor
        self.fcn = fcn
        # scaler_events are 2-tuples - (fcn, scale)
        self.scaler_events = []
        if name is None:
            functools.update_wrapper(self, fcn)

    def __call__(self, *args, **kwargs):
        if self.fcn(*args, **kwargs) is False:
            return

        # create an Event Descriptor if we don't have one and Event.save()
        # has been invoked
        if not self._dq.empty() and self.desc is None:
            elems = {}
            while not self._dq.empty():
                elems.update(self._dq.get(False))

            self.desc = doc_descriptor(self._run.begin_run_event, elems,
                                           event_type=self.__name__)
            self._run.evq.put((self.__name__, self.desc))
            event_doc = doc_event(self.desc, self.seq_num, elems)
            self._run.evq.put((self.__name__, event_doc))
            self._run.evq.join()
        elif not self._dq.empty():
            elems = {}
            while not self._dq.empty():
                elems.update(self._dq.get(False))

            # TODO: sanity checking on elems vs self.descriptor
            event_doc = doc_event(self.desc, self.seq_num, elems)
            self._run.evq.put((self.__name__, event_doc))
            self._run.evq.join()

        # actuate scaler_events, if we have any for this event
        for callback, scale_factor in self.scaler_events:
            if not (self.seq_num + 1) % scale_factor:
                callback(*args, **kwargs)

        self.seq_num += 1

    def save(self, elems):
        vals = {e: e.read() for e in elems}
        self._dq.put(vals)


class Run(FSM, OphydObject):
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

    SUB_BEGIN_RUN = 'begin_run'
    SUB_END_RUN = 'end_run'
    SUB_PAUSE_RUN = 'pause_run'
    SUB_RESUME_RUN = 'resume_run'
#    SUB_SCAN = 'trajectory_scan'
#    SUB_PERIODIC = 'periodic_scan'
#    SUB_SCALER = 'scaler_scan'
#    SUB_SIGNAL = 'signal_scan'

    # trigger_map = ['trigger', ['src state_1',,,], 'destination state']
    trigger_map = [ ['start', 'stopped', 'acquiring'],
                    ['pause', 'acquiring', 'suspended'],
                    ['resume', 'suspended', 'acquiring'],
                    ['stop', ['acquiring', 'suspended'], 'stopped'] ]
 
    def __init__(self, **kwargs):
        self._threads = {}
        self._thread_ev = threading.Event()
        self._events = {}
        self.evq = Queue.Queue()

        super(Run, self).__init__(initial='stopped',
                                  trigger_map=Run.trigger_map)
        OphydObject.__init__(self, register=False, **kwargs)

        self['stopped'].subscribe(self._begin_run, event_type='exit')
        # TODO: must also clean up any state here from previous run
        self['stopped'].subscribe(self._stop_threads, event_type='entry')
        self['stopped'].subscribe(self._empty_evq, event_type='entry')
        self['stopped'].subscribe(self._end_run)
        self['acquiring'].subscribe(self._start_threads,
                                    event_type='entry')
        self['acquiring'].subscribe(self._tend_evq)
        self['suspended'].subscribe(self._stop_threads,
                                         event_type='entry')

        self._session = register_object(self, set_vars=False)

    def _publish_run_doc(self, event, doc):
        self._run_subs(doc, sub_type=event)
        self.evq.task_done()

    def _tend_evq(self, *args, **kwargs):
        while self.state == 'acquiring':
            try:
                msg = self.evq.get(block=True, timeout=0.1)
            except Queue.Empty:
                continue
            except KeyboardInterrupt:
                # TODO: check for and distribute evq contents
                return

            self._publish_run_doc(*msg)

    def _empty_evq(self, *args, **kwargs):
        while not self.evq.empty():
            msg = self.evq.get(block=False)
            self._publish_run_doc(*msg)

    def _start_threads(self, *args, **kwargs):
        if self._threads:
            if self._thread_ev.is_set():
                self._thread_ev.clear()
            [thread.start() for thread in self._threads.itervalues()]
        else:
            # given nothing to do
            self.stop(status='success')

    def _stop_threads(self, *args, **kwargs):
        if self._threads:
            self._thread_ev.set()

    def _begin_run(self, *args, **kwargs):
        print('\n\nbegin_run_event\n\n')
        self.begin_run_event = doc_begin_run()
        #print(self.begin_run_event)
        self._run_subs(self.begin_run_event, sub_type='begin_run')

    def _end_run(self, status=None, reason=None, **kwargs):
        print('\n\nend_run_event\n\n')
        self.end_run_event = doc_end_run(self.begin_run_event, status,
                                             reason=reason)
        self._run_subs(self.end_run_event, sub_type='end_run')

    def _trajectory_scan(self, scan, **kwargs):
        for state in scan:
            if not self._thread_ev.is_set():
                scan.next_state(scan, **kwargs)
            else:
                return False

    def _add_event(self, ev_type, cb):
        # NOTE - cb is a Scan object here
        event = Event(self._trajectory_scan, self, name=ev_type)
        thread = ScanContext(event, cb, self, name=ev_type)
        self._events[event.__name__] = event
        self._threads[thread.name] = thread
        self._subs[event.__name__] = list()

    # Need kwargs here to carry "period", "signal", and "scaler" 
    # supplementary arguments ("when", "what signal", "scaling factor").
    def trigger(self, cb, event_type=None, **kwargs):
        ''' Configure Run with callbacks for scan types.

            Add callbacks for Run start, stop, pause, resume event
            and add callbacks Scan types: trajectory scans, period scans,
            signal scans, and scaler scans.

        Parameters:
        ------------
        cb: callable
            If event_type is 'trajectory_scan' or 'periodic_scan', cb must
            be a Scan instance.

        event_type: string
            One of 'trajectory_scan', 'periodic_scan', 'scaler_scan',
            'signal_scan', 'pause_run', or 'resume_run'.

        kwargs:
            If event_type is 'scaler_scan', the following keyword arguments
            are required:

            event: string
                   The name of the event to scale

            scale: integer
                   Invoke callback, cb, every 'scale' number of 'event'(s)

                   Eg:
                   run.trigger(timer, event_type='periodic_scan')
                   run.trigger(mycb, event_type='scaler_scan', event='timer',
                               scale=4)
        '''
        # wrap callbacks for each subscription-type in our own special sauce
        if 'trajectory_scan' in event_type:
            if 'trajectory' not in self._threads:
                self._add_event('trajectory', cb)
            else:
                raise ValueError('Multiple Trajectory events not supported')
        elif 'periodic_scan' in event_type:
            if 'periodic' not in self._threads:
                self._add_event('periodic', cb)
            else:
                raise ValueError('Multiple Periodic events not supported')
        elif 'scaler_scan' in event_type:
            event = kwargs.pop('event', None)
            if event is None:
                raise ValueError('No event argument provided for %s' % cb)
            scale = kwargs.pop('scale', None)
            if scale is None:
                raise ValueError('No scaling factor given for event %s' % cb)
            scale = int(scale)

            # add the callback to the Event to be scaled
            cb = Event(cb, self)
            scaled_event = self._events[event]
            scaled_event.scaler_events.append((cb, scale))
            self._events[cb.__name__] = cb
            self._subs[cb.__name__] = list()
        elif 'signal_scan' in event_type:
            raise NotImplementedError('Signal events not supported. Yet')
        elif 'pause_run' in event_type:
            self['suspended'].subscribe(cb, event_type='enter')
        elif 'resume_run' in event_type:
            self['suspended'].subscribe(cb, event_type='exit')
        else:
            raise ValueError('%s is not a supported event.' % event_type)
 
    def subscribe(self, cb, event_type=None):
        '''Subscribe to receive Run Docs.

        Parameters:
        -----------
        cb: callable
            The callback to invoke for 'event_type' Run Docs
        event_type: string
            One of 'begin_run' or 'end_run' or any of the registered
            trigger events (see Run.trigger). '*' may be used to subscribe
            to all Run Doc producing events.
        '''
        if event_type == '*':
            for event in self._events:
                OphydObject.subscribe(self, cb, event_type=event, run=False)
        else:
            OphydObject.subscribe(self, cb, event_type=event_type, run=False)
 

class ScanContext(object):
    def __init__(self, event, scan, run, **kwargs):
        self.name = kwargs.pop('name')
        self._event = event 
        self._scan = scan
        self._run = run

        self._thread = threading.Thread(target=self.execute, name=self.name)
        self._thread.daemon = True

    def start(self, *args, **kwargs):
        if not self._thread.is_alive():
            self._thread = threading.Thread(target=self.execute, name=self.name)
            self._thread.start()

    def execute(self):
        scan = self._scan

        while not self._run._thread_ev.is_set():
            try:
                self._event(scan, event=self._event)
            except StopIteration as si:
                exc = traceback.format_exc()
                logging.debug('%s', exc)
                scan.run.stop(status='success')
                return
            except Exception as ex:
                exc = traceback.format_exc()
                logging.debug('%s', exc)
                if self._run.state != 'stopped':
                    scan.run.stop(status='fail', reason=exc)
                    raise ex
                return
