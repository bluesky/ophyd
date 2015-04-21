from __future__ import print_function, division

import six

import logging
from warnings import warn
import getpass
import os
import datetime
import time
from collections import defaultdict
from threading import Thread, Timer
from Queue import Queue, Empty
import numpy as np
from ..session import register_object
from ..controls.detector import Detector
from metadatastore import api as mds
import traceback


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


class KillScanException(RuntimeError):
    """Exception that gets raised when a KillScanCondition is met

    Attributes
    ----------
    killers : list
        List of callables that told the RunEngine to kill itself
    """
    def __init__(self, killers):
        super(KillScanException, self).__init__("Scan killed: %s" % killers)


class RunEngine(object):
    """The run engine

    Attributes
    ----------
    logger : logging.Logger
    scan : ophyd.scan_api.Scan
        the ophyd.scan_api.Scan object that called the RunEngine
    pause : bool
        True: Pause the scan
        False: Do not pause the scan
    _pausers : set
        Set of callables that have paused the scan
    pause_time : int
        If ``self.pause``, wait ``pause_time`` before checking if ``self.pause``
        is True
    kill : bool
        True: kill the scan
    _killers : set
        Set of callables that have asked the scan to terminate
    """

    def __init__(self, logger, pause_time=.1):
        self._demuxer = Demuxer()
        self._sessionmgr = register_object(self)
        self._scan_state = False
        self.logger = self._sessionmgr._logger
        self.logger.setLevel(logging.DEBUG)

        # the currently executing scan thread
        self._scan_thread = None
        # the ophyd.scan_api.Scan object that called the RunEngine
        self.scan = None

        # boolean flag to pause the scan
        self._pause = False
        self._pausers = set()
        # if self._pause is True, check with `_pause_time` frequency until
        # it is False
        self.pause_time = pause_time  # ms
        # boolean flag to kill the scan
        self._kill = False
        self._killers = set()
        # lists of threading.Timer objects that set the _pause/_kill attrs
        self._pause_timers = []
        self._kill_timers = []

    # start/stop/pause/resume are external api methods
    def start(self):
        pass

    def stop(self):
        self._scan_state = False

    @property
    def running(self):
        return self._scan_state

    def kill(self, killing_callable):
        """Kill the scan

        Set the kill instance attribute to True so that the next time the flag
        is checked, the scan will raise a ``ScanKilledException`` and exit
        """
        self._killers.add(killing_callable)
        self._kill = True

    def pause(self, pausing_callable):
        """Pause the scan.

        Set the pause instance attribute to True so that the next time the flag
        is checked, the scan will wait until it is False
        """
        self.logger.info("Scan is being paused by: {}"
                         "".format(pausing_callable))
        self.logger.info("Scan is additionally waiting on {}"
                         "".format(self._pausers))
        self._pausers.add(pausing_callable)
        self._pause = True

    def resume(self, pausing_callable):
        """Resume the scan

        Set the pause instance attribute to False so that the next time the
        flag is checked, the scan will resume
        """
        # remove the pausing_callable from the list
        self._pausers.remove(pausing_callable)
        self.logger.info("Scan no longer paused by: %s" % pausing_callable)
        if self._pausers:
            self.logger.info("Scan is still waiting on %s" % self._pausers)
        else:
            self._pause = False

    def _run_start(self, arg):
        # run any registered user functions
        # save user data (if any), and run_header
        self.logger.info('Begin Run...')

    def _end_run(self, arg):
        # start up the pause scan conditions
        for pause_scan_condition in self.scan.pause_scan_conditions:
            pause_scan_condition.stop_checking()

        state = arg.get('state', 'success')
        bre = arg['run_start']
        reason = arg.pop('verbose_end_condition', '')
        rs = mds.insert_run_stop(bre, time.time(), exit_status=state,
                                 reason=reason)
        self.scan.emit_stop(rs)
        self.logger.info('End Run...')

    def _check_scan_status(self):
        """Helper function to check kill/pause statuses

        """
        # check for a kill signal first
        def kill():
            if self._kill:
                raise KillScanException(self._killers)
        kill()
        # keep checking until the scan is unpaused
        while self._pause:
            self.logger.info("in _check_scan_status waiting for self._pause to "
                             "be False. It's value is currently %s" %
                             self._pause)
            kill()
            time.sleep(self.pause_time)

    def _move_positioners(self, positioners=None, settle_time=None):
        self.logger.info('pre-move')
        self._check_scan_status()
        self.scan.cb_registry.process('pre-move',  self)
        try:
            status = [pos.move_next(wait=False)[1] for pos in positioners]
        except StopIteration:
            return None

        # status now holds the MoveStatus() instances
        time.sleep(0.05)
        # TODO: this should iterate at most N times to catch hangups
        while not all(s.done for s in status):
            self.logger.info('during move')
            time.sleep(0.1)

        if settle_time is not None:
            time.sleep(settle_time)

        # use metadatastore to format the events so that ophyd is insulated
        # from metadatastore spec changes
        self._check_scan_status()
        self.logger.info('post-move')
        self.scan.cb_registry.process('post-move',  self)
        return {
            pos.name: {
                'timestamp': pos.timestamp[pos.pvname.index(pos.report['pv'])],
                'value': pos.position}
            for pos in positioners}

    def _start_scan(self, run_start=None, detectors=None,
                    data=None, positioners=None, settle_time=None,
                    **kw):
        dets = detectors
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
            self.logger.debug('self._scan_state is still True in self._start_scan')
            posvals = self._move_positioners(positioners, settle_time)
            self.logger.debug('moved positioners')
            # if we're done iterating over positions, get outta Dodge
            if posvals is None:
                self.logger.debug('posvals is None. Breaking out.')
                break

            # Trigger detector acquisision
            self._check_scan_status()
            self.logger.info('processing pre-trigger callbacks')
            self.scan.cb_registry.process('pre-trigger',  self)
            self.logger.debug('gathering acquire status')
            acq_status = [trig.acquire() for trig in triggers]

            while any([not stat.done for stat in acq_status]):
                self.logger.info('waiting for acquisition to be finished')
                time.sleep(0.05)
            self.logger.info('acquisition finished')
            self._check_scan_status()
            self.logger.debug('processing post-trigger callbacks')
            self.scan.cb_registry.process('post-trigger',  self)
            # Read detector values
            tmp_detvals = {}
            self.logger.debug('gathering detector values')
            for det in dets + positioners:
                read_val = det.read()
                self.logger.debug('updating temp vals: {}'.format(read_val))
                tmp_detvals.update(read_val)


            self.logger.debug('formatting event for mds')
            detvals = mds.format_events(tmp_detvals)

            self.logger.debug('passing data onto Demuxer for distribution')
            self.logger.info(self._demunge_values(detvals, names))
            # grab the current time as a timestamp that describes when the
            # event data was bundled together
            self.logger.debug('grabbing bundle time')
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
                    positioners=positioners,
                    detectors=dets, data=detvals)

                event_descriptor = mds.insert_event_descriptor(
                    run_start=run_start, time=evdesc_creation_time,
                    data_keys=mds.format_data_keys(data_key_info))
                self.logger.debug(
                    'event_descriptor: %s', vars(event_descriptor))
                self.scan.emit_descriptor(event_descriptor)
                # insert the event again. this time it better damn well work
                self.logger.debug(
                    'inserting event %d------------------', seq_num)
                event = mds.insert_event(event_descriptor=event_descriptor,
                                         time=bundle_time, data=detvals,
                                         seq_num=seq_num)
            self.logger.debug('event %d--------', seq_num)
            self.logger.debug('%s', vars(event))

            self.scan.emit_event(event)

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

    def start_run(self, scan, start_args=None, end_args=None, scan_args=None):
        """

        Parameters
        ----------
        scan : Scan instance
        start_args
        end_args
        scan_args

        Returns
        -------
        data : dict
            {data_name: []}
        """
        # stash the current scan
        self.scan = scan
        runid = self.scan.scan_id
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
        self.scan.emit_start(run_start)
        pretty_time = datetime.datetime.fromtimestamp(
            recorded_time).isoformat()
        self.logger.info("Scan ID: %s", runid)
        self.logger.info("Time: %s", pretty_time)
        self.logger.info("uid: %s", str(run_start.uid))

        # stash bre for later use
        scan_args['run_start'] = run_start
        end_args['run_start'] = run_start

        keys = self._get_data_keys(
            positioners=scan_args.get('positioners', None),
            detectors=scan_args.get('detectors', None))
        data = defaultdict(list)

        scan_args['data'] = data
        scan_args['scan'] = scan  # used for callbacks

        self._run_start(start_args)
        self._scan_thread = Thread(target=self._start_scan,
                                   name='Scanner',
                                   kwargs=scan_args)
        self._scan_thread.daemon = True
        self._scan_state = True
        self._scan_thread.start()
        end_args['scan'] = scan
        # start up the pause scan conditions
        for pause_scan_condition in scan.pause_scan_conditions:
            pause_scan_condition(self)
        try:
            while self._scan_state is True:
                self.logger.debug('scan state is still true')
                if np.random.random() < 0.05:
                    self._pause = True
                    self.logger.warning("Pausing run engine")
                elif self._pause:
                    self._pause = False
                    self.logger.warning("Releasing pause on run engine")
                try:
                    while True:
                        self.logger.debug('trying to get something from the '
                                          'scan.desc_queue')
                        descriptor = self.scan.desc_queue.get(timeout=0.05)
                        self.logger.debug('processing the event-descriptor signal')
                        self.scan.cb_registry.process('event-descriptor',
                                                      descriptor)
                except Empty as e:
                    pass
                try:
                    while True:
                        self.logger.debug('trying to get something from the '
                                          'scan.ev_queue')
                        event = self.scan.ev_queue.get(timeout=0.05)
                        self.logger.debug('processing the event signal')
                        self.scan.cb_registry.process('event', event)
                except Empty:
                    pass
                self.logger.debug('sleeping for 1 second')
                time.sleep(1)
        except (KeyboardInterrupt, KillScanException):
            self._scan_state = False
            self._scan_thread.join()
            end_args['state'] = 'abort'
            end_args['verbose_end_condition'] = traceback.format_exc()
        finally:
            self._end_run(end_args)
        # clear the stashed scan
        self.scan = None

        return data
