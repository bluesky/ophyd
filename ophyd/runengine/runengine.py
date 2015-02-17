from __future__ import print_function
# import logging
import sys
import getpass
import os
import time
from threading import Thread
from Queue import Queue
import numpy as np
from ..session import register_object
from ..controls.signal import SignalGroup

from metadatastore import api as mds

# Data formatting helper function
def _get_info(positioners=None, detectors=None, data=None):
    """Helper function to extract information from the positioners/detectors
    and send it over to metadatastore so that ophyd is insulated from mds
    spec changes

    Parameters
    ----------
    positioners : list, optional
        List of ophyd positioners
    detectors : list
        List of ophyd detectors, optional
    data : dict
        Dictionary of actual data
    """
    pv_info = {pos.name: {'source': pos.report['pv'],
                          'dtype': 'number',
                          'shape': None}
               for pos in positioners}

    def get_det_info(detector):
        """Internal function to grab info from a detector
        """
        val = np.asarray(data[detector.name])
        dtype = 'number'
        try:
            shape = val.shape
        except AttributeError:
            # val is probably a float...
            shape = None
        source = "PV:{}".format(detector.pvname)
        if not shape:
            dtype = 'array'
        return {detector.name: {'source': source, 'dtype': dtype,
                                'shape': shape}}

    for det in detectors:
        if isinstance(det, SignalGroup):
            for sig in det.signals:
                pv_info.update(get_det_info(sig))
        else:
            pv_info.update(get_det_info(det))

    return pv_info

class Demuxer(object):
    '''Demultiplexer

    Attributes
    ----------
    inpq : Queue
    outpqs : list of Queues
    thread : threading.Thread
    demux : bool

    '''
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
    '''The run engine

    Parameters
    ----------
    logger : logging.Logger
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

    def _run_start(self, arg):
        # run any registered user functions
        # save user data (if any), and run_header
        print('Begin Run...')

    def _end_run(self, arg):
        state = arg.get('state', 'success')
        bre = arg['run_start']
        mds.insert_run_stop(bre, time.time(), exit_status=state)
        print('End Run...')

    def _move_positioners(self, positioners=None, settle_time=None, **kwargs):
        try:
            status = [pos.move_next(wait=False)[1] for pos in positioners]
        except StopIteration:
            return None

        # status now holds the MoveStatus() instances
        time.sleep(0.05)
        # TODO: this should iterate at most N times to catch hangups
        while not all(s.done for s in status):
            time.sleep(0.1)
        if settle_time is not None:
            time.sleep(settle_time)

        # use metadatastore to format the events so that ophyd is insulated from
        # metadatastore spec changes
        return {
            pos.name: {
                'timestamp': pos.timestamp[pos.pvname.index(pos.report['pv'])],
                'value': pos.position}
            for pos in positioners}

    def _start_scan(self, **kwargs):
        # print('Starting Scan...{}'.format(kwargs))
        run_start = kwargs.get('run_start')
        dets = kwargs.get('detectors')
        trigs = kwargs.get('triggers')
        data = kwargs.get('data')

        # creation of the event descriptor should be delayed until the first
        # event comes in. Set it to None for now
        event_descriptor = None

        seq_num = 0
        while self._scan_state is True:
            print('self._scan_state is True in self._start_scan')
            posvals = self._move_positioners(**kwargs)
            print('moved positioners')
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
                    # print('vars(det) in ophyd _start_scan', vars(det))
                    for sig in det.signals:
                        detvals.update({sig.name: {
                            'timestamp': sig.timestamp[sig.pvname.index(sig.report['pv'])],
                            'value': sig.value}})
                else:
                    detvals.update({
                        det.name: {'timestamp': det.timestamp,
                                   'value': det.value}})
            detvals.update(posvals)
            detvals = mds.format_events(detvals)
            # TODO: timestamp this datapoint?
            # data.update({'timestamp': time.time()})
            # pass data onto Demuxer for distribution
            print('datapoint[{}]: {}'.format(seq_num, detvals))
            # grab the current time as a timestamp that describes when the
            # event data was bundled together
            bundle_time = time.time()
            # actually insert the event into metadataStore
            try:
                print('\n\ninserting event {}\n------------------'.format(seq_num))
                event = mds.insert_event(event_descriptor=event_descriptor,
                                         time=bundle_time, data=detvals,
                                         seq_num=seq_num)
            except mds.EventDescriptorIsNoneError:
                # the time when the event descriptor was created
                print('event_descriptor has not been created. creating it now...')
                evdesc_creation_time = time.time()
                data_key_info = _get_info(positioners=kwargs.get('positioners'),
                                          detectors=dets, data=detvals)

                event_descriptor = mds.insert_event_descriptor(
                    run_start=run_start, time=evdesc_creation_time,
                    data_keys=mds.format_data_keys(data_key_info))
                print('\n\nevent_descriptor: {}\n'.format(vars(event_descriptor)))
                # insert the event again. this time it better damn well work
                print('\n\ninserting event {}\n------------------'.format(seq_num))
                event = mds.insert_event(event_descriptor=event_descriptor,
                                         time=bundle_time, data=detvals,
                                         seq_num=seq_num)
            print('\n\nevent {}\n--------\n{}'.format(seq_num, vars(event)))

            seq_num += 1
            # update the 'data' object from detvals dict
            for k, v in detvals.items():
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

    def start_run(self, runid, start_args=None, end_args=None, scan_args=None):
        """

        Parameters
        ----------
        runid : sortable
        start_args
        end_args
        scan_args

        Returns
        -------
        data : dict
            {data_name: []}
        """
        if start_args is None:
            start_args = {}
        if end_args is None:
            end_args = {}
        if scan_args is None:
            scan_args = {}

        # format the begin run event information
        beamline_id = scan_args.get('beamline_id', None)
        if beamline_id is None:
            beamline_id = os.uname()[1].split('-')[0]
        custom = scan_args.get('custom', None)
        beamline_config = scan_args.get('beamline_config', None)
        owner = scan_args.get('owner', None)
        if owner is None:
            owner = getpass.getuser()
        runid = str(runid)

        blc = mds.insert_beamline_config(beamline_config, time=time.time())
        # insert the run_start into metadatastore
        run_start = mds.insert_run_start(
            time=time.time(), beamline_id=beamline_id, owner=owner,
            beamline_config=blc, scan_id=runid, custom=custom)

        # stash bre for later use
        scan_args['run_start'] = run_start
        end_args['run_start'] = run_start

        keys = self._get_data_keys(**scan_args)
        data = {k: [] for k in keys}

        scan_args['data'] = data

        self._run_start(start_args)
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
            end_args['state'] = 'abort'
        finally:
            self._end_run(end_args)

        return data
