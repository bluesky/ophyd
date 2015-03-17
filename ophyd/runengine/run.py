from __future__ import print_function

from threading import Thread


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
        self._fsmq = threading.Queue()


   def _fsm(self):
       while True:
           msg = self._fsmq.get(block=True)

