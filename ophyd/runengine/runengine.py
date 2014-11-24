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

    def _move_positioners(self, positioners=None, settle_time=None, **kwargs):
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
        if settle_time is not None:
            time.sleep(settle_time)
        #return {pos.name: pos.position for pos in positioners}
        ret = {}
        [ret.update(pos.report) for pos in positioners]
            
        return ret

    def _start_scan(self, **kwargs):
        print('Starting Scan...{}'.format(kwargs))
        hdr = kwargs.get('header')
        evdesc = kwargs.get('event_descriptor')
        dets = kwargs.get('detectors')
        trigs = kwargs.get('triggers')

        data = {}
        seqno = 0
        while self._scan is True:
            posvals = self._move_positioners(**kwargs)
            # if we're done iterating over positions, get outta Dodge
            if posvals is None:
                break
            # execute user code
            print('execute user code')
            #detvals = {d.name: d.value for d in dets}
            #TODO: handle triggers here (pvs that cause detectors to fire)
            if trigs is not None:
                for t in trigs:
                    t._set_request(1, wait=True)
            #TODO: again, WTF is with the delays required?
            time.sleep(0.05)
            detvals = {}
            for d in dets:
                detvals.update(d.report)
            time.sleep(0.5)
            data.update(posvals, **detvals)
            #TODO: timestamp this datapoint?
            #data.update({'timestamp': time.time()})
            # pass data onto Demuxer for distribution
            print('datapoint[{}]: {}'.format(seqno,data))
            #event = data_collection.format_event(hdr, evdesc,
            #                                  seq_no=seqno,
            #                                  data=data)
            #data_collection.write_to_event_PV(event)
            time.sleep(0.5)
            seqno += 1
        self._scan = False
        return

    def _get_data_keys(self, **kwargs):
        pos = kwargs.get('positioners')
        det = kwargs.get('detectors')
        ret = {}
        for p in pos:
            ret.update(p.report)
        for d in det:
            ret.update(d.report)

        return ret

    def start_run(self, runid, begin_args=None, end_args=None, scan_args=None):
        # create run_header and event_descriptors
        #header = data_collection.create_run_header(scan_id=runid)
        header = {'run_header': 'Foo'}
        keys = self._get_data_keys(**scan_args)
        #print('keys = %s'%keys)
        event_descriptor = {'a': 1, 'b':2}
        if scan_args is not None:
            scan_args.update(header, **event_descriptor)
        #event_descriptor = data_collection.create_event_descriptor(
        #                    run_header=header, event_type_id=1, data_keys=keys,
        #                    descriptor_name=scan_description)
        # write the header and event_descriptor to the header PV
        #data_collection.write_to_hdr_PV(header, event_descriptor)

        self._begin_run(begin_args)

        self._scan_thread = Thread(target=self._start_scan, 
                                   name='Scanner',
                                   kwargs=scan_args)
        self._scan_thread.daemon = True
        self._scan = True
        self._scan_thread.start()
        self._scan_thread.join()

        self._end_run(end_args)
