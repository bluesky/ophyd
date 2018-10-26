import atexit
import copy
import ctypes
import functools
import logging
import queue
import threading
import warnings

from types import SimpleNamespace

import epics
from epics import get_pv as _get_pv, caget, caput, ca, dbr  # noqa

try:
    ca.find_libca()
except ca.ChannelAccessException:
    thread_class = threading.Thread
else:
    thread_class = ca.CAThread


module_logger = logging.getLogger(__name__)
_dispatcher = None

if not hasattr(epics.dbr, '_cast_args'):
    # Stash a copy of the original cast args
    epics.dbr._cast_args = epics.dbr.cast_args


def get_pv(*args, **kwargs):
    kwargs.setdefault('context', ca.current_context())
    return _get_pv(*args, **kwargs)


class _DispatcherThread(threading.Thread):
    'A queue-based dispatcher thread which attaches to a specific CA context'

    def __init__(self, name, *, dispatcher):
        super().__init__(name=name)
        self.daemon = True
        self.context = dispatcher.main_context
        self._stop_event = dispatcher._stop_event
        self._timeout = dispatcher._timeout
        self.logger = dispatcher.logger
        self.queue = queue.Queue()

    def run(self):
        '''The dispatcher itself'''
        ca.attach_context(self.context)

        self.logger.debug('pyepics dispatcher thread %s started', self.name)
        while not self._stop_event.is_set():
            try:
                callback, args, kwargs = self.queue.get(True, self._timeout)
            except queue.Empty:
                ...
            else:
                try:
                    callback(*args, **kwargs)
                except Exception as ex:
                    self.logger.exception(
                        'Exception occurred during callback %r', callback
                    )

        self.logger.debug('pyepics dispatcher thread %s exiting', self.name)
        ca.detach_context()


class EventDispatcher:
    '''An event dispatcher which pokes at the internals of pyepics

    The monitor dispatcher works around having callbacks from libca threads.
    Using epics CA calls (caget, caput, etc.) from those callbacks is not
    possible without this dispatcher workaround.

    ... note::

       Without `all_contexts` set, only the callbacks that are run with
       the same context as the the main thread are affected.

    ... note::

       Ensure that you call epics.ca.use_initial_context() at startup in
       the main thread

    Parameters
    ----------
    all_contexts : bool, optional
        re-route _all_ callbacks from _any_ context to the dispatcher callback
        thread
    timeout : float, optional
    callback_logger : logging.Logger, optional
        A logger to notify about failed callbacks. If unspecified, this
        defaults to the module logger `ophyd._pyepics_shim`.

    Attributes
    ----------
    main_context : ctypes long
        The main CA context
    logger : logging.Logger
        A logger to notify about failed callbacks
    queue : Queue
        The event queue
    '''

    def __init__(self, all_contexts=False, timeout=0.1, callback_logger=None):
        self.get_put_thread = None
        self.monitor_thread = None
        self.connect_thread = None

        # The dispatcher thread will stop if this event is set
        self._stop_event = threading.Event()
        self.main_context = ca.current_context()
        self.logger = (callback_logger if callback_logger is not None
                       else module_logger)

        self._all_contexts = bool(all_contexts)
        self._timeout = timeout
        self._reroute_callbacks(True)

    def is_alive(self):
        return any(thread.is_alive() for thread in self.threads.values()
                   if thread is not None)

    @property
    def threads(self):
        return {'get_put_thread': self.get_put_thread,
                'monitor_thread': self.monitor_thread,
                'connect_thread': self.connect_thread,
                }

    def stop(self):
        '''Stop the dispatcher threads and re-enable normal callbacks'''
        self._stop_event.set()
        for attr, thread in self.threads.items():
            if thread is not None:
                thread.join()
                setattr(self, attr, None)
        self._reroute_callbacks(False)

    def _start_threads(self):
        'Start all dispatcher threads'
        for attr in self.threads:
            thread = _DispatcherThread(name=attr, dispatcher=self)
            thread.start()
            setattr(self, attr, thread)

    def _reroute_callbacks(self, enable):
        '''Re-route EPICS callbacks to our handler threads

        Parameters
        ----------
        enable : bool
            Enable/disable re-routing of callbacks
        '''
        if enable:
            connect = self._connect_event
            put = self._put_event
            get = self._get_event
            monitor = self._monitor_event
            access = self._access_rights_event
            self._start_threads()
            epics.dbr.cast_args = self._cast_args
        else:
            connect = ca._onConnectionEvent
            put = ca._onPutEvent
            get = ca._onGetEvent
            monitor = ca._onMonitorEvent
            access = ca._onAccessRightsEvent
            epics.dbr.cast_args = epics.dbr._cast_args

        ca._CB_CONNECT = ctypes.CFUNCTYPE(None, dbr.connection_args)(connect)
        ca._CB_PUTWAIT = ctypes.CFUNCTYPE(None, dbr.event_handler_args)(put)
        ca._CB_GET = ctypes.CFUNCTYPE(None, dbr.event_handler_args)(get)
        ca._CB_EVENT = ctypes.CFUNCTYPE(None, dbr.event_handler_args)(monitor)
        ca._CB_ACCESS = (
            ctypes.CFUNCTYPE(None, dbr.access_rights_handler_args)(access)
        )

    @property
    def applies_to_context(self):
        'Does this dispatcher work for the current Channel Access context?'
        current_context = ca.current_context()
        return (self._all_contexts or self.main_context == current_context)

    @staticmethod
    def _cast_args(args):
        'Replacement epics.dbr.cast_args - use pre-casted + copied args'
        try:
            return args._casted
        except AttributeError:
            return epics.dbr._cast_args(args)

    def _make_handler(thread_name, pyepics_func):
        @functools.wraps(pyepics_func)
        def wrapped(self, args):
            if self.applies_to_context:
                queue = getattr(self, thread_name).queue
                queue.put((pyepics_func, [args], {}))
            else:
                pyepics_func(args)
        return wrapped

    def _make_casting_handler(thread_name, pyepics_func):
        @functools.wraps(pyepics_func)
        def wrapped(self, args):
            if not self.applies_to_context:
                return pyepics_func(args)

            queue = getattr(self, thread_name).queue
            new_args = SimpleNamespace(
                usr=args.usr,
                chid=args.chid,
                type=args.type,
                count=args.count,
                status=args.status,
                raw_dbr=None,
                # in place of raw_dbr, we cast the args while the data is
                # accessible to python:
                _casted=copy.deepcopy(self._cast_args(args))
            )
            # TODO: the copy above could result in multiple copies of data,
            # affecting performance - workaround ideas?
            queue.put((pyepics_func, [new_args], {}))

        return wrapped

    _monitor_event = _make_casting_handler('monitor_thread',
                                           ca._onMonitorEvent)
    _connect_event = _make_handler('connect_thread',
                                   ca._onConnectionEvent)
    _access_rights_event = _make_handler('connect_thread',
                                         ca._onAccessRightsEvent)
    _put_event = _make_handler('get_put_thread', ca._onPutEvent)
    _get_event = _make_casting_handler('get_put_thread', ca._onGetEvent)


def setup(logger):
    '''Setup ophyd for use

    Must be called once per session using ophyd
    '''
    try:
        ca.find_libca()
        # if we can not find libca, then we clearly are not
        # going to be using CA threads so no need to install
        # the trampoline
    except ca.ChannelAccessException:
        return
    # It's important to use the same context in the callback dispatcher
    # as the main thread, otherwise not-so-savvy users will be very
    # confused
    global _dispatcher

    if _dispatcher is not None:
        logger.debug('ophyd already setup')
        return

    def _cleanup():
        '''Clean up the ophyd session'''
        global _dispatcher
        if _dispatcher is None:
            return

        logger.debug('Performing ophyd cleanup')
        if _dispatcher.is_alive():
            logger.debug('Joining the dispatcher thread')
            _dispatcher.stop()

        _dispatcher = None

        logger.debug('Finalizing libca')
        ca.finalize_libca()

    ca.use_initial_context()

    logger.debug('Installing event dispatcher')
    _dispatcher = EventDispatcher()
    atexit.register(_cleanup)
    return _dispatcher


def get_pv_form(version):
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
        except Exception:
            return None

        return version_tuple

    try:
        from pkg_resources import parse_version
    except ImportError:
        parse_version = _naive_parse_version

    version = parse_version(_fix_git_versioning(version))

    if version is None:
        warnings.warn('Unrecognized PyEpics version; using local timestamps',
                      ImportWarning)
        return 'native'

    elif version <= parse_version('3.2.3'):
        warnings.warn(
            ('PyEpics versions <= 3.2.3 will use local timestamps '
             '(version: %s)' % epics.__version__), ImportWarning)
        return 'native'
    else:
        return 'time'


pv_form = get_pv_form(epics.__version__)
