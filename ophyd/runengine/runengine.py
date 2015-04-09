from __future__ import print_function
import logging
import getpass
import os
import datetime
import time
from collections import defaultdict
from threading import Thread
from Queue import Queue
import numpy as np
from ..session import register_object
from ..controls.detector import Detector
from metadatastore import api as mds


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
    desc = {}
    [desc.update(x.describe()) for x in (detectors + positioners)]

    info_dict = {}
    for name, value in data.iteritems():
        """Internal function to grab info from a detector
        """
        # grab 'value' from [value, timestamp]
        val = np.asarray(value[0])

        dtype = 'number'
        try:
            shape = val.shape
        except AttributeError:
            # val is probably a float...
            shape = None

        if shape:
            dtype = 'array'

        d = {'dtype': dtype, 'shape': shape}
        d.update(desc[name])
        d = {name: d}
        info_dict.update(d)

    return info_dict


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

            # self.logger.debug('Demuxer: %s', inp)

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
        self._sessionmgr = register_object(self)
        self._scan_state = False
        self.logger = self._sessionmgr._logger

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
        self.logger.info('Begin Run...')

    def _end_run(self, arg):
        state = arg.get('state', 'success')
        bre = arg['run_start']
        mds.insert_run_stop(bre, time.time(), exit_status=state)
        self.logger.info('End Run...')

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

        # use metadatastore to format the events so that ophyd is insulated
        # from metadatastore spec changes
        return {
            pos.name: {
                'timestamp': pos.timestamp[pos.pvname.index(pos.report['pv'])],
                'value': pos.position}
            for pos in positioners}

    def _start_scan(self, **kwargs):
        run_start = kwargs.get('run_start')
        dets = kwargs.get('detectors')
        data = kwargs.get('data')
        positioners = kwargs.get('positioners')
        triggers = [det for det in dets if isinstance(det, Detector)]

        # creation of the event descriptor should be delayed until the first
        # event comes in. Set it to None for now
        event_descriptor = None

        # provide header for formatted list of positioners and detectors in
        # INFO channel
        names = list()
        for pos in positioners + dets:
            names.extend(pos.describe().keys())

        self.logger.info(self._demunge_names(names))
        seq_num = 0
        while self._scan_state is True:
            self.logger.debug(
                'self._scan_state is True in self._start_scan')
            posvals = self._move_positioners(**kwargs)
            self.logger.debug('moved positioners')
            # if we're done iterating over positions, get outta Dodge
            if posvals is None:
                break

            # Trigger detector acquisision
            acq_status = [trig.acquire() for trig in triggers]

            while any([not stat.done for stat in acq_status]):
                time.sleep(0.05)

            time.sleep(0.05)
            # Read detector values
            tmp_detvals = {}
            for det in dets + positioners:
                tmp_detvals.update(det.read())

            detvals = mds.format_events(tmp_detvals)

            # pass data onto Demuxer for distribution
            self.logger.info(self._demunge_values(detvals, names))
            # grab the current time as a timestamp that describes when the
            # event data was bundled together
            bundle_time = time.time()
            # actually insert the event into metadataStore
            try:
                self.logger.debug(
                    'inserting event %d------------------', seq_num)
                event = mds.insert_event(event_descriptor=event_descriptor,
                                         time=bundle_time, data=detvals,
                                         seq_num=seq_num)
            except mds.EventDescriptorIsNoneError:
                # the time when the event descriptor was created
                self.logger.debug(
                    'event_descriptor has not been created. '
                    'creating it now...')
                evdesc_creation_time = time.time()
                data_key_info = _get_info(
                    positioners=kwargs.get('positioners'),
                    detectors=dets, data=detvals)

                event_descriptor = mds.insert_event_descriptor(
                    run_start=run_start, time=evdesc_creation_time,
                    data_keys=mds.format_data_keys(data_key_info))
                self.logger.debug(
                    'event_descriptor: %s', vars(event_descriptor))
                # insert the event again. this time it better damn well work
                self.logger.debug(
                    'inserting event %d------------------', seq_num)
                event = mds.insert_event(event_descriptor=event_descriptor,
                                         time=bundle_time, data=detvals,
                                         seq_num=seq_num)
            self.logger.debug('event %d--------', seq_num)
            self.logger.debug('%s', vars(event))

            seq_num += 1
            # update the 'data' object from detvals dict
            for k, v in detvals.items():
                data[k].append(v)

            if not positioners:
                break

        self._scan_state = False
        return

    def _demunge_values(self, vals, keys):
        '''Helper function to format scan values

        Parameters
        ----------
        vals :  dict
        '''
        msg = ''.join('{}\t'.format(vals[name][0]) for name in keys)
        return msg

    def _demunge_names(self, names):
        '''Helper function to format scan device names

        Parameters
        ----------
        names : list of device names
        '''
        unique_names = [name for i, name in enumerate(names) if name not in
                        names[:i]]
        msg = ''.join('{}\t'.format(name) for name in unique_names)
        return msg

    def _get_data_keys(self, **kwargs):
        # ATM, these are both lists
        names = [o.name for o in kwargs.get('positioners')]
        for det in kwargs.get('detectors'):
            names += det.describe().keys()

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
        recorded_time = time.time()
        run_start = mds.insert_run_start(
            time=recorded_time, beamline_id=beamline_id, owner=owner,
            beamline_config=blc, scan_id=runid, custom=custom)
        pretty_time = datetime.datetime.fromtimestamp(
                                          recorded_time).isoformat()
        self.logger.info("Scan ID: %s", runid)
        self.logger.info("Time: %s",  pretty_time)
        self.logger.info("uid: %s", str(run_start.uid))

        # stash bre for later use
        scan_args['run_start'] = run_start
        end_args['run_start'] = run_start

        keys = self._get_data_keys(**scan_args)
        data = defaultdict(list)

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
