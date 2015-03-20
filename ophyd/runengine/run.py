from __future__ import print_function

import threading
import Queue

from ..controls.ophydobj import OphydObject


class Run(object):

    BEGIN_RUN = 0
    END_RUN = 1
    PAUSE_RUN = 2
    RESUME_RUN = 3
    SCAN_EV = 4
    PERIODIC_EV = 5
    SIGNAL_EV = 6
    SCALER_EV = 7
    
    def __init__(self, run_num):
        self._run_num = run_num

    def trigger(self, callable, every=None, **kwargs):
       callable(**kwargs)

    def start(self):
        pass



class RunEngine(object):

    def __init__(self):
        self._fsm_thread = threading.Thread(target=self._fsm)
        self._fsm_thread.daemon = True
        self._fsmq = Queue.Queue()
        self._fsm_thread.start()


    def _fsm(self):
        while True:
            msg = self._fsmq.get(block=True)
            print(msg)

    def message(self, msg):
        self._fsmq.put(msg, block=False)
