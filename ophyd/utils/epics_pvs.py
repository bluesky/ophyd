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
           'install_monitor_dispatcher',
           'restore_monitor',
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


# TODO this needs to be setup by the session manager.
# TODO ** call epics.ca.use_initial_context() at startup in main thread
def monitor_dispatcher(monitor_queue, stop_event,
                       timeout=0.1):
    while True:
        try:
            callback, args, kwargs = monitor_queue.get(True, timeout)
        except queue.Empty:
            pass
        else:
            callback(*args, **kwargs)

        if stop_event.is_set():
            break


def install_monitor_dispatcher(all_contexts=False):
    '''
    The monitor dispatcher works around having callbacks from libca threads.
    Using epics CA calls (caget, caput, etc.) from those callbacks is not possible
    without this dispatcher workaround.

    ... note:: Without `all_contexts` set, only the callbacks that are run with the
        same context as the the main thread are affected.

    :param all_contexts: re-route _all_ callbacks from _any_ context to
        the dispatcher callback thread [default: False]

    '''
    def monitor_event(args):
        if all_contexts or dispatcher_thread.main_context == epics.ca.current_context():
            if callable(args.usr):
                args.usr = lambda orig_cb=args.usr, **kwargs: \
                    monitor_queue.put((orig_cb, [], kwargs))

        epics.ca._onMonitorEvent(args)

    # The dispatcher thread will stop if this event is set
    stop_event = threading.Event()
    monitor_queue = queue.Queue()

    # Re-route monitor events to our new handler
    epics.ca._CB_EVENT = ctypes.CFUNCTYPE(None, epics.dbr.event_handler_args)(monitor_event)

    # TODO this whole implementation should probably be a subclass of CAThread

    # Start up the dispatcher thread
    dispatcher_thread = epics.ca.CAThread(target=monitor_dispatcher,
                                          name='monitor_dispatcher',
                                          args=(monitor_queue, stop_event))

    dispatcher_thread.daemon = True
    dispatcher_thread.queue = monitor_queue
    dispatcher_thread.stop_event = stop_event
    dispatcher_thread.main_context = epics.ca.current_context()
    dispatcher_thread.start()

    return dispatcher_thread


def restore_monitor():
    epics.ca._CB_EVENT = ctypes.CFUNCTYPE(None,
                                          epics.dbr.event_handler_args)(epics.ca._onMonitorEvent)
