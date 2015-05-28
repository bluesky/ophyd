from __future__ import print_function
import logging
from warnings import warn
import getpass
import os
import uuid
import datetime
import time
from collections import defaultdict
from threading import Thread
from Queue import Queue, Empty
import numpy as np
from ..session import register_object
from ..controls.detector import Detector
import matplotlib.pyplot as plt


def _get_info(positioners=None, detectors=None, data=None):
    """Helper function to extract information from the positioners/detectors
    and assemble it according to our document specification.

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

    def _end_run(self, scan, run_start_uid, exit_status):
        doc = dict(run_start=run_start_uid, time=time.time(),
                   exit_status=exit_status)
        scan.emit_stop(doc)
        self.logger.info('End of Run.')

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

        return {
            pos.name: (pos.timestamp[pos.pvname.index(pos.report['pv'])],
                       pos.position)
            for pos in positioners}

    def _start_scan(self, scan, run_start_uid, detectors=None,
                    data=None, positioners=None):

        dets = detectors
        triggers = [det for det in dets if isinstance(det, Detector)]

        # provide header for formatted list of positioners and detectors in
        # INFO channel
        names = list()
        for pos in positioners + dets:
            names.extend(pos.describe().keys())

        self.logger.info(self._demunge_names(names))
        seq_num = 0
        event_descriptor = None  # created once the first Event is created
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

            if event_descriptor is None:
                # Build and emit a descriptor.
                evdesc_creation_time = time.time()
                data_key_info = _get_info(
                    positioners=positioners,
                    detectors=dets, data=detvals)
                evdesc_uid = uuid.uuid4()
                doc = dict(run_start=run_start_uid, time=evdesc_creation_time,
                           data_keys=data_key_info, uid=evdesc_uid)
                scan.emit_descriptor(doc)
                self.logger.debug('Emitted Event Descriptor:\n%s', vars(doc))
            # Build and emit and Event.
            bundle_time = time.time()
            ev_uid = uuid.uuid4()
            doc = dict(event_descriptor=evdesc_uid,
                       time=bundle_time, data=detvals, seq_num=seq_num,
                       uid=ev_uid)
            self.emit_event(doc)
            self.logger.debug('Emitted Event %d:\n%s' % (seq_num, vars(doc)))

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

    def _get_data_keys(self, positioners=None, detectors=None):
        if positioners is None:
            positioners = []
        if detectors is None:
            detectors = []
        # ATM, these are both lists
        names = [o.name for o in positioners]
        for det in detectors:
            names.extend(det.describe().keys())

        return names

    def start_run(self, scan, **kwargs):
        """

        Parameters
        ----------
        scan : Scan instance

        Returns
        -------
        data : dict
            {data_name: []}
        """
        runid = scan.scan_id

        # format the begin run event information
        beamline_id = kwargs.get('beamline_id', None)
        if beamline_id is None:
            beamline_id = os.uname()[1].split('-')[0]
        custom = kwargs.get('custom', {})
        owner = kwargs.get('owner', None)
        if owner is None:
            owner = getpass.getuser()
        scan_id= str(runid)

        recorded_time = time.time()
        run_start_uid = str(uuid.uuid4())
        doc = dict(uid=run_start_uid,
                   time=recorded_time, beamline_id=beamline_id, owner=owner,
                   scan_id=scan_id, **custom)
        scan.emit_start(doc)
        pretty_time = datetime.datetime.fromtimestamp(
                                          recorded_time).isoformat()
        self.logger.info("Scan ID: %s", runid)
        self.logger.info("Time: %s", pretty_time)
        self.logger.info("uid: %s", str(run_start_uid))

        keys = self._get_data_keys(**kwargs)
        data = defaultdict(list)
        kwargs['data'] = data

        self.logger.info('Beginning Run...')
        self._scan_thread = Thread(target=self._start_scan,
                                   name='Scanner',
                                   args=(scan, run_start_uid),
                                   kwargs=kwargs)
        self._scan_thread.daemon = True
        self._scan_state = True
        self._scan_thread.start()
        try:
            while self._scan_state is True:
                scan.dispatcher.process_descriptor_queue()
                scan.dispatcher.process_event_queue()
        except KeyboardInterrupt:
            self._scan_state = False
            self._scan_thread.join()
            exit_status = 'abort'
        except Exception as err:
            exit_status = 'fail'
            raise err
        finally:
            self._end_run(scan, run_start_uid, exit_status)

        return data
