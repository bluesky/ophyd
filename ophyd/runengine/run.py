from __future__ import print_function

import time
import threading
import Queue
import uuid
import functools
import logging
import copy
import os
import getpass
import grp
import traceback

from ..controls.ophydobj import OphydObject
from .fsm import FSM, State
#from ..session import session
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


class RunDocs(object):
    def __init__(self, **kwargs):
        super(RunDocs, self).__init__()
        self.doc = {'uid': str(uuid.uuid4()), 'time': time.time()}

    @classmethod
    def begin_run(cls, scan_id=None, group=None, owner=None,
                  beamline_config=None, beamline_id=None, **kwargs):
        br_doc = cls().doc

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

    @classmethod
    def end_run(cls, br_event, state, reason=None):
        er_doc = cls().doc

        er_doc['begin_run_event'] = br_event['uid']

        if state in ('success', 'abort', 'fail'):
            er_doc['completion_state'] = state
        else:
            raise ValueError('Completion state must be one of success|abort|fail')

        if reason is not None:
            er_doc['reason'] = reason

        return er_doc

    @classmethod
    def descriptor(cls, br_event, sources, **kwargs):
        desc = cls().doc

        desc['begin_run_event'] = br_event['uid']
        desc['keys'] = {src.name: src.describe() for src in sources}
        if kwargs:
            desc.update(kwargs)

        return desc

    @classmethod
    def event(cls, desc, seq_num, elems):
        event = cls().doc

        event['descriptor'] = desc['uid']
        event['seq_num'] = seq_num
        event['data'] = {k.name: v for k,v in elems.iteritems()}

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
        ret = self.fcn(*args, **kwargs)

        # create an Event Descriptor if we don't have one and Event.save()
        # has been invoked
        if not self._dq.empty() and self.desc is None:
            elems = {}
            while not self._dq.empty():
                elems.update(self._dq.get(False))

            self.desc = RunDocs.descriptor(self._run.begin_run_event, elems,
                                           event_type=self.__name__)
            event_doc = RunDocs.event(self.desc, self.seq_num, elems)
            print('\nevent descriptor =', self.desc, '\n')
            print('\nevent = ', event_doc, '\n')
        elif not self._dq.empty():
            elems = {}
            while not self._dq.empty():
                elems.update(self._dq.get(False))

            # TODO: sanity checking on elems vs self.descriptor
            event_doc = RunDocs.event(self.desc, self.seq_num, elems)
            print('\nevent = ', event_doc, '\n')

        # actuate scaler_events, if we have any for this event
        for callback, scale_factor in self.scaler_events:
            if not (self.seq_num + 1) % scale_factor:
                callback(*args, **kwargs)

        self.seq_num += 1

        return ret

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

    SUB_SCAN = 'trajectory_scan'
    SUB_PERIODIC = 'periodic_scan'
    SUB_SCALER = 'scaler_scan'
    SUB_SIGNAL = 'signal_scan'

    # trigger_map = ['trigger', ['src state_1',,,], 'destination state']
    trigger_map = [ ['start', 'stopped', 'acquiring'],
                    ['pause', 'acquiring', 'suspended'],
                    ['resume', 'suspended', 'acquiring'],
                    ['stop', ['acquiring', 'suspended'], 'stopped'] ]
 
    def __init__(self, **kwargs):
        self._run_state = None
        # Blocking-Queue for start/stop/pause/resume commands.
        self._cmdq = Queue.Queue()
        self._threads = {}
        self._thread_ev = threading.Event()
        self._events = {}

        super(Run, self).__init__(initial='stopped',
                                  trigger_map=Run.trigger_map)
        OphydObject.__init__(self, register=False, **kwargs)

        self['stopped'].subscribe(self._begin_run, event_type='exit')
        # TODO: must also clean up any state here from previous run
        self['stopped'].subscribe(self._stop_threads, event_type='entry')
        self['stopped'].subscribe(self._end_run)
        self['acquiring'].subscribe(self._start_threads,
                                    event_type='entry')
        self['suspended'].subscribe(self._stop_threads,
                                         event_type='entry')

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
        # TODO: emit begin_run_event
        print('\n\nbegin_run_event\n\n')
        self.begin_run_event = RunDocs.begin_run()
        print(self.begin_run_event)

    def _end_run(self, status=None, reason=None, **kwargs):
        # TODO: emit end_run_event
        print('\n\nend_run_event\n\n')
        self.end_run_event = RunDocs.end_run(self.begin_run_event, status,
                                             reason=reason)
        print(self.end_run_event)

    def _trajectory_scan(self, scan, **kwargs):
        for state in scan:
            if not self._thread_ev.is_set():
                scan.next_state(scan, **kwargs)
            else:
                return

        data = copy.copy(scan.data)
        scan.data_buf.append(data)
        scan.data.clear()

    def _add_event(self, ev_type, cb):
        # NOTE - cb is a Scan object here
        event = Event(self._trajectory_scan, self, name=ev_type)
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
        elif 'signal_scan' in event_type:
            raise NotImplementedError('Signal events not supported. Yet')
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
