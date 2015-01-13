from __future__ import print_function
# import logging
import sys
import time
from threading import Thread
from Queue import Queue

from ..session import register_object
from ..controls.signal import SignalGroup

try:
    from databroker.api import data_collection
except ImportError:
    data_collection = None

try:
    from metadataStore.api.collection import create_event
except ImportError as ex:
    print('[!!] Failed to import metadataStore api: %s' % ex, file=sys.stderr)
    create_event = None


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
        self._logger = register_object(self)
        self._scan_state = False

    # start/stop/pause/resume are external api methods
    def start(self):
        pass

    def stop(self):
        self._scan_state = False

    @property
    def running(self):
        return self._scan_state

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
        try:
            status = [pos.move_next(wait=False)[1]
                      for pos in positioners]
        except StopIteration:
            return None

        # status now holds the MoveStatus() instances
        time.sleep(0.05)
        # TODO: this should iterate at most N times to catch hangups
        while not all(s.done for s in status):
            time.sleep(0.1)

        if settle_time is not None:
            time.sleep(settle_time)
        # return {pos.name: pos.position for pos in positioners}
        ret = {}
        [ret.update({pos.name: pos.position}) for pos in positioners]

        return ret

    def _start_scan(self, **kwargs):
        # print('Starting Scan...{}'.format(kwargs))
        hdr = kwargs.get('header')
        evdesc = kwargs.get('event_descriptor')
        dets = kwargs.get('detectors')
        trigs = kwargs.get('triggers')
        data = kwargs.get('data')

        seqno = 0
        while self._scan_state is True:
            posvals = self._move_positioners(**kwargs)
            # if we're done iterating over positions, get outta Dodge
            if posvals is None:
                break
            # execute user code
            # print('execute user code')
            # detvals = {d.name: d.value for d in dets}
            # TODO: handle triggers here (pvs that cause detectors to fire)
            if trigs is not None:
                for t in trigs:
                    t.put(1, wait=True)
            # TODO: again, WTF is with the delays required? CA is too fast,
            # and python is too slow (or vice versa!)
            time.sleep(0.05)
            detvals = {}
            for det in dets:
                if isinstance(det, SignalGroup):
                    # If we have a signal group, loop over all names
                    # and signals
                    for sig in det.signals:
                        detvals.update({sig.name: sig.value})
                else:
                    detvals.update({det.name: det.value})
            detvals.update(posvals)
            # TODO: timestamp this datapoint?
            # data.update({'timestamp': time.time()})
            # pass data onto Demuxer for distribution
            print('datapoint[{}]: {}'.format(seqno, detvals))
            event = data_collection.format_event(hdr, evdesc,
                                                 seq_no=seqno,
                                                 data=detvals)
            create_event(event)
            seqno += 1
            # update the 'data' object from detvals dict
            for k, v in detvals.iteritems():
                data[k].append(v)

            if kwargs.get('positioners') is None:
                break
            if len(kwargs.get('positioners')) == 0:
                break
        self._scan_state = False
        return

    def _get_data_keys(self, **kwargs):
        # ATM, these are both lists
        names = [o.name for o in kwargs.get('positioners')]
        for det in kwargs.get('detectors'):
            if isinstance(det, SignalGroup):
                names += [o.name for o in det.signals]
            else:
                names.append(det.name)

        return names

    def start_run(self, runid, begin_args=None, end_args=None, scan_args=None):
        # create run_header and event_descriptors
        header = data_collection.create_run_header(scan_id=runid, **scan_args)
        # header = {'run_header': 'Foo'}
        keys = self._get_data_keys(**scan_args)
        data = {k: [] for k in keys}
        # print('keys = %s'%keys)
        # event_descriptor = {'a': 1, 'b':2}
        event_descriptor = data_collection.create_event_descriptor(
            run_header=header, event_type_id=1, data_keys=keys,
            descriptor_name='Scan Foo')
        if scan_args is not None:
            scan_args['header'] = header
            scan_args['event_descriptor'] = event_descriptor
            scan_args['data'] = data
        # write the header and event_descriptor to the header PV

        self._begin_run(begin_args)

        self._scan_thread = Thread(target=self._start_scan,
                                   name='Scanner',
                                   kwargs=scan_args)
        self._scan_thread.daemon = True
        self._scan_state = True
        self._scan_thread.start()
        try:
            while self._scan_state is True:
                time.sleep(0.10)
        except KeyboardInterrupt:
            self._scan_state = False
            self._scan_thread.join()

        self._end_run(end_args)
        return data
