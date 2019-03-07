import atexit
import logging
import threading
import warnings

import epics
from epics import caget, caput, ca, dbr  # noqa

from ._dispatch import _CallbackThread, EventDispatcher, wrap_callback

try:
    ca.find_libca()
except ca.ChannelAccessException:
    raise ImportError('libca not found; pyepics is unavailable')
else:
    thread_class = ca.CAThread


module_logger = logging.getLogger(__name__)
name = 'pyepics'
_dispatcher = None


def get_dispatcher():
    'The event dispatcher for the pyepics control layer'
    return _dispatcher


class PyepicsCallbackThread(_CallbackThread):
    def attach_context(self):
        super().attach_context()
        ca.attach_context(self.context)

    def detach_context(self):
        super().detach_context()
        ca.detach_context()


class PyepicsShimPV(epics.PV):
    def __init__(self, pvname, callback=None, form='time', verbose=False,
                 auto_monitor=None, count=None, connection_callback=None,
                 connection_timeout=None, access_callback=None):
        self._get_lock = threading.Lock()
        self._ctrlvars_lock = threading.Lock()
        self._timevars_lock = threading.Lock()
        connection_callback = wrap_callback(_dispatcher, 'metadata',
                                            connection_callback)
        callback = wrap_callback(_dispatcher, 'monitor', callback)
        access_callback = wrap_callback(_dispatcher, 'metadata',
                                        access_callback)

        super().__init__(pvname, form=form, verbose=verbose,
                         auto_monitor=auto_monitor, count=count,
                         connection_timeout=connection_timeout,
                         connection_callback=connection_callback,
                         callback=callback, access_callback=access_callback)

    def get_ctrlvars(self, timeout=5, warn=True):
        "get control values for variable"
        with self._ctrlvars_lock:
            return super().get_ctrlvars(timeout=timeout, warn=warn)

    def get_timevars(self, timeout=5, warn=True):
        "get time values for variable"
        with self._timevars_lock:
            return super().get_timevars(timeout=timeout, warn=warn)

    def _configure_auto_monitor(self):
        if self._monref is not None:
            return

        # Not auto-monitoring; need to set up the internal monitor before
        # subscriptions can be used
        if not self.auto_monitor:
            self.auto_monitor = ca.DEFAULT_SUBSCRIPTION_MASK

        if self.connected:
            self.force_connect(pvname=self.pvname, chid=self.chid, conn=True)

    def add_callback(self, callback=None, index=None, run_now=False,
                     with_ctrlvars=True, **kw):
        self._configure_auto_monitor()
        callback = wrap_callback(_dispatcher, 'monitor', callback)
        return super().add_callback(callback=callback, index=index,
                                    run_now=run_now,
                                    with_ctrlvars=with_ctrlvars, **kw)

    def get_with_metadata(self, count=None, as_string=False, as_numpy=True,
                          timeout=None, with_ctrlvars=False, form=None,
                          use_monitor=True):
        with self._get_lock:
            return super().get_with_metadata(
                count=count, as_string=as_string, as_numpy=as_numpy,
                timeout=timeout, with_ctrlvars=with_ctrlvars, form=form,
                use_monitor=use_monitor)

    def put(self, value, wait=False, timeout=30.0, use_complete=False,
            callback=None, callback_data=None):
        callback = wrap_callback(_dispatcher, 'get_put', callback)
        return super().put(value, wait=wait, timeout=timeout,
                           use_complete=use_complete, callback=callback,
                           callback_data=callback_data)

    def _getarg(self, arg):
        "wrapper for property retrieval"
        if self._args[arg] is None:
            if arg in ('status', 'severity', 'timestamp', 'posixseconds',
                       'nanoseconds'):
                self.get_timevars(timeout=1, warn=False)
            else:
                self.get_ctrlvars(timeout=1, warn=False)
        return self._args.get(arg, None)

    def get_all_metadata_blocking(self, timeout):
        if self._args['status'] is None:
            self.get_timevars(timeout=timeout)
        self.get_ctrlvars(timeout=timeout)
        md = self._args.copy()
        md.pop('value', None)
        return md

    def get_all_metadata_callback(self, callback, *, timeout):
        def get_metadata_thread(pvname):
            md = self.get_all_metadata_blocking(timeout=timeout)
            callback(pvname, md)

        _dispatcher.schedule_utility_task(get_metadata_thread,
                                          pvname=self.pvname)

    def clear_callbacks(self):
        super().clear_callbacks()
        self.access_callbacks.clear()
        self.connection_callbacks.clear()


def release_pvs(*pvs):
    # Run _release_pvs in the 'monitor' thread, assuring that the CA context is correct
    def _release_pvs():
        for pv in pvs:
            pv.clear_callbacks()
            pv.clear_auto_monitor()
        event.set()

    event = threading.Event()
    _dispatcher.get_thread_context('monitor').run(_release_pvs)
    event.wait()


def get_pv(pvname, form='time', connect=False, context=None, timeout=5.0,
           connection_callback=None, access_callback=None, callback=None,
           **kwargs):
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
    if form not in ('native', 'time', 'ctrl'):
        form = 'native'

    if context is None:
        context = ca.current_context()

    thispv = None

    # TODO: this needs some work.
    # thispv = epics.pv._PVcache_.get((pvname, form, context))
    # if thispv is not None:
    #     if callback is not None:
    #         # wrapping is taken care of by `add_callback`
    #         thispv.add_callback(callback)
    #     if access_callback is not None:
    #         access_callback = wrap_callback(_dispatcher, 'metadata',
    #                                         access_callback)
    #         thispv.access_callbacks.append(access_callback)
    #     if connection_callback is not None:
    #         connection_callback = wrap_callback(_dispatcher, 'metadata',
    #                                             connection_callback)
    #         thispv.connection_callbacks.append(connection_callback)
    #     if thispv.connected:
    #         if connection_callback:
    #             thispv.force_connect()
    #         if access_callback:
    #             thispv.force_read_access_rights()

    if thispv is None:
        thispv = PyepicsShimPV(pvname, form=form, callback=callback,
                               connection_callback=connection_callback,
                               access_callback=access_callback, **kwargs)

    if connect:
        if not thispv.wait_for_connection(timeout=timeout):
            ca.write('cannot connect to %s' % pvname)
    return thispv


def setup(logger):
    '''Setup ophyd for use

    Must be called once per session using ophyd
    '''
    # It's important to use the same context in the callback _dispatcher
    # as the main thread, otherwise not-so-savvy users will be very
    # confused
    global _dispatcher

    if _dispatcher is not None:
        logger.debug('ophyd already setup')
        return

    epics._get_pv = epics.get_pv
    epics.get_pv = get_pv
    epics.pv.get_pv = get_pv

    def _cleanup():
        '''Clean up the ophyd session'''
        global _dispatcher
        if _dispatcher is None:
            return
        epics.get_pv = epics._get_pv
        epics.pv.get_pv = epics._get_pv

        logger.debug('Performing ophyd cleanup')
        if _dispatcher.is_alive():
            logger.debug('Joining the dispatcher thread')
            _dispatcher.stop()

        _dispatcher = None

    logger.debug('Installing event dispatcher')
    _dispatcher = EventDispatcher(thread_class=PyepicsCallbackThread,
                                  context=ca.current_context(), logger=logger)
    atexit.register(_cleanup)
    return _dispatcher


def _check_pyepics_version(version):
    '''Verify compatibility with the pyepics version installed

    For proper functionality, ophyd requires pyepics >= 3.3.2
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
        except Exception:
            return None

        return version_tuple

    try:
        from pkg_resources import parse_version
    except ImportError:
        parse_version = _naive_parse_version

    try:
        version = parse_version(_fix_git_versioning(version))
    except Exception:
        version = None

    if version is None:
        warnings.warn('Unrecognized PyEpics version; assuming it is '
                      'compatible', ImportWarning)
    elif version < parse_version('3.3.2'):
        raise RuntimeError(f'The installed version of pyepics={version} is not'
                           f'compatible with ophyd.  Please upgrade to the '
                           f'latest version.')


_check_pyepics_version(getattr(epics, '__version__', None))
