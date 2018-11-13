'''
P4P TODO list

* Discuss with upstream
    1. There does not appear to be a way to monitor connection status outside
       of a value monitor
    2. No such thing as read/write access?
    3. Wrapping basic Python data types...
    4. pvRequest filters for monitoring data? pvRequest seems limited to a
       comma-delimited list of dotted fields
    5. Issue: '[13SIM1:Pva1:Image] warning : not a channel request'
       What does this mean/why is it not an exception we can catch?

* In this shim
    1. Support non-normative types (and attributes/etc with AD images)
    2. Process by default?
    3. pv_form has no meaning - we get all the information possible
'''

import atexit
import collections
import functools
import logging
import threading

from caproto.threading.pyepics_compat import PV as _PV, caput, caget  # noqa
from ._dispatch import _CallbackThread, EventDispatcher, wrap_callback
from .utils.epics_pvs import AlarmSeverity, AlarmStatus

import p4p
import p4p.client.thread
from p4p.nt import NTScalar, NTNDArray

PVInfo = collections.namedtuple('PVInfo', 'instances subscriptions')
thread_class = threading.Thread
pv_form = 'time'
module_logger = logging.getLogger(__name__)
_dispatcher = None
name = 'p4p'

_unwrap = {
    "epics:nt/NTScalar:1.0": NTScalar.unwrap,
    "epics:nt/NTScalarArray:1.0": NTScalar.unwrap,
    "epics:nt/NTNDArray:1.0": NTNDArray.unwrap,
}


class P4pCallbackThread(_CallbackThread):
    ...


def normative_type_to_dictionary(value):
    'Unpack a normative type value into a useful dictionary'
    pva_id = value.getID()
    try:
        unwrap_func = _unwrap[pva_id]
    except KeyError:
        # TODO: unhandled NT-types?
        return value
    else:
        ntype = unwrap_func(value)

    info = dict(pva_id=pva_id)
    ntype_dict = ntype.raw.todict()
    try:
        info['value'] = ntype_dict.pop('value')
    except KeyError:
        ...

    try:
        stamp = ntype_dict.pop('timeStamp')
    except KeyError:
        ...
    else:
        info['timestamp'] = stamp['secondsPastEpoch'] + 1.e-9 * stamp['nanoseconds']
        info['timestamp_user_tag'] = stamp['userTag']

    try:
        alarm = ntype_dict.pop('alarm')
    except KeyError:
        ...
    else:
        info['status'] = alarm['status']
        info['severity'] = alarm['severity']

    if len(ntype_dict):
        info['metadata'] = ntype_dict
        print(ntype_dict)
    return info


class P4pContext:
    def __init__(self):
        self.context = p4p.client.thread.Context(provider='pva', unwrap=False)
        self.lock = threading.RLock()
        # pvinfo is keyed on pvname -> PVInfo
        self.pvinfo = {}

    def release_pv(self, pv):
        pvinfo = self.pvinfo[pv.pvname]
        pvinfo.instances.pop(pv)
        if not len(pvinfo.instances):
            for sub in list(pvinfo.subscriptions):
                sub.close()
                pvinfo.subscriptions.pop(sub)
            self.pvinfo.pop(pv.pvname)

    def get_pv(self, pvname, *, connect, callback=None, form='time', verbose=False,
               auto_monitor=None, count=None, connection_callback=None,
               connection_timeout=None, access_callback=None):
        instance = NormativeTypePV(pvname, context=self, form=form,
                                   connection_callback=connection_callback,
                                   access_callback=access_callback)

        try:
            pvinfo = self.pvinfo[pvname]
        except KeyError:
            # For now, we use one subscription - for values + everything
            subscriptions = [
                self.context.monitor(
                    name=pvname,
                    cb=functools.partial(self._subscription_callback, pvname),
                    request=None, notify_disconnect=True)
            ]

            self.pvinfo[pvname] = PVInfo(
                instances=[instance],
                subscriptions=subscriptions,
            )
        else:
            pvinfo.instances.append(instance)

        return instance

    def _subscription_callback(self, pvname, value):
        try:
            pvinfo = self.pvinfo[pvname]
        except KeyError:
            return

        if not isinstance(value, Exception):
            try:
                value = normative_type_to_dictionary(value)
            except Exception as ex:
                value = {
                    'status': AlarmStatus.READ,
                    'severity': AlarmSeverity.MAJOR,
                }

        for instance in pvinfo.instances:
            if isinstance(value, Exception):
                instance._status_update(value)
            else:
                instance._monitor_update(value)

    def get(self, name, request=None, timeout=5.0, throw=True):
        '''
        Fetch current value of some number of PVs.

        Parameters
        ----------
        name: str
            A single name string or list of name strings
        request : str, p4p.Value, or None
            A p4p.Value or string to qualify this request, or None to use a
            default.
        timeout : float
            Operation timeout in seconds
        throw (bool):
            When true, operation error throws an exception. If False then the
            Exception is returned instead of the Value

        Returns
        -------
        A p4p.Value or Exception, or list of same. Subject to Automatic Value
        unwrapping.
        '''
        return self.context.get(name, request=request, timeout=timeout,
                                throw=throw)

    def put(self, name, values, *, request=None, timeout=5.0, throw=True,
            process=None, wait=None):
        '''Write a new value of some number of PVs.

        Parameters
        ----------
        name
            A single name string or list of name strings
        values
            A single value or a list of values
        request
            A :py:class:`p4p.Value` or string to qualify this request, or None to use a default.
        timeout
            Operation timeout in seconds
        throw
            When true, operation error throws an exception.  If False then the
            Exception is returned instead of the Value
        process
            Control remote processing.  May be 'true', 'false', 'passive', or None.
        wait
            Wait for all server processing to complete.

        Returns
        -------
        A None or Exception, or list of same

        When invoked with a single name then returns is a single value.
        When invoked with a list of name, then returns a list of values

        If 'wait' or 'process' is specified, then 'request' must be omitted or None.

        >>> ctxt = Context('pva')
        >>> ctxt.put('pv:name', 5.0)
        >>> ctxt.put(['pv:1', 'pv:2'], [1.0, 2.0])
        >>> ctxt.put('pv:name', {'value':5})
        >>>

        The provided value(s) will be automatically coerced to the target type.
        If this is not possible then an Exception is raised/returned.

        Unless the provided value is a dict, it is assumed to be a plain value
        and an attempt is made to store it in '.value' field.
        '''
        return self.context.put(name, values=values, request=request, timeout=timeout,
                                throw=throw, process=process, wait=wait)


class NormativeTypePV:
    '''Implements some functionality of a pyepics PV for backward-compatibility
    with EpicsSignal - but only with basic normative types.
    '''

    def __init__(self, pvname, *, context, callback=None, form='time', verbose=False,
                 auto_monitor=None, count=None, connection_callback=None,
                 connection_timeout=None, access_callback=None):
        self.context = context
        self._connect_event = threading.Event()
        self._callbacks = {}
        self._put_threads = []
        self._metadata = dict(
            pvname=pvname,
            value=None,
            write_access=True,
            read_access=True,
            timestamp=None,
            connected=False,
        )

        self.pvname = pvname
        self.form = form
        self.verbose = verbose
        self.auto_monitor = True
        self.count = count
        self.connection_timeout = connection_timeout
        self.connection_callback = wrap_callback(_dispatcher, 'metadata',
                                                 connection_callback)
        self.callback = callback
        self.access_callback = wrap_callback(_dispatcher, 'metadata',
                                             access_callback)

    def wait_for_connection(self, timeout=5):
        if not self._connect_event.wait(timeout):
            raise TimeoutError(f'Failed to connect within {timeout:.3f} sec')

    def _status_update(self, value):
        if isinstance(value, p4p.client.raw.Cancelled):
            ...
        elif isinstance(value, p4p.client.raw.Disconnected):
            self._connect_event.clear()
            self._metadata['connected'] = False
            self.connection_callback(self.pvname, conn=False, pv=self)

    def _monitor_update(self, info):
        if not self.connected:
            self._metadata['connected'] = True
            self._connect_event.set()
            self.access_callback(True, True, pv=self)
            self.connection_callback(self.pvname, conn=True, pv=self)

        # _metadata updated with potential keys:
        #   timestamp, timestamp_user_tag
        #   status, severity
        #   value
        #   pva_id (such as NTScalar)
        #   metadata
        self._metadata.update(**info)

        callback_data = dict(self._metadata)
        for cb, wrapped_cb in self._callbacks.items():
            wrapped_cb(**callback_data)

    def clear_callbacks(self):
        self._callbacks.clear()

    def add_callback(self, callback=None, run_now=False):
        self._callbacks[callback] = wrap_callback(_dispatcher, 'monitor',
                                                  callback)

    def get(self, count=None, as_string=False, as_numpy=True, timeout=None,
            with_ctrlvars=False, use_monitor=True):
        # TODO (or not?) use_monitor
        info = normative_type_to_dictionary(self.context.get(self.pvname, timeout=timeout))
        self._metadata.update(**info)
        return self._metadata['value']

    def put(self, value, wait=False, timeout=30.0, use_complete=False,
            callback=None, callback_data=None):
        if callback is not None or wait:
            callback = wrap_callback(_dispatcher, 'get_put', callback)
            if wait:
                self.context.put(self.pvname, values=value, timeout=timeout,
                                 wait=True)
            else:
                def put_thread():
                    self.context.put(self.pvname, values=value, timeout=timeout,
                                     wait=True)
                    callback()
                    self._put_threads.pop(thread)

                thread = threading.Thread(target=put_thread,
                                          daemon=True)
                self._put_threads.put(thread)
                thread.start()
        else:
            self.context.put(self.pvname, values=value, timeout=timeout,
                             wait=False)

    def release(self):
        self.context.release_pv(self)
        self._callbacks.clear()
        self.access_callback = None

    @property
    def metadata(self):
        return dict(self._metadata)

    @property
    def connected(self):
        return self._metadata['connected']

    @property
    def timestamp(self):
        return self._metadata['timestamp']

    @property
    def precision(self):
        return self._metadata.get('precision', None)

    def get_ctrlvars(self):
        'pyepics compat'
        ...

    def get_timevars(self):
        'pyepics compat'
        ...


def release_pvs(*pvs):
    for pv in pvs:
        pv.release()


def get_pv(pvname, form='time', connect=False, context=None, timeout=5.0,
           connection_callback=None, access_callback=None, callback=None,
           auto_monitor=None):
    """Get a PV from PV cache or create one if needed.

    Parameters
    ---------
    form : str, optional
        PV form: one of 'native' (default), 'time', 'ctrl'
    connect : bool, optional
        whether to wait for connection (default False)
    context : int, optional
        PV threading context (defaults to current context)
    timeout : float, optional
        connection timeout, in seconds (default 5.0)
    """
    context = _dispatcher.context
    return context.get_pv(pvname=pvname,
                          form=form,
                          connect=connect,
                          connection_timeout=timeout,
                          connection_callback=connection_callback,
                          access_callback=access_callback,
                          callback=callback,
                          auto_monitor=auto_monitor)


def setup(logger):
    'Setup p4p for use in ophyd'
    global _dispatcher

    if _dispatcher is not None:
        logger.debug('ophyd already setup')
        return

    def _cleanup():
        global _dispatcher
        if _dispatcher is None:
            return

        logger.debug('Performing p4p cleanup')
        if _dispatcher.is_alive():
            logger.debug('Joining the dispatcher thread')
            _dispatcher.stop()

        _dispatcher = None

    logger.debug('Installing event dispatcher')
    context = P4pContext()
    _dispatcher = EventDispatcher(thread_class=P4pCallbackThread,
                                  context=context, logger=logger)
    atexit.register(_cleanup)
    return _dispatcher
