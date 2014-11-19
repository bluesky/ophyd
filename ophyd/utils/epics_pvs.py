from __future__ import print_function
import ctypes
import threading
import Queue as queue

from . import errors
import epics

__all__ = ['split_record_field',
           'strip_field',
           'record_field',
           'check_alarm',
           'MonitorDispatcher',
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


class MonitorDispatcher(epics.ca.CAThread):
    # TODO this needs to be setup by the session manager.
    def __init__(self, all_contexts=False, timeout=0.1,
                 callback_logger=None):
        '''
        The monitor dispatcher works around having callbacks from libca threads.
        Using epics CA calls (caget, caput, etc.) from those callbacks is not possible
        without this dispatcher workaround.

        ... note:: Without `all_contexts` set, only the callbacks that are run with the
            same context as the the main thread are affected.

        ... note:: Ensure that you call epics.ca.use_initial_context() at startup in the
            main thread

        :param all_contexts: re-route _all_ callbacks from _any_ context to
            the dispatcher callback thread [default: False]

        '''
        epics.ca.CAThread.__init__(self, name='monitor_dispatcher')

        self.daemon = True
        self.queue = queue.Queue()

        # The dispatcher thread will stop if this event is set
        self.stop_event = threading.Event()
        self.main_context = epics.ca.current_context()
        self.callback_logger = callback_logger

        self._all_contexts = bool(all_contexts)
        self._timeout = timeout

    def run(self):
        '''
        The dispatcher itself
        '''
        self._setup_pyepics(True)

        while not self.stop_event.is_set():
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

    def stop(self):
        '''
        Stop the dispatcher thread and re-enable normal callbacks
        '''
        self._stop_event.set()

    def _setup_pyepics(self, enable):
        # Re-route monitor events to our new handler
        if enable:
            fcn = self._monitor_event
        else:
            fcn = epics.ca._onMonitorEvent

        epics.ca._CB_EVENT = ctypes.CFUNCTYPE(None, epics.dbr.event_handler_args)(fcn)

    def _monitor_event(self, args):
        if self.all_contexts or self.main_context == epics.ca.current_context():
            if callable(args.usr):
                if not hasattr(args.usr, '_disp_tag') or args.usr._disp_tag is not self:
                    args.usr = lambda orig_cb=args.usr, **kwargs: \
                        self.queue.put((orig_cb, [], kwargs))
                    args.usr._disp_tag = self

        return epics.ca._onMonitorEvent(args)
