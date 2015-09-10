import logging

from ophyd.runengine.scan import *
from ophyd.controls.positioner import Positioner
from ophyd.controls import Signal


logging.basicConfig(level=logging.DEBUG)


######################################################
### Some simple objects for testing...
######################################################
class NullPositioner(Positioner):
    def __init__(self, name=None):
        super(NullPositioner, self).__init__(name=name)

    def move(self, position, wait=False, **kwargs):
        self._started_moving = True
        status = super(NullPositioner, self).move(position, wait=wait,
                                         moved_cb=None, timeout=30.0)
        self._started_moving = False
        self._position = position
        status._finished()

        return status

    # Override read(), as this object has no internal Signal(s)
    def read(self):
        return {self.name: [self._position, time.time()]}

    def describe(self):
        """Return the description as a dictionary"""
        return {self.name: {'source': 'SIM:{}'.format(self.name)}}


class NullDetector(Signal):
    def __init__(self, **kwargs):
        super(NullDetector, self).__init__(**kwargs)
        self.done = True

    def acquire(self):
        time.sleep(3)
        return self

######################################################
### create a 1-d Trajectory and Periodic scans 
######################################################
mtr = NullPositioner(name='nullmtr')
det = NullDetector(name='nulldet', value=5)

states = [ State(name='next_pos', state_cb=next_pos),
           State(name='move_all', state_cb=move_all),
           State(name='wait_all', state_cb=wait_all),
           State(name='pos_read', state_cb=pos_read),
           State(name='det_acquire', state_cb=det_acquire),
           State(name='wait_acquire', state_cb=wait_all),
           State(name='det_read', state_cb=det_read)
         ]
scan = Scan(states=states)
scan.detectors.append(det)

states = [ State(name='next_pos', state_cb=next_pos),
           State(name='det_acquire', state_cb=det_acquire),
           State(name='wait_acquire', state_cb=wait_all),
           State(name='det_read', state_cb=det_read)
         ]
pscan = PeriodScan(states=states)
