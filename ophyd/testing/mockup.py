import time as ttime
import numpy as np
from threading import Thread, Timer, Event
from multiprocessing import Process
import logging


logging.basicConfig(level=logging.INFO,
                    format='[%(levelname)-7s] (%(threadName)-26s) %(message)s')


"""Multi-threaded mock-up of the Ophyd RunEngine
"""


class MockPositioner(object):
    """

    Attributes
    ----------
    start : float
    stop : float
    step : float
    pos : float
        Current motor position
    name : str
        Name of the positioner. Used primarily for logging messages
    move_event : threading.Event
        when ``set()``, will kick off the ``move_thread`` to move to the next
        position. After the desired position has been reached, ``move_event``
        will be cleared so the positioner can be told to move again
    position_reached_event : threading.Event
        when ``set()``, will un-block the RunEngine thread
    kill : bool
        True: Stop the mock positioner
    kill_event : threading.Event
        when ``set()`` will cause the thread targeting ``run()`` to return
        False when ``Thread.is_alive()`` is called
    """
    def __init__(self, name, move_time=0.5, start=0, stop=3, step=.2):
        super(MockPositioner, self).__init__()
        self._move_time = move_time
        self._start = None
        self._stop = None
        self._step = None
        self._trajectory = None
        self._pos = None
        self.start = start
        self.stop = stop
        self.step = step
        self._name = name
        self.move_event = Event()
        self.position_reached_event = Event()
        self.kill = False
        self.kill_event = Event()

    # yay boilerplate
    @property
    def start(self):
        return self._start

    @property
    def stop(self):
        return self._stop

    @property
    def step(self):
        return self._step

    @start.setter
    def start(self, start):
        self._start = start
        self.reset()

    @stop.setter
    def stop(self, stop):
        self._stop = stop
        self.reset()

    @step.setter
    def step(self, step):
        self._step = step
        self.reset()

    def reset(self):
        if (self._start is not None and self._stop is not None and
                self._step is not None):
            # force it to be a generator
            self._trajectory = iter(np.arange(self._start, self._stop,
                                              self._step))

    def move(self):
        logging.debug('Move started')
        ttime.sleep(self._move_time)
        self._pos = self._trajectory.next()
        logging.info('Move to %s complete.' % self._pos)

    @property
    def pos(self):
        return self._pos

    def run(self):
        while True:
            # wait for the trigger event
            should_move = self.move_event.wait(timeout=1)
            logging.debug('checking self.kill')
            if self.kill:
                self.kill = False
                break
            logging.debug('checking self.kill not set')
            if should_move:
                # wait for the move_event to be triggered
                logging.debug('Move event triggered.' % self._name)
                try:
                    self.move()
                except StopIteration:
                    break
                finally:
                    # clear the move event after the positioner has moved
                    self.move_event.clear()
                    # notify scan engine that the position has been reached
                    self.position_reached_event.set()
        # emit the kill event
        self.kill_event.set()

    @property
    def name(self):
        return self._name


class GaussianMockDetector(object):
    """

    Attributes
    ----------
    x0 : float
    sigma : float
    read : float
        Return the most recently acquired detector image
    name : str
        Name of the detector. Used primarily for logging messages
    acquire_time : float
        Time it takes for the detector to acquire an image
    trigger_event : threading.Event
        when ``set()``, will kick off the ``trigger_thread`` to acqure an image
        for ``acquire_time``. After the acquisition has completed,
        ``trigger_event`` will be cleared so that the detector can be told to
        acquire again
    acquiring_complete_event : threading.Event
        when ``set()``, will un-block the RunEngine thread
    kill_event : threading.Event
        when ``set()`` will cause the thread targeting ``run()`` to return
        False when ``Thread.is_alive()`` is called
    """

    def __init__(self, positioner, name, x0=1.5, sigma=.5, acquire_time=0.25):
        self._x0 = x0
        self._sigma = sigma
        self._positioner = positioner
        self._name = name
        self._value = -1
        self._acquire_time = acquire_time
        self.trigger_event = Event()
        self.acquiring_complete_event = Event()
        self.kill = False
        self.kill_event = Event()

    def _gaussian(self, x):
        logging.debug('computing gaussian with parameters x={}, x0={}, sigma={}'
                      ''.format(x, self._x0, self._sigma))
        return np.exp(-((x-self._x0)**2/(2*self._sigma)**2))

    def _acquire(self):
        logging.debug("Acquiring image")
        ttime.sleep(self._acquire_time)
        self._value = self._gaussian(self._positioner.pos)
        logging.info("Image acquired. val=%s" % self._value)

    @property
    def read(self):
        return self._value

    def run(self):
        while True:
            # wait for the trigger event
            acquire = self.trigger_event.wait(timeout=1)
            logging.debug('checking self.kill')
            if self.kill:
                self.kill = False
                break
            logging.debug('checking self.kill not set')
            if acquire:
                # obtain an image!
                self._acquire()
                # clear the trigger event after it has been triggered
                self.trigger_event.clear()
                # notify the scan engine that the acquisition is complete
                self.acquiring_complete_event.set()
        # let the run engine know the detector thread is dead
        self.kill_event.set()

    @property
    def name(self):
        return self._name


class MockScanEngine(object):

    def __init__(self, positioners, detectors, name):
        self._positioners = positioners
        self._detectors = detectors
        self._name = name
        self._scan_running = False
        # all the events
        self.start_scan_event = Event()
        self.end_scan_event = Event()
        self.pause_scan_event = Event()
        self.resume_scan_event = Event()
        self.kill_scan_event = Event()
        self.kill_runengine_event = Event()

        self._execution_thread = Thread(
            target=self.run, args=[], name="MockScanEngine-%s" % name)
        self._execution_thread.start()

    def _create_positioner_threads(self):
        positioner_threads = [Thread(target=pos.run, args=(),
                                     name='MockPositioner-%s' % pos.name)
                              for pos in self._positioners]
        for pos_thread in positioner_threads:
            pos_thread.daemon = True
            logging.debug("Starting thread %s" % pos_thread.name)
            pos_thread.start()
        return positioner_threads

    def _create_detector_threads(self):
        detector_threads = [Thread(target=det.run, args=(),
                                   name='GaussianMockDetector-%s' %
                                        det.name)
                            for det in self._detectors]
        for det_thread in detector_threads:
            det_thread.daemon = True
            logging.debug("Starting thread %s" % det_thread.name)
            det_thread.start()

        return detector_threads

    def run(self):
        positioner_threads = []
        detector_threads = []
        while True:
            logging.info("Waiting for start_scan signal")
            self._scan_running = self.start_scan_event.wait(timeout=1)
            self.start_scan_event.clear()
            logging.info("Start_scan signal received")
            # create and start the positioner daemon threads
            logging.debug('Creating positioner threads')
            positioner_threads = self._create_positioner_threads()
            # create and start the detector daemon threads
            logging.debug('Creating detector threads')
            detector_threads = self._create_detector_threads()

            keep_running = True
            while keep_running:
                # move positioners
                for pos in self._positioners:
                    pos.move_event.set()

                for pos in self._positioners:
                    # wait for the position to be reached
                    pos.position_reached_event.wait()
                    # reset the event so it can be used on the next loop
                    pos.position_reached_event.clear()

                # make sure at least one positioner is still alive
                keep_running = False
                for pos in positioner_threads:
                    logging.debug('Checking if all positioners are done.')
                    keep_running = keep_running or pos.is_alive()

                logging.debug('keep_running = %s' % keep_running)

                if not keep_running:
                    logging.info("All positioners are done. "
                                 "Terminating Scan.")
                    for det in self._detectors:
                        det.kill = True
                    for det, det_thread in zip(self._detectors,
                                               detector_threads):
                        if det_thread.is_alive():
                            logging.debug('Waiting for %s to end' %
                                          det_thread.name)
                            det.kill_event.wait()
                    continue

                # trigger detectors
                for det in self._detectors:
                    det.trigger_event.set()

                for det in self._detectors:
                    # wait for the acquisition to be complete
                    det.acquiring_complete_event.wait()
                    # reset the event so it can be used on the next loop
                    det.acquiring_complete_event.clear()

            self.end_scan_event.set()

            logging.info("Scan complete. RunEngine waiting for the next "
                         "start_scan_event")


class MockScan(object):
    def __init__(self):
        super(MockScan, self).__init__()

    def __call__(self, detector, start, stop, step):
        detector.start = start
        detector.stop = stop
        detector.step = step


if __name__ == "__main__":
    pos = MockPositioner('pos', stop=.5)
    det = GaussianMockDetector(pos, 'det1')
    positioners = [pos]
    detectors = [det]
    scan_engine = MockScanEngine(positioners, detectors, 'scan_engine')
    for i in range(3):
        logging.info('Starting scan in 1 second')
        ttime.sleep(1)
        logging.info('Scan starting')
        scan_engine.start_scan_event.set()
        logging.info('Waiting for scan to finish...')
        scan_engine.end_scan_event.wait()
        scan_engine.end_scan_event.clear()
        logging.info('Previous scan done. Starting another one.')
        for pos in positioners:
            pos.reset()

    # kill the run engine
