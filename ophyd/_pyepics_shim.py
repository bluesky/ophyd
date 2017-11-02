import atexit
import ctypes
import epics
import queue
import threading
import warnings

from epics import get_pv as _get_pv, caget, caget, caput

try:
    epics.ca.find_libca()
except epics.ca.ChannelAccessException:
    thread_class = threading.Thread
else:
    thread_class = epics.ca.CAThread


_dispatcher = None


def get_pv(*args, **kwargs):
    import epics
    kwargs.setdefault('context', epics.ca.current_context())
    return _get_pv(*args, **kwargs)


class MonitorDispatcher(epics.ca.CAThread):
    '''A monitor dispatcher which works with pyepics

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

        epics.ca._CB_EVENT = (
            ctypes.CFUNCTYPE(None, epics.dbr.event_handler_args)(fcn))

    def _monitor_event(self, args):
        if (self._all_contexts or
                self.main_context == epics.ca.current_context()):
            if callable(args.usr):
                if (not hasattr(args.usr, '_disp_tag') or
                        args.usr._disp_tag is not self):
                    args.usr = lambda orig_cb=args.usr, **kwargs: \
                        self.queue.put((orig_cb, [], kwargs))
                    args.usr._disp_tag = self

        return epics.ca._onMonitorEvent(args)


def setup(logger):
    '''Setup ophyd for use

    Must be called once per session using ophyd
    '''
    try:
        epics.ca.find_libca()
        # if we can not find libca, then we clearly are not
        # going to be using CA threads so no need to install
        # the trampoline
    except epics.ca.ChannelAccessException:
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
            _dispatcher.join()

        _dispatcher = None

        logger.debug('Finalizing libca')
        epics.ca.finalize_libca()

    epics.ca.use_initial_context()

    logger.debug('Installing monitor dispatcher')
    _dispatcher = MonitorDispatcher()
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
        warnings.warn('PyEpics versions <= 3.2.3 will use local timestamps (version: %s)' %
                      epics.__version__,
                      ImportWarning)
        return 'native'
    else:
        return 'time'


pv_form = get_pv_form(epics.__version__)
