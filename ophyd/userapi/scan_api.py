from __future__ import print_function
import numpy as np
from time import sleep, strftime
import six
from ..runengine import RunEngine
from ..controls import EpicsMotor, PVPositioner
from ..session import get_session_manager

session_manager = get_session_manager()
logger = get_session_manager()._logger

__all__ = ['AScan', 'DScan']


def ensure_iterator(i):
    """Check if i is an iterator. If not return length-1 iterator"""
    if hasattr(i, "__iter__") or hasattr(i, "__getitem__"):
        return i
    else:
        return [i]


class Scan(object):

    def __init__(self):
        self._run_eng = RunEngine(None)
        self._last_data = None

        self.triggers = None
        self.detectors = None
        self._default_detectors = list()
        self._default_triggers = list()
        self.settle_time = None

        self.paths = list()
        self.positioners = list()

        self._plotx = None
        self._ploty = None

    def check_paths(self):
        pass

    def __enter__(self):
        self.pre_scan()

    def __exit__(self, exec_type, exec_value, traceback):
        logger.debug("Scan context manager exited with %s", str(exec_value))
        self.post_scan()

    def pre_scan(self):
        pass

    def post_scan(self):
        pass

    def setup_detectors(self):
        pass

    def setup_triggers(self):
        pass

    def format_plot(self):
        '''
        Format the bits of information the user (most likely)
        cares about

        Returns
        -------
        plotx : str
            The default positioners to set as the x axis
        ploty : list
            The list of positioners/detectors to plot on the y axis
        '''
        pos_names = [pos.name for pos in self.positioners]
        det_names = [det.name for det in self.detectors]
        valid_names = pos_names + det_names
        # default value for the x axis
        plotx = self.positioners[0].name
        # if plotx is not a valid string, ignore it. if it is, make
        # sure that it is in the positioners/detectors that the
        # scan knows about
        if isinstance(self._plotx, six.string_types):
            if self._plotx:
                for name in valid_names:
                    if name in self._plotx:
                        plotx = name

        ploty = []
        # checking validity of self._ploty
        for name in valid_names:
            if name in self._ploty:
                ploty.append(name)
        return plotx, ploty

    def run(self):
        """Run the scan"""
        self.scan_id = session_manager.get_next_scan_id()

        with self:
            self.check_paths()
            self.setup_detectors()
            self.setup_triggers()

            for pos, path in zip(self.positioners, self.paths):
                pos.set_trajectory(path)

            scan_args = dict()
            scan_args['detectors'] = self.detectors
            scan_args['triggers'] = self.triggers
            scan_args['positioners'] = self.positioners
            scan_args['settle_time'] = self.settle_time
            scan_args['custom'] = {}
            plotx, ploty = self.format_plot()
            scan_args['custom']['plotx'] = plotx
            if ploty:
                scan_args['custom']['ploty'] = ploty
            # Run the scan!
            self.data = self._run_eng.start_run(self.scan_id,
                                                scan_args=scan_args)

    @property
    def data(self):
        """Return the last scanned data set"""
        return self._last_data

    @data.setter
    def data(self, data):
        self._last_data = data

    @property
    def triggers(self):
        """Return the default triggers for this scan"""
        if self._triggers is None:
            return self._default_triggers
        else:
            return self._triggers + self.default_triggers

    @triggers.setter
    def triggers(self, triggers):
        """Set the default triggers for this scan"""
        self._triggers = triggers

    @property
    def detectors(self):
        """Return the default detectors for this scan"""
        if self._detectors is None:
            return self._default_detectors
        else:
            return self._detectors + self._default_detectors

    @detectors.setter
    def detectors(self, detectors):
        """Set the default detectors for this scan"""
        self._detectors = detectors

    @property
    def default_detectors(self):
        """Get the defualt detectors"""
        return self._default_detectors

    @default_detectors.setter
    def default_detectors(self, det):
        """Set the default detectors"""
        self._default_detectors = det

    @property
    def default_triggers(self):
        """Get the defualt triggers"""
        return self._default_triggers

    @default_triggers.setter
    def default_triggers(self, trig):
        """Set the default triggers"""
        self._default_triggers = trig

    @property
    def positioners(self):
        """Get the posiitoners for the scan"""
        return self._positioners

    @positioners.setter
    def positioners(self, positioners):
        """Set the positioners for the scan"""
        self._positioners = positioners

    @property
    def paths(self):
        """Get the paths for the scan"""
        return self._paths

    @paths.setter
    def paths(self, paths):
        """Set the paths for the scan"""
        self._paths = paths

    @property
    def ploty(self):
        return self._ploty

    @ploty.setter
    def ploty(self, ploty):
        '''

        Parameters
        ----------
        ploty : str
            The name of the data set that is understood to be the
            important y data for the scan
        '''
        self._ploty = ploty


class ScanND(Scan):

    """Class for a N-Dimensional Scan"""

    def __init__(self):
        Scan.__init__(self)
        self.dimension = None

    def calc_linear_path(self, start, stop, npts):
        """Return a linearaly spaced path"""
        return np.linspace(start, stop, npts)

    def calc_path(self, start, stop, npts, dim):
        """Calculate a single path given start, stop and npts for dim"""
        N = np.asarray(npts)
        a = self.calc_linear_path(start, stop, npts[dim])
        x = N[::-1][:len(N)-dim-1]
        y = N[:dim]
        a = np.repeat(a, x.prod())
        a = np.tile(a, y.prod())
        return a

    def __call__(self, positioners, start, stop, npts):
        """Run Scan"""

        # This is an n-dimensional scan. We take the dims from
        # the length of npts.

        npts = ensure_iterator(npts)
        positioners = ensure_iterator(positioners)
        start = ensure_iterator(start)
        stop = ensure_iterator(stop)

        dimension = len(npts)
        pos = list()
        paths = list()

        npts = np.asarray(npts) + 1

        start = ensure_iterator(start)
        stop = ensure_iterator(stop)

        for b, e, d in zip(start, stop, range(dimension)):
            # For each dimension we work out the paths
            iter_pos = ensure_iterator(positioners[d])

            for p in iter_pos:
                pos.append(p)
                paths.append(self.calc_path(b, e, npts, d))

        self.positioners = pos
        self.paths = paths

        self.run()


class AScan(ScanND):

    def pre_scan(self):
        pass
        ScanND.pre_scan(self)

        time_text = strftime("%a, %d %b %Y %H:%M:%S %Z")

        msg = ''
        msg += 'Scan ID         : {}\n'.format(self.scan_id)
        msg += 'Scan started at : {}\n\n'.format(time_text)
        msg += '===\n'
        for p in self.positioners + self.triggers + self.detectors:
            try:
                msg += 'PV:{}\n'.format(p.report['pv'])
            except KeyError:
                pass

        logger.info(msg)


class DScan(AScan):

    def __init__(self):
        AScan.__init__(self)

    def pre_scan(self):
        """Prescan Compute Paths"""
        self._start_positions = [p.position for p in self.positioners]
        self.paths = [np.array(path) + start
                      for path, start in zip(self.paths, self._start_positions)]
        AScan.pre_scan(self)

    def post_scan(self):
        """Post Scan Move to start positions"""
        AScan.post_scan(self)

        status = [pos.move(start, wait=False)
                  for pos, start in zip(self.positioners, self._start_positions)]

        print("\nMoving positioners back to start positions.")
        while any(not stat.done for stat in status):
            sleep(0.01)

        print("Done.")
