from __future__ import print_function
import numpy as np
from time import sleep, strftime
import six

from ..runengine import RunEngine
from ..session import get_session_manager

session_manager = get_session_manager()
logger = session_manager._logger

__all__ = ['AScan', 'DScan']

try:
    logbook = session_manager['olog_client']
except KeyError:
    logbook = None


def ensure_iterator(i):
    """Check if i is an iterator. If not return length-1 iterator"""
    if hasattr(i, "__iter__") or hasattr(i, "__getitem__"):
        return i
    else:
        return [i]


def objects_to_str(iterables, iter_sep=', ', iter_start='(',
                   iter_stop=')'):

    text = '['
    sep = ''

    # To see if we need start/stop chars then we see if we
    # have a length 1 iterator
    l = 0
    try:
        l = len(iterables)
    except TypeError:
        pass

    if l == 1:
        # For a length 1 iterator we dont set the start
        text = ''
    else:
        text = iter_start

    for i in iterables:
        # Is the object i iterable:
        try:
            iter(i)
        except TypeError:
            try:
                # Try to see if we have a name attribute
                text += '{}{}'.format(sep, i.name)
            except AttributeError:
                # Object does not have a name
                pass
            else:
                # We have a valid name, break the iteration
                break

            text += '{}{}'.format(sep, str(i))

        else:
            text += '{}{}'.format(sep, objects_to_str(i))

        # Now we have gone round once, set the separator
        sep = iter_sep

    if l != 1:
        text += iter_stop

    return text


def cmdline_to_str(*args, **kwargs):
    """Format a string based on the command line"""
    msg = objects_to_str(args)
    return msg


class SharedState(object):
    _shared_state = {}

    def __init__(self):
        self.__dict__ = self._shared_state


class Scan(SharedState):
    def __init__(self, *args, **kwargs):
        super(Scan, self).__init__(*args, **kwargs)

        self._default_detectors = []
        self._default_triggers = []
        self._run_eng = RunEngine(None)

        self._last_data = None

        self.triggers = None
        self.detectors = None
        self.settle_time = None

        self.paths = list()
        self.positioners = list()

        self._plotx = None
        self._ploty = None

    def check_paths(self):
        """Check the paths against any limits of positioners"""
        for pos, path in zip(self.positioners, self.paths):
            for p in path:
                if pos.check_value(p):
                    raise ValueError('Scan moves positioner {} \
                                     out of limits {},{}'.format(
                                     pos.name, p.low_limit, p.high_limit))

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
        Guess the positioners and detectors that the user cares about

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
            if self._ploty is not None:
                if name in self._ploty:
                    ploty.append(name)
        return plotx, ploty

    def run(self, **kwargs):
        """Run the scan"""
        self.scan_id = session_manager.get_next_scan_id()

        # Run this in a context manager to capture
        # the KeyboardInterrupt

        with self:
            self.check_paths()
            self.setup_detectors()
            self.setup_triggers()

            for pos, path in zip(self.positioners, self.paths):
                pos.set_trajectory(path)

            # Create the dict to pass to the run-engine

            scan_args = dict()
            scan_args['detectors'] = self.detectors
            scan_args['triggers'] = self.triggers
            scan_args['positioners'] = self.positioners
            scan_args['settle_time'] = self.settle_time
            scan_args['custom'] = {}
            # plotx, ploty = self.format_plot()
            # scan_args['custom']['plotx'] = plotx
            # if ploty:
            #     scan_args['custom']['ploty'] = ploty

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

    def __init__(self, *args, **kwargs):
        super(ScanND, self).__init__()
        self.dimension = None
        self.scan_command = None

    def pre_scan(self, *args, **kwargs):
        super(ScanND, self).pre_scan(*args, **kwargs)
        self.make_log_entry()

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

    def make_log_entry(self):
        """Format and make a log entry for the scan"""
        time_text = strftime("%a, %d %b %Y %H:%M:%S %Z")

        # Print header

        msg = 'Scan Command    : {}\n'.format(self.scan_command)
        msg += 'Scan ID         : {}\n'.format(self.scan_id)
        msg += 'Scan started at : {}\n'.format(time_text)
        msg += 'Scan Dimension  : {}\n'.format(self.dimension)
        msg += 'Scan Datapoints : {} ({})\n'.format(self.datapoints,
                                                    np.prod(self.datapoints))

        # Print positioners and start and stop values

        msg += '\n{:<30} {:<20} {:<20}:\n'.format('Positioners',
                                                  'Min', 'Max')
        for pos, path in zip(self.positioners, self.paths):
            msg += '{:<30} {:<20.8f} {:<20.8f}\n'.format(pos.name,
                                                         min(path),
                                                         max(path))

        msg += '\nTriggers:\n'
        for trig in self.triggers:
            msg += '{:<30}\n'.format(trig.name)

        msg += '\nDetectors:\n'
        for det in self.detectors:
            msg += '{:<30}\n'.format(det.name)

        msg += '\n{0:=^80}\n'.format('')

        for p in self.positioners + self.triggers + self.detectors:
            try:
                msg += 'PV:{}\n'.format(p.report['pv'])
            except KeyError:
                pass

        logbook.log(msg)

    def format_command_line(self, *args, **kwargs):
        """Return a string representation of the passed arguments"""
        cl_name = '{}()'.format(self.__class__.__name__)
        cl_args = cmdline_to_str(*args, **kwargs)
        return cl_name + cl_args

    def __call__(self, positioners, start, stop, npts, **kwargs):
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

        # Calculate number of points from intervals

        npts = np.asarray(npts) + 1

        start = ensure_iterator(start)
        stop = ensure_iterator(stop)

        args = (positioners, start, stop, npts)
        self.scan_command = self.format_command_line(*args, **kwargs)

        for b, e, d in zip(start, stop, range(dimension)):
            # For each dimension we work out the paths
            iter_pos = ensure_iterator(positioners[d])

            for p in iter_pos:
                pos.append(p)
                paths.append(self.calc_path(b, e, npts, d))

        self.positioners = pos
        self.paths = paths
        self.datapoints = npts
        self.dimension = dimension

        self.run(**kwargs)


class AScan(ScanND):
    pass


class DScan(AScan):
    def pre_scan(self):
        """Prescan store starting positions and change paths"""
        super(DScan, self).pre_scan()
        self._start_positions = [p.position for p in self.positioners]
        self.paths = [np.array(path) + start
                      for path, start in zip(self.paths, self._start_positions)]

    def post_scan(self):
        """Post Scan Move to start positions"""
        super(DScan, self).pre_scan()
        status = [pos.move(start, wait=False)
                  for pos, start in
                  zip(self.positioners, self._start_positions)]

        print("\nMoving positioners back to start positions.")
        while any(not stat.done for stat in status):
            sleep(0.01)

        print("Done.")
