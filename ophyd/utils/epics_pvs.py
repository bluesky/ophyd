# vi: ts=4 sw=4 sts=4 expandtab
'''
:mod:`ophyd.utils.epics_pvs` - EPICS-related utilities
======================================================

.. module:: ophyd.utils.epics_pvs
   :synopsis:

'''

from __future__ import print_function
import ctypes
import warnings
import threading

import epics

from . import errors
from . import threads
from .decorators import cached_retval

__all__ = ['split_record_field',
           'strip_field',
           'record_field',
           'check_alarm',
           'MonitorDispatcher',
           'get_pv_form',
           ]


def split_record_field(pv):
    '''
    Splits a pv into (record, field)

    :param str pv: the pv to split
    :returns: (record, field)
    '''
    if '.' in pv:
        record, field = pv.rsplit('.', 1)
    else:
        record, field = pv, ''

    return record, field


def strip_field(pv):
    '''
    Strip off the field from a record
    '''
    return split_record_field(pv)[0]


def record_field(record, field):
    '''
    Given a record and a field, combine them into
    a pv of the form: record.FIELD
    '''
    record = strip_field(record)
    return '%s.%s' % (record, field.upper())


def check_alarm(base_pv, stat_field='STAT', severity_field='SEVR',
                reason_field=None, reason_pv=None,
                min_severity=errors.EPICS_SEV_MINOR):
    """
    Raise an exception if an alarm is set

    :raises: AlarmError (MinorAlarmError, MajorAlarmError)
    """
    stat_pv = '%s.%s' % (base_pv, stat_field)
    severity_pv = '%s.%s' % (base_pv, severity_field)
    if reason_field is not None:
        reason_pv = '%s.%s' % (base_pv, reason_field)
    reason = None

    severity = epics.caget(severity_pv)

    if severity >= min_severity:
        try:
            error_class = errors.get_alarm_error(severity)
        except KeyError:
            pass
        else:
            severity = epics.caget(severity_pv, as_string=True)
            alarm = epics.caget(stat_pv, as_string=True)
            if reason_pv is not None:
                reason = epics.caget(reason_pv, as_string=True)

            message = 'Alarm status %s [severity %s]' % (alarm, severity)
            if reason is not None:
                message = '%s: %s' % (message, reason)

            raise error_class(message)

    return True


class MonitorDispatcher(threads.ThreadFunnel):
    def __init__(self, *args, **kwargs):
        '''
        The monitor dispatcher works around having callbacks from libca threads.
        Using epics CA calls (caget, caput, etc.) from those callbacks is not possible
        without this dispatcher workaround.

        ... note:: Without `all_contexts` set, only the callbacks that are run with the
            same context as the the main thread are affected.

        ... note:: Ensure that you call epics.ca.use_initial_context() at startup in the
            main thread

        :param all_contexts: re-route _all_ callbacks from _any_ context to
            the dispatcher callback thread(s) [default: False]
        :param single_thread: only use one thread [default: False]

        '''
        all_contexts = kwargs.pop('all_contexts', False)
        single_thread = kwargs.get('single_thread', False)

        self.main_context = epics.ca.current_context()
        self.all_contexts = bool(all_contexts)
        self.single_thread = bool(single_thread)

        threads.ThreadFunnel.__init__(self, *args, name='MonitorDispatch',
                                      single_thread=single_thread, **kwargs)

        self.setup()

    def _tag_args(self, args):
        '''
        Mark the PyEpics monitor callback arguments to be handled by the
        dispatcher
        '''
        if not callable(args.usr):
            # Not a callback
            return
        elif hasattr(args.usr, '_disp_tag') and args.usr._disp_tag is self:
            # Already tagged with this dispatcher. No need to do it again.
            return

        if self.single_thread:
            args.usr = lambda orig_cb=args.usr, **kwargs: \
                self.add_event(orig_cb, **kwargs)
        else:
            thread = threading.currentThread()
            cat = 'Epics%s' % (thread.ident, )
            if cat not in self._categories:
                # Dynamically add categories
                self.add_category(cat)

            args.usr = lambda cat=cat, orig_cb=args.usr, **kwargs: \
                self.add_event(cat, orig_cb, **kwargs)
        args.usr._disp_tag = self

    def _monitor_event(self, args):
        if self.all_contexts or self.main_context == epics.ca.current_context():
            self._tag_args(args)

        return epics.ca._onMonitorEvent(args)

    def _setup_pyepics(self, enable):
        # Re-route monitor events to our new handler
        if enable:
            fcn = self._monitor_event
        else:
            fcn = epics.ca._onMonitorEvent

        epics.ca._CB_EVENT = ctypes.CFUNCTYPE(None, epics.dbr.event_handler_args)(fcn)

    def setup(self):
        if not self._initialized:
            self._setup_pyepics(True)
            self._initialized = True

    def teardown(self):
        if self._initialized:
            self._setup_pyepics(False)


def waveform_to_string(value, type_=str, delim=''):
    '''
    Convert a waveform that represents a string
    into an actual Python string

    :param value: The value to convert
    :param type_: Python type to convert to
    :param delim: delimiter to use when joining string
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


@cached_retval
def get_pv_form():
    '''
    Due to a bug in certain versions of PyEpics, form='time'
    cannot be used with some large arrays.

    native: gives time.time() timestamps from this machine
    time: gives timestamps from the PVs themselves

    :returns: 'native' or 'time'
    '''

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

    version = parse_version(epics.__version__)

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


def records_from_db(fn):
    '''
    Naively parses db/template files looking for record names

    :returns: [(record type, record name), ...]
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
