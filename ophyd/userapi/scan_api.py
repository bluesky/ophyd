from __future__ import print_function
import numpy as np
from time import sleep
import six
import sys
import collections
import itertools
import string
import traceback

from IPython.utils.coloransi import TermColors as tc

from ..runengine import RunEngine
from ..session import get_session_manager
from ..utils import LimitError

session_manager = get_session_manager()
logger = session_manager._logger

__all__ = ['AScan', 'DScan', 'Scan', 'Data', 'Count']


def estimate(x, y):
    """Return a dictionary of the vital stats of a 'peak'"""
    stats = dict()
    # Center of peak
    stats['ymin'] = y.min()
    stats['ymax'] = y.max()
    stats['avg_y'] = np.average(y)
    stats['x_at_ymin'] = x[y.argmin()]
    stats['x_at_ymax'] = x[y.argmax()]
    # Calculate CEN from derivative
    zero_cross = np.where(np.diff(np.sign(y - (stats['ymax']
                                               + stats['ymin'])/2)))[0]
    if zero_cross.size == 2:
        stats['cen'] = (x[zero_cross].sum() / 2,
                        (stats['ymax'] + stats['ymin'])/2)
    elif zero_cross.size == 1:
        stats['cen'] = x[zero_cross[0]]
    if zero_cross.size == 2:
        fwhm = x[zero_cross]
        stats['width'] = fwhm[1] - fwhm[0]
        stats['fwhm_left'] = (fwhm[0], y[zero_cross[0]])
        stats['fwhm_right'] = (fwhm[1], y[zero_cross[1]])

    # Center of mass
    stats['center_of_mass'] = (x * y).sum() / y.sum()
    return stats


class OphydList(list):
    """Subclass of List for Ophyd Objects to allow easy removal"""
    def pop(self, obj):
        pass


class Data(object):
    """Class for containing scan data

    This is a small object for containing data from a scan as objects. The
    data can be set on initialization or using the :py:meth:`data_dict`
    proprty. Data which has a length greater than 1 is stored as numpy
    arrays.

    Parameters
    ----------
    data : dict
        Dictionary of data from scan
    """

    def __init__(self, data=None):
        """Initialize class with data

        """
        if data is not None:
            self.data_dict = data

    def _estimate(self, xname, yname):
        """Estimate peak parameters"""
        self._estimate_dict = estimate(self.data_dict[xname],
                                       self.data_dict[yname])

    def estimate(self, xname, yname):
        self._estimate(xname, yname)
        return self._estimate_dict

    def cen(self, xname, yname):
        """Calculate the center from FWHM"""
        self._estimate(xname, yname)
        return self._estimate_dict['cen']

    @property
    def data_dict(self):
        """Dictionary of data objects"""
        return self._data_dict

    @data_dict.setter
    def data_dict(self, data):
        """Set the data dictionary"""
        keys = data.keys()
        values = [np.array(a) for a in data.values()]
        keys = [''.join([ch if ch in (string.ascii_letters + string.digits)
                        else '_'
                        for ch in key]) for key in keys]
        self._data_dict = {key: value for key, value in zip(keys, values)}
        for key, value in zip(keys, values):
            setattr(self, key, value)


class Scan(object):
    """Class for configuring and running a scan

    This class performs setup and calls the Ophyd RunEngine to start a scan
    (run). It cah be inhereted to overload the configuration or add additional
    steps in the scan. When the scan is run using the :py:meth:`run` method the
    class enters a context manager (itsself) which runs :py:meth:`pre_scan` on
    entry, and runs :py:meth:`post_scan` on exit. Because of the use of the
    context manager, :py:meth:'post_scan' will run even if an exception is
    thrown in the :py:class:`RunEngine`. Within the context manager the
    following steps are taken:

    * :py:meth:`check_paths`
    * :py:meth:`setup_detectors`
    * :py:meth:`setup_triggers`

    After configuring the detectors and triggers the trajectory is loaded
    into the positioners using the :py:meth:`set_trajectory` method.
    Finally the :py:class:`RunEngine` is initialised from the scans config
    and executed using the :py:meth:`start_run()` method.

    The data which is collected in the run, returned by the run-engine is
    appended to a ringbuffer and can be accessed through the :py:meth:`data`
    method.

    Attributes
    ----------
    TODO
    """
    _shared_config = {'default_triggers': [],
                      'default_detectors': [],
                      'user_detectors': [],
                      'user_triggers': [],
                      'scan_data': None, }

    def __init__(self, *args, **kwargs):
        super(Scan, self).__init__(*args, **kwargs)

        self._run_eng = RunEngine(None)

        if self._shared_config['scan_data'] is None:
            self._shared_config['scan_data'] = collections.deque(maxlen=100)
        self._data_buffer = self._shared_config['scan_data']

        self.settle_time = None

        self.paths = list()
        self.positioners = list()

        self._plotx = None
        self._ploty = None

        try:
            self.logbook = session_manager['olog_client']
        except KeyError:
            self.logbook = None

    def __call__(self, *args, **kwargs):
        """Start a run

        This is a convinience function and calls :py:meth:`run` with the
        parameters passed to this function. This is equivalent to::

        >>>scan.run(*args, **kwargs)
        """
        self.run(*args, **kwargs)

    def check_paths(self):
        """Check the positioner paths

        This routine checks the path of the positioners against limits by
        using the :py:meth:`check_value` method.

        Raises
        ------
        ValueError
            Raised in the case that a positioner will be moved outside its
            limits.
        """
        for pos, path in zip(self.positioners, self.paths):
            for p in path:
                try:
                    pos.check_value(p)
                except LimitError:
                    raise ValueError('Scan moves positioner {} \
                                     out of limits {},{}'.format(
                                     pos.name, pos.low_limit, pos.high_limit))

    def __enter__(self):
        """Entry point for context manager"""
        self.pre_scan()

    def __exit__(self, exec_type, exec_value, tb):
        """Exit point for context manager"""
        logger.debug("Scan context manager exited with %s", str(exec_value))
        traceback.print_tb(tb)
        self.post_scan()

    def pre_scan(self):
        """Routine run before scan starts"""
        pass

    def post_scan(self):
        """Routine run after scan has completed"""
        pass

    def setup_detectors(self, detectors):
        """Routine run to setup detectors before scan starts

        Parameters
        ----------
        detectors : list of Ophyd Objects
            List of the detectors to configure.
        """
        pass

    def setup_triggers(self, triggers):
        """Routine run to setup triggers before scan starts

        Parameters
        ----------
        triggers : list of OphydObjects
            List of the triggers to configure.
        """
        pass

    def format_plot(self):
        """Guess the positioners and detectors that the user cares about

        Returns
        -------
        plotx : str
            The default positioners to set as the x axis
        ploty : list
            The list of positioners/detectors to plot on the y axis
        """

        pos_names = [pos.name for pos in self.positioners]
        det_names = [det.name for det in self.detectors]
        valid_names = pos_names + det_names
        # default value for the x axis
        if len(self.positioners) > 0:
            plotx = self.positioners[0].name
            # if plotx is not a valid string, ignore it. if it is, make
            # sure that it is in the positioners/detectors that the
            # scan knows about
            if isinstance(self._plotx, six.string_types):
                if self._plotx:
                    for name in valid_names:
                        if name in self._plotx:
                            plotx = name
                            break
        else:
            plotx = None

        ploty = []
        # checking validity of self._ploty
        for name in valid_names:
            if self._ploty is not None:
                if name in self._ploty:
                    ploty.append(name)
        return plotx, ploty

    def run(self, **kwargs):
        """Run the scan

        The main loop of the scan. This routine runs the scan and calls the
        ophyd runengine.
        """
        self.scan_id = session_manager.get_next_scan_id()

        # Run this in a context manager to capture
        # the KeyboardInterrupt

        with self:
            self.check_paths()
            self.setup_detectors(self.detectors)
            self.setup_triggers(self.triggers)

            for pos, path in zip(self.positioners, self.paths):
                pos.set_trajectory(path)

            # Create the dict to pass to the run-engine

            scan_args = dict()
            scan_args['detectors'] = self.detectors
            scan_args['triggers'] = self.triggers
            scan_args['positioners'] = self.positioners
            scan_args['settle_time'] = self.settle_time
            scan_args['custom'] = {}
            plotx, ploty = self.format_plot()
            if plotx:
                scan_args['custom']['plotx'] = plotx
            if ploty:
                scan_args['custom']['ploty'] = ploty

            # Run the scan!
            data = self._run_eng.start_run(self.scan_id,
                                           scan_args=scan_args)

            self._data_buffer.append(Data(data))

    @property
    def data(self):
        """Return the data ringbuffer

        Returns
        -------
        :py:class:`collections.deque` object containing :py:class:`Data` objects
        """
        return self._data_buffer

    @property
    def last_data(self):
        """Returns the last data set

        Returns
        -------
        :py:class:`Data` object
            Returns the last data. Equivalent to `Scan.data[-1]`
        """
        if len(self._data_buffer) > 0:
            return self._data_buffer[-1]
        return None

    @property
    def default_detectors(self):
        """Return the default detectors

        Returns
        -------
        list of OphydObjects
        """
        return self._shared_config['default_detectors']

    @default_detectors.setter
    def default_detectors(self, detectors):
        """Set the default detectors"""
        self._shared_config['default_detectors'] = detectors

    @property
    def default_triggers(self):
        """Return the default triggers

        Returns
        -------
        list of OphydObjects
        """
        return self._shared_config['default_triggers']

    @default_triggers.setter
    def default_triggers(self, triggers):
        """Set the default triggers"""
        self._shared_config['default_triggers'] = triggers

    @property
    def user_detectors(self):
        """Return the user detectors

        Returns
        -------
        list of OphydObjects
        """
        return self._shared_config['user_detectors']

    @user_detectors.setter
    def user_detectors(self, detectors):
        """Set the user detectors"""
        self._shared_config['user_detectors'] = detectors

    @property
    def user_triggers(self):
        """Return the user triggers

        Returns
        -------
        list of OphydObjects
        """
        return self._shared_config['user_triggers']

    @user_triggers.setter
    def user_triggers(self, triggers):
        """Set the user triggers"""
        self._shared_config['user_triggers'] = triggers

    @property
    def triggers(self):
        """Return the triggers for this scan

        The triggers of the scan is a concatenation of the list of triggers
        for this scan instance and the default triggers which is a singleton.

        Returns
        -------
        list of OphydObjects
        """
        return self._shared_config['user_triggers'] + self.default_triggers

    @property
    def detectors(self):
        """Return the detectors for this scan

        The detectors of the scan is a concatenation of the list of detectors
        for this scan instance and the default detectors which is a singleton.

        Returns
        -------
        list of OphydObjects
        """
        return self._shared_config['user_detectors'] + self.default_detectors


class AScan(Scan):
    """Class for running N-Dimensional Scan

    This class performs setup and runs N-dimensional scans.

    Examples
    --------
    Scan motor m1 from -10 to 10 with 20 intervals::

    >>>scan(m1, -10, 10, 20)

    Scan motor m1 and m2 in a linear path with 20 intervals with m1
    starting at -10 and m2 starting at -5 and traveling to 10 and 5
    respectively::

    >>>scan([[m1, m2]], [[-10, -5]], [[10, 5]], 20)

    Scan motors m1 and m2 in a mesh of 20 x 20 intervals with m1 traveling
    from -10 to 10 and m2 traveling from -5 to 5::

    >>>scan([[m1], [m2]], [[-10], [-5]], [[10], [5]], [20, 20])

    Scan motors m1 and m2 in a linear path in the first dimension and
    m3 as a linear path in the second dimension::

    >>>scan([[m1, m2], m3], [[-10, -5], -2], [[10, 5], 2], [20, 20])
    """

    def __init__(self, *args, **kwargs):
        super(AScan, self).__init__()
        self.dimension = None
        self.scan_command = None

    def pre_scan(self, *args, **kwargs):
        super(AScan, self).pre_scan(*args, **kwargs)
        self._make_log_entry()

    def _make_log_entry(self):
        """Format and make a log entry for the scan"""

        # Print header

        msg = ['Scan Command    : {}'.format(self.scan_command)]
        msg.append('Scan ID         : {}'.format(self.scan_id))
        msg.append('Scan Dimension  : {}'.format(self.dimension))
        msg.append('Scan Datapoints : {} ({})'.format(self.datapoints,
                                                      np.prod(self.datapoints)))

        # Print positioners and start and stop values

        msg.append('')
        msg.append('{:<30} {:<20} {:<20}:'.format('Positioners',
                                                  'Min', 'Max'))

        for pos, path in zip(self.positioners, self.paths):
            msg.append('{:<30} {:<20.8f} {:<20.8f}'.format(pos.name,
                                                           min(path),
                                                           max(path)))
        msg.append('')
        msg.append('Triggers:')
        for trig in self.triggers:
            msg.append('{:<30}'.format(trig.name))

        msg.append('')
        msg.append('Detectors:')
        for det in self.detectors:
            msg.append('{:<30}'.format(det.name))

        msg.append('')

        msg.append('{0:=^80}'.format(''))

        for p in self.positioners + self.triggers + self.detectors:
            try:
                msg.append('PV:{}'.format(p.report['pv']))
            except KeyError:
                pass

        d = {}
        d['id'] = self.scan_id
        d['command'] = self.scan_command
        d['triggers'] = repr(self.triggers)
        d['detectors'] = repr(self.detectors)
        d['positioners'] = repr(self.positioners)
        d['start'] = repr(self.start)
        d['stop'] = repr(self.stop)
        d['npts'] = repr(self.npts)
        if self.logbook is not None:
            self.logbook.log('\n'.join(msg), properties={'OphydScan': d},
                             ensure=True,
                             logbooks=['Data Acquisition'])

    def _format_command_line(self, *args, **kwargs):
        """Return a string representation of the passed arguments"""
        cl_args = cmdline_to_str(*args, **kwargs)
        rtn = '{}()({})'.format(self.__class__.__name__, cl_args)
        return rtn

    def __call__(self, positioners, start, stop, npts, **kwargs):
        """Scan positioners along a regular path

        This method will Setup the scan and run the RunEngine (perform a scan)

        Parameters
        ----------
        positioners : Positioner or list of Positioners
            The positioner objects to use in the scan
        start : position or list of positions
            The start position of the positioners
        stop : position or list of positions
            The stop position of the positioners
        npts : int or list of int
            The number of intervals in the scan
        """
        self.setup_scan(positioners, start, stop, npts, **kwargs)
        self.run(**kwargs)

    def setup_scan(self, positioners, start, stop, npts, **kwargs):
        """Setup scan along a regular path.

        This method will Setup the scan only. The scan can be executed using
        :py:meth:`run` method.

        Parameters
        ----------
        positioners : Positioner or list of Positioners
            The positioner objects to use in the scan
        start : position or list of positions
            The start position of the positioners
        stop : position or list of positions
            The stop position of the positioners
        npts : int or list of int
            The number of intervals in the scan
        """

        # This is an n-dimensional scan. We take the dims from
        # the length of npts.

        positioners = ensure_iterator(positioners)
        start = ensure_iterator(start)
        stop = ensure_iterator(stop)
        npts = np.array(ensure_iterator(npts))
        dimension = npts.shape[0]

        self.start = start
        self.stop = stop
        self.npts = npts

        args = (positioners, start, stop, npts)
        self.scan_command = self._format_command_line(*args, **kwargs)

        # Calculate number of points from intervals

        npts = np.array(npts) + 1

        # Make the array to populate the ranges with
        edges = [np.linspace(0, 1, n) for n in npts]
        grid = [np.array(a) for a in zip(*itertools.product(*edges))]

        # This grid goes from 0 to 1 in all dimensions.
        # and can be used to scale start and stop points

        pos = []
        paths = []
        for d in range(dimension):
            # For each dimension we work out the paths
            # each dimension can have a number of positioners
            iter_pos = ensure_iterator(positioners[d])
            begin = ensure_iterator(start[d])
            end = ensure_iterator(stop[d])

            for p, b, e in zip(iter_pos, begin, end):
                pos.append(p)
                path = b + ((e-b) * grid[d])
                paths.append(path)

        self.positioners = pos
        self.paths = paths
        self.datapoints = npts
        self.dimension = dimension


class DScan(AScan):
    def setup_scan(self, *args, **kwargs):
        """Store starting positions and change paths

        This setup_scan routine stores the current position of the positioners
        upon execution and then sets the paths to the difference between the
        current position and the scan range.
        """
        super(DScan, self).setup_scan(*args, **kwargs)
        self._start_positions = [p.position for p in self.positioners]
        self.paths = [np.array(path) + start
                      for path, start in zip(self.paths, self._start_positions)]

    def post_scan(self):
        """Post Scan Move to start positions

        This post scan routine returns the positioners to their origional
        starting position (as recorded by :py:meth:`pre_scan`) once the scan
        has finished.
        """
        super(DScan, self).post_scan()
        status = [pos.move(start, wait=False)
                  for pos, start in
                  zip(self.positioners, self._start_positions)]

        logger.info("Moving positioners back to start positions.......")
        while any(not stat.done for stat in status):
            sleep(0.01)

        logger.info(tc.Green + " Done.")


class Count(Scan):
    """Trigger and collect a single measurement

    This class serves as a mechanism to trigger and collect a single
    measurement. This is often termed a *count*. This class inherits
    from the :py:class:`Scan` class and therefore formats and records a
    single *run* of one datapoint.

    A log entry is created if the logbook is setup which records the
    result of the scan.
    """
    def post_scan(self):
        """Post-scan print data

        This post-scan routine prints the scan results to the screen and
        if the logbook is setup prints the results to the screen
        """
        super(Count, self).post_scan()

        msg = self._fmt_count()

        logger.info('\n'+msg+'\n')

        # Make a logbook entry

        lmsg = []
        lmsg.append('Scan ID         : {}'.format(self.scan_id))
        lmsg.append('')
        lmsg.append(msg)
        lmsg.append('Triggers:')
        for trig in self.triggers:
            lmsg.append('{:<30}'.format(trig.name))
        lmsg.append('')
        lmsg.append('{0:=^80}'.format(''))
        for p in self.triggers + self.detectors:
            try:
                lmsg.append('PV:{}'.format(p.report['pv']))
            except KeyError:
                pass

        d = {}
        d['id'] = self.scan_id
        d['triggers'] = repr(self.triggers)
        d['detectors'] = repr(self.detectors)
        d['values'] = repr(self.last_data.data_dict)
        if self.logbook is not None:
            self.logbook.log('\n'.join(lmsg), ensure=True,
                             properties={'OphydCount': d},
                             logbooks=['Data Acquisition'])

    def _fmt_count(self):
        """Format the count results

        Returns
        -------
        string
            String of a tabular representation of the counts from the
            detectors
        """
        rtn = []
        rtn.append('{:<28} | {}'.format('Detector', 'Value'))
        rtn.append('{0:=^60}'.format(''))
        data = collections.OrderedDict(sorted(self.last_data.data_dict.items()))
        for x, y in data.iteritems():
            rtn.append('{:<30} {}'.format(x, y))
        rtn.append('')
        return '\n'.join(rtn)


def ensure_iterator(i):
    """Check if i is an iterator. If not return length-1 iterator"""
    if hasattr(i, "__iter__") or hasattr(i, "__getitem__"):
        return i
    else:
        return [i]


def objects_to_str(iterables, iter_sep=', ', iter_start='(',
                   iter_stop=')'):

    text = []

    # To see if we need start/stop chars then we see if we
    # have a length 1 iterator

    l = 0
    try:
        l = len(iterables)
    except TypeError:
        pass

    for i in iterables:
        # Is the object i iterable:
        if isinstance(i, tuple):
            text.append(objects_to_str(i))
        elif isinstance(i, list):
            text.append(objects_to_str(i, iter_start='[', iter_stop=']'))
        else:
            try:
                # Try to see if we have a name attribute
                text.append(i.name)
            except AttributeError:
                # Object does not have a name
                pass
            else:
                # We have a valid name, break the iteration
                break

            text.append(repr(i))

    text = iter_sep.join(text)

    if l != 1:
        return ''.join([iter_start, text, iter_stop])

    return text


def cmdline_to_str(*args, **kwargs):
    """Format a string based on the command line"""
    msg = [objects_to_str(args, iter_start='', iter_stop='')]
    if len(kwargs) > 0:
        msg.append(', ')
        for key, value in kwargs.iteritems():
            msg.append('{}={}'.format(key, objects_to_str(value)))

    return ''.join(msg)
