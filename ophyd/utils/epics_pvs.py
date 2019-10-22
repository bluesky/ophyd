# vi: ts=4 sw=4 sts=4 expandtab
from enum import IntEnum
import time as ttime
import logging
import functools
import numpy as np

from .errors import DisconnectedError, OpException


__all__ = ['split_record_field',
           'strip_field',
           'record_field',
           'set_and_wait',
           'AlarmStatus',
           'AlarmSeverity',
           'fmt_time'
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


def set_and_wait(signal, val, poll_time=0.01, timeout=60, rtol=None,
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
    signal.put(val)
    expiration_time = ttime.time() + timeout if timeout is not None else None
    current_value = signal.get()

    if atol is None and hasattr(signal, 'tolerance'):
        atol = signal.tolerance
    if rtol is None and hasattr(signal, 'rtolerance'):
        rtol = signal.rtolerance

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

    while not _compare_maybe_enum(val, current_value, es, atol, rtol, timeout, start_time, signal.name):
        logger.debug("Waiting for %s to be set from %r to %r%s...",
                     signal.name, current_value, val, within_str)
        ttime.sleep(poll_time)
        if poll_time < 0.1:
            poll_time *= 2  # logarithmic back-off
        current_value = signal.get()
        if expiration_time is not None and ttime.time() > expiration_time:
            raise TimeoutError("Attempted to set %r to value %r and timed "
                               "out after %r seconds. Current value is %r." %
                               (signal, val, timeout, current_value))


def _compare_maybe_enum(a, b, enums, atol, rtol, timeout, start_time, signal_name):
    if enums:
        # convert enum values to strings if necessary first:
        if not isinstance(a, str):
            a = enums[a]
        if not isinstance(b, str):
            b = enums[b]
        # then compare the strings
        ret = a == b
        if ret and signal_name == 'rixscam_hdf5_capture':
            print(f'>>>> Setting "{signal_name}" took {ttime.time() - start_time:.5f}s (timeout={timeout}s)')
        return ret

    # if either relative/absolute tolerance is used, use numpy
    # to compare:
    if atol is not None or rtol is not None:
        return np.allclose(a, b,
                           rtol=rtol if rtol is not None else 1e-5,
                           atol=atol if atol is not None else 1e-8,
                           )
    ret = a == b
    try:
        return bool(ret)
    except ValueError:
        return np.all(ret)


_type_map = {'number': (float, np.floating),
             'array': (np.ndarray, list, tuple),
             'string': (str, ),
             'integer': (int, np.integer),
             }


def data_type(val):
    '''Determine data-type of val.

    Returns
    -------
    str
        One of ('number', 'array', 'string'), else raises ValueError
    '''
    for json_type, py_types in _type_map.items():
        if isinstance(val, py_types):
            return json_type
    # no legit type found...
    raise ValueError(
        '{!r} '.format(val) +
        'not a valid type (int, float, ndarray, str, list, tuple)')


def data_shape(val):
    '''Determine data-shape (dimensions)

    Returns
    -------
    list
        Empty list if val is number or string, otherwise
        ``list(np.ndarray.shape)``
    '''
    dtype = data_type(val)
    if dtype != 'array':
        return []

    try:
        return list(val.shape)
    except AttributeError:
        return [len(val)]


# Vendored from pyepics v3.3.0
# e33b9290282c93f8dfe0fbe81ced55cbcab99564
# Copyright  2010  Matthew Newville, The University of Chicago.
# All rights reserved.
# Epics Open License
# see other_licenses folder for full license
def fmt_time(tstamp=None):
    "simple formatter for time values"
    if tstamp is None:
        tstamp = ttime.time()
    tstamp, frac = divmod(tstamp, 1)
    return "%s.%5.5i" % (ttime.strftime("%Y-%m-%d %H:%M:%S",
                                        ttime.localtime(tstamp)),
                         round(1.e5*frac))
