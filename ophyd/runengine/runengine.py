from __future__ import print_function
import logging
from threading import Thread
from Queue import Queue
import time

#from databroker.api import data_collection



class Demuxer(object):

    def __init__(self):
        self.inpq = Queue()
        self.outpqs = []
        self.thread = Thread(target=self.demux, args=(self.inpq, self.outpqs))
        self.demux = False

    def start(self):
        self.demux = True
        self.thread.start()

    def stop(self):
        self.demux = False
        self.thread.join()

    def enqueue(self, data):
        self.inpq.put(data)

    # return an  output queue to pull data from
    def register(self):
        outpq = Queue()
        self.outpqs.append(outpq)
        return outpq

    def demux(self, inpq, outpqs):
        while self.demux:
            # block waiting for input
            inp = inpq.get(block=True)

            # TODO debug statement
            print('Demuxer: %s' % inp)

            for q in self.outpqs:
                q.put(inp)
        return


class RunEngine(object):
    '''

    '''
    def __init__(self, logger):
        self._demuxer = Demuxer()

    # start/stop/pause/resume are external api methods
    def start(self):
        pass

    def stop(self):
        self._scan = False

    def pause(self):
        pass

    def resume(self):
        pass

    def _begin_run(self, arg):
        # run any registered user functions
        # save user data (if any), and run_header
        print('Begin Run...')

    def _end_run(self, arg):
        print('End Run...')

    def _move_positioners(self, positioners=None):
        positioners = positioners['positioners']
        for pos in positioners:
            try:
                pos.move_next(wait=False)
            except StopIteration as si:
                return None
        #TODO: FIXME why the F**K is this delay necessary for proper operation!!!
        time.sleep(0.05)
        moving = any([pos.moving for pos in positioners])
        #TODO: this should iterate at most N times to catch hangups
        while moving:
            time.sleep(0.1)
            moving = any([pos.moving for pos in positioners])
        #if dwell_time != 0:
        #    time.sleep(dwell_time)
        return {pos.name: pos.position for pos in positioners}

    def _start_scan(self, **kwargs):
        print('Starting Scan...')
        dets = kwargs.get('detectors')

        while self._scan is True:
            posvals = self._move_positioners(kwargs)
            # if we're done iterating over positions, get outta Dodge
            if posvals is None:
                break
            # execute user code
            print('execute user code')
            detvals = {d.name: d.value for d in dets}
            time.sleep(0.5)
            # pass data onto Demuxer for distribution
            print('distribute data: %s, %s'%(posvals,detvals))
            time.sleep(0.5)
        self._scan = False
        return

    def start_run(self, runid, begin_args=None, end_args=None, scan_args=None):
        # gather run_header data
        self._begin_run(begin_args)
        self._scan_thread = Thread(target=self._start_scan, 
                                   name='Scanner',
                                   kwargs=scan_args)
        self._scan_thread.daemon = True
        self._scan = True
        self._scan_thread.start()
        self._scan_thread.join()
        self._end_run(end_args)
