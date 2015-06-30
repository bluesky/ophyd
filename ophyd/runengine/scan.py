import logging
import time
import copy
import functools

import numpy as np

from .fsm import FSM, State
from .run import Run


logging.basicConfig(level=logging.DEBUG)

# TODO: add argument version (timeout, etc)
def blocking(fcn):
    @functools.wraps(fcn)
    def wrapper(scan, **kwargs):
        while not (scan.run._thread_ev.is_set() or fcn(scan, **kwargs)):
            time.sleep(0.05)
    return wrapper

def next_pos(scan, **kwargs):
    pt = next(scan.path_gen)
    scan.current_pt = pt if isinstance(pt, list) else [pt]

def move_all(scan, **kwargs):
    scan.wait_status = [pos.move(pt, wait=False) for pos, pt in 
                        zip(scan.positioners, scan.current_pt)]

@blocking
def wait_all(scan, **kwargs):
    return all(s.done for s in scan.wait_status)

def pos_read(scan, **kwargs):
    scan.data.update({pos.name: pos.read() for pos in scan.positioners})

    event = kwargs.get('event', None)
    if event:
        event.save(data)

def det_acquire(scan, **kwargs):
    detectors = [det for det in scan.detectors
                 if hasattr(det, 'acquire')]
    scan.wait_status = [det.acquire() for det in detectors]

def det_read(scan, **kwargs):
    scan.data.update({det.name: det.read() for det in scan.detectors})

    event = kwargs.get('event', None)
    if event:
        event.save(data)


class Scan(FSM):
    positioners = None
    detectors = []
    path = None
    wait_status = None
    current_pt = None

    def __init__(self, states):
        super(Scan, self).__init__(states=states, ordered=True, loop=False)

    def path_iter(self, path):
        for pt in path:
            yield pt

    def __call__(self, pos, st, end, npts, execute=True, **kwargs):
        self.run = Run()

        self.run.subscribe(self, event_type='trajectory_scan')

        self.path = np.linspace(st, end, npts+1).tolist()
        self.path_gen = self.path_iter(self.path)
        self.positioners = pos if isinstance(pos, list) else [pos]

        if execute:
            self.run.start()
        else:
            '''At this point, the scan is "primed" with a path.
               Other scaler, timed, signal events can be added to 
               return Run object. Execute that with run.start().
            '''
            return self.run


class PeriodScan(Scan):
    '''At a minimum, period must not be less than the duration of the longest
       activity carried out during this scan. Obviously.
    '''
    period = None

    def __init__(self, states):
       super(PeriodScan, self).__init__(states=states)

    def path_iter(self, path):
        delta_t = path
        wake_time = 0
        while True:
            time.sleep(delta_t)
            wake_time = time.time() + path
            yield delta_t
            delta_t = wake_time - time.time()
            if delta_t < 0.0:
                logging.info('Periodic event deadline exceeded by %s [s]'
                                  % abs(delta_t))
                delta_t = path

    def stop(self, *args, **kwargs):
        self.run.stop(status='success')

    def __call__(self, period, duration, execute=True, **kwargs):
        '''Execute a scan periodically.

        Parameters
        ----------
        period : int
            The time between invocations, in seconds
        duration : int or None
            Total duration to run, in seconds.
            i.e. total cycles = ceil(duration/period)
            If duration is None, the scan will run until canceled externally.
        '''
        self.run = Run()
        self.run.subscribe(self, event_type='periodic_scan')

        if period < 0.0:
            period = 0
        self.period = period

        if duration is not None:
            scale = 1
            if duration > 0.0 and duration >= self.period:
                scale = int(np.ceil(duration/period))
            self.run.subscribe(self.stop, event_type='scaler_scan',
                               event='periodic', scale=scale)

        self.path_gen = self.path_iter(self.period)

        if execute:
            self.run.start()
        else:
            return self.run
