# vi: ts=4 sw=4 sts=4 expandtab
'''
:mod:`ophyd.utils.epics_pvs` - EPICS-related utilities
======================================================

.. module:: ophyd.utils.epics_pvs
   :synopsis:
'''
from enum import IntEnum
import time as ttime
import ctypes
import threading
import queue
import logging
import warnings
import functools
import numpy as np

import epics

from .errors import DisconnectedError, OpException

__all__ = ['split_record_field',
           'strip_field',
           'record_field',
           'MonitorDispatcher',
           'get_pv_form',
           'set_and_wait',
           'AlarmStatus',
           'AlarmSeverity',
           ]

logger = logging.getLogger(__name__)


class BadPVName(ValueError, OpException):
    ...


class AlarmSeverity(IntEnum):
    NO_ALARM = 0
    MINOR = 1
    MAJOR = 2
    INVALID = 3


class AlarmStatus(IntEnum):
    NO_ALARM = 0
    READ = 1
    WRITE = 2
    HIHI = 3
    HIGH = 4
    LOLO = 5
    LOW = 6
    STATE = 7
    COS = 8
    COMM = 9
    TIMEOUT = 10
    HWLIMIT = 11
    CALC = 12
    SCAN = 13
    LINK = 14
    SOFT = 15
    BAD_SUB = 16
    UDF = 17
    DISABLE = 18
    SIMM = 19
    READ_ACCESS = 20
    WRITE_ACCESS = 21


def validate_pv_name(pv):
    '''Validates that there is not more than 1 '.' in pv

    Parameters
    ----------
    pv : str
        The pv to check

    Raises
    ------
    BadPVName
    '''
    if pv.count('.') > 1:
        raise BadPVName(pv)


def split_record_field(pv):
    '''Splits a pv into (record, field)

    Parameters
    ----------
    pv : str
        the pv to split

    Returns
    -------
    record : str
    field : str
    '''
    if '.' in pv:
        record, field = pv.rsplit('.', 1)
    else:
        record, field = pv, ''

    return record, field


def strip_field(pv):
    '''Strip off the field from a record'''
    return split_record_field(pv)[0]


def record_field(record, field):
    '''Given a record and a field, combine them into
    a pv of the form: record.FIELD
    '''
    record = strip_field(record)
    return '%s.%s' % (record, field.upper())


class MonitorDispatcher(epics.ca.CAThread):
    '''A monitor dispatcher which works with pyepics

    The monitor dispatcher works around having callbacks from libca threads.
    Using epics CA calls (caget, caput, etc.) from those callbacks is not
    possible without this dispatcher workaround.

    ... note:: Without `all_contexts` set, only the callbacks that are run with
        the same context as the the main thread are affected.

    ... note:: Ensure that you call epics.ca.use_initial_context() at startup in
        the main thread

    Parameters
    ----------
    all_contexts : bool, optional
        re-route _all_ callbacks from _any_ context to the dispatcher callback
        thread
    timeout : float, optional
    callback_logger : logging.Logger, optional
        A logger to notify about failed callbacks

    Attributes
    ----------
    main_context : ctypes long
        The main CA context
    callback_logger : logging.Logger
        A logger to notify about failed callbacks
    queue : Queue
        The event queue
    '''

    def __init__(self, all_contexts=False, timeout=0.1,
                 callback_logger=None):
        epics.ca.CAThread.__init__(self, name='monitor_dispatcher')

        self.daemon = True
        self.queue = queue.Queue()

        # The dispatcher thread will stop if this event is set
        self._stop_event = threading.Event()
        self.main_context = epics.ca.current_context()
        self.callback_logger = callback_logger

        self._all_contexts = bool(all_contexts)
        self._timeout = timeout

        self.start()

    def run(self):
        '''The dispatcher itself'''
        self._setup_pyepics(True)

        while not self._stop_event.is_set():
            try:
                callback, args, kwargs = self.queue.get(True, self._timeout)
            except queue.Empty:
                pass
            else:
                try:
                    callback(*args, **kwargs)
                except Exception as ex:
                    if self.callback_logger is not None:
                        self.callback_logger.error(ex, exc_info=ex)

        self._setup_pyepics(False)
        epics.ca.detach_context()

    def stop(self):
        '''Stop the dispatcher thread and re-enable normal callbacks'''
        self._stop_event.set()

    def _setup_pyepics(self, enable):
        # Re-route monitor events to our new handler
        if enable:
            fcn = self._monitor_event
        else:
            fcn = epics.ca._onMonitorEvent

        epics.ca._CB_EVENT = ctypes.CFUNCTYPE(None, epics.dbr.event_handler_args)(fcn)

    def _monitor_event(self, args):
        if self._all_contexts or self.main_context == epics.ca.current_context():
            if callable(args.usr):
                if not hasattr(args.usr, '_disp_tag') or args.usr._disp_tag is not self:
                    args.usr = lambda orig_cb=args.usr, **kwargs: \
                        self.queue.put((orig_cb, [], kwargs))
                    args.usr._disp_tag = self

        return epics.ca._onMonitorEvent(args)


def waveform_to_string(value, type_=str, delim=''):
    '''Convert a waveform that represents a string into an actual Python string

    Parameters
    ----------
    value
        The value to convert
    type_ : type, optional
        Python type to convert to
    delim : str, optional
        delimiter to use when joining string
    '''
    try:
        value = delim.join(chr(c) for c in value)
    except TypeError:
        value = type_(value)

    try:
        value = value[:value.index('\0')]
    except (IndexError, ValueError):
        pass

    return value


def get_pv_form():
    '''Get the PV form that should be used for pyepics

    Due to a bug in certain versions of PyEpics, form='time' cannot be used
    with some large arrays.

    native: gives time.time() timestamps from this machine
    time: gives timestamps from the PVs themselves

    Returns
    -------
    {'native', 'time'}
    '''
    def _fix_git_versioning(in_str):
        return in_str.replace('-g', '+g')

    def _naive_parse_version(version):
        try:
            version = version.lower()

            # Strip off the release-candidate version number (best-effort)
            if 'rc' in version:
                version = version[:version.index('rc')]

            version_tuple = tuple(int(v) for v in version.split('.'))
        except:
            return None

        return version_tuple

    try:
        from pkg_resources import parse_version
    except ImportError:
        parse_version = _naive_parse_version

    version = parse_version(_fix_git_versioning(epics.__version__))

    if version is None:
        warnings.warn('Unrecognized PyEpics version; using local timestamps',
                      ImportWarning)
        return 'native'

    elif version <= parse_version('3.2.3'):
        warnings.warn('PyEpics versions <= 3.2.3 will use local timestamps (version: %s)' %
                      epics.__version__,
                      ImportWarning)
        return 'native'
    else:
        return 'time'


pv_form = get_pv_form()


def records_from_db(fn):
    '''Naively parse db/template files looking for record names

    Returns
    -------
    records : list
        [(record type, record name), ...]
    '''

    ret = []
    for line in open(fn, 'rt').readlines():
        line = line.strip()

        if line.startswith('#'):
            continue

        if not (line.startswith('record') or line.startswith('grecord')):
            continue

        if '(' not in line:
            continue

        line = line[line.index('(') + 1:]
        if ',' not in line:
            continue

        rtype, record = line.split(',', 1)
        rtype = rtype.strip()
        record = record.strip()

        if record.startswith('"'):
            # Surrounded by quotes, easy to parse
            record = record[1:]
            record = record[:record.index('"')]
        else:
            # No quotes, and macros may contain parentheses
            # Find the first non-matching parenthesis and
            # that should denote the end of the record name
            #
            # $(P)$(R)Record)
            #               ^

            in_paren = 0
            for i, c in enumerate(record):
                if c == '(':
                    in_paren += 1
                elif c == ')':
                    in_paren -= 1

                    if in_paren < 0:
                        record = record[:i]
                        break

        ret.append((rtype, record))

    return ret


def raise_if_disconnected(fcn):
    '''Decorator to catch attempted access to disconnected EPICS channels.'''
    @functools.wraps(fcn)
    def wrapper(self, *args, **kwargs):
        if self.connected:
            return fcn(self, *args, **kwargs)
        else:
            raise DisconnectedError('{} is not connected'.format(self.name))
    return wrapper


def set_and_wait(signal, val, poll_time=0.01, timeout=10, rtol=None,
                 atol=None):
    """Set a signal to a value and wait until it reads correctly.

    For floating point values, it is strongly recommended to set a tolerance.
    If tolerances are unset, the values will be compared exactly.

    Parameters
    ----------
    signal : EpicsSignal (or any object with `get` and `put`)
    val : object
        value to set signal to
    poll_time : float, optional
        how soon to check whether the value has been successfully set
    timeout : float, optional
        maximum time to wait for value to be successfully set
    rtol : float, optional
        allowed absolute tolerance between the readback and setpoint values
    atol : float, optional
        allowed relative tolerance between the readback and setpoint values

    Raises
    ------
    TimeoutError if timeout is exceeded
    """
    if atol is None and hasattr(signal, 'tolerance'):
        atol = signal.tolerance
    if rtol is None and hasattr(signal, 'rtolerance'):
        rtol = signal.rtolerance

    signal.put(val)
    expiration_time = ttime.time() + timeout if timeout is not None else None
    current_value = signal.get()
    try:
        es = signal.enum_strs
    except AttributeError:
        es = ()

    if atol is not None:
        within_str = ['within {!r}'.format(atol)]
    else:
        within_str = []

    if rtol is not None:
        within_str.append('(relative tolerance of {!r})'.format(rtol))

    if within_str:
        within_str = ' '.join([''] + within_str)
    else:
        within_str = ''

    while not _compare_maybe_enum(val, current_value, es, atol, rtol):
        logger.info("Waiting for %s to be set from %r to %r%s...",
                    signal.name, current_value, val, within_str)
        ttime.sleep(poll_time)
        poll_time *= 2  # logarithmic back-off
        current_value = signal.get()
        if expiration_time is not None and ttime.time() > expiration_time:
            raise TimeoutError("Attempted to set %r to value %r and timed "
                               "out after %r seconds. Current value is %r." %
                               (signal, val, timeout, current_value))


def _compare_maybe_enum(a, b, enums, atol, rtol):
    if enums:
        # convert enum values to strings if necessary first:
        if not isinstance(a, str):
            a = enums[a]
        if not isinstance(b, str):
            b = enums[b]
        # then compare the strings
        return a == b

    # if either relative/absolute tolerance is used, use numpy
    # to compare:
    if atol is not None or rtol is not None:
        return np.allclose(a, b,
                           rtol=rtol if rtol is not None else 1e-5,
                           atol=atol if atol is not None else 1e-8,
                           )
    return a == b


_type_map = {'number': (float, ),
             'array': (np.ndarray, ),
             'string': (str, ),
             'integer': (int, ),
             }


def data_type(val):
    '''Determine data-type of val.

    Returns:
    -----------
    str
        One of ('number', 'array', 'string'), else raises ValueError
    '''
    for json_type, py_types in _type_map.items():
        if type(val) in py_types:
            return json_type
    # no legit type found...
    raise ValueError('{} not a valid type (int, float, ndarray, str)'.format(val))


def data_shape(val):
    '''Determine data-shape (dimensions)

    Returns:
    --------
    list
        Empty list if val is number or string, otherwise list(np.ndarray.shape)
    '''
    for json_type, py_types in _type_map.items():
        if type(val) in py_types:
            if json_type is 'array':
                return list(val.shape)
            else:
                return list()
    raise ValueError('Cannot determine shape of {}'.format(val))
