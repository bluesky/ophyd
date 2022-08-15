import atexit
import logging
import threading

from caproto.threading import pyepics_compat
from caproto.threading.pyepics_compat import PV as _PV
from caproto.threading.pyepics_compat import caget, caput  # noqa

from ._dispatch import EventDispatcher, _CallbackThread, wrap_callback

thread_class = threading.Thread
module_logger = logging.getLogger(__name__)
_dispatcher = None
name = "caproto"


def get_dispatcher():
    "The event dispatcher for the caproto control layer"
    return _dispatcher


class CaprotoCallbackThread(_CallbackThread):
    ...


class PV(_PV):
    def __init__(
        self,
        pvname,
        callback=None,
        form="time",
        verbose=False,
        auto_monitor=None,
        count=None,
        connection_callback=None,
        connection_timeout=None,
        access_callback=None,
        context=None,
    ):
        connection_callback = wrap_callback(
            _dispatcher, "metadata", connection_callback
        )
        callback = wrap_callback(_dispatcher, "monitor", callback)
        access_callback = wrap_callback(_dispatcher, "metadata", access_callback)

        super().__init__(
            pvname,
            form=form,
            verbose=verbose,
            auto_monitor=auto_monitor,
            count=count,
            connection_timeout=connection_timeout,
            connection_callback=connection_callback,
            callback=callback,
            access_callback=access_callback,
            context=context,
        )

    def add_callback(
        self, callback=None, index=None, run_now=False, with_ctrlvars=True, **kw
    ):
        if not self.auto_monitor:
            self.auto_monitor = True
        callback = wrap_callback(_dispatcher, "monitor", callback)
        return super().add_callback(
            callback=callback,
            index=index,
            run_now=run_now,
            with_ctrlvars=with_ctrlvars,
            **kw
        )

    def put(
        self,
        value,
        wait=False,
        timeout=30.0,
        use_complete=False,
        callback=None,
        callback_data=None,
    ):
        if callback:
            use_complete = True
        callback = wrap_callback(_dispatcher, "get_put", callback)
        return super().put(
            value,
            wait=wait,
            timeout=timeout,
            use_complete=use_complete,
            callback=callback,
            callback_data=callback_data,
        )

    # TODO: caproto breaks API compatibility in wait_for_connection, raising TimeoutError

    def get_all_metadata_blocking(self, timeout):
        if self._args["status"] is None:
            self.get_timevars(timeout=timeout)
        self.get_ctrlvars(timeout=timeout)
        md = self._args.copy()
        md.pop("value", None)
        return md

    def get_all_metadata_callback(self, callback, *, timeout):
        def get_metadata_thread(pvname):
            md = self.get_all_metadata_blocking(timeout=timeout)
            callback(pvname, md)

        _dispatcher.schedule_utility_task(get_metadata_thread, pvname=self.pvname)

    def clear_callbacks(self):
        super().clear_callbacks()
        self.access_callbacks.clear()
        self.connection_callbacks.clear()

    def clear_auto_monitor(self):
        # TODO move into caproto
        self.auto_monitor = False
        if self._auto_monitor_sub is not None:
            self._auto_monitor_sub.clear()
            self._auto_monitor_sub = None


def release_pvs(*pvs):
    for pv in pvs:
        pv.clear_callbacks()
        # pv.disconnect()


def get_pv(
    pvname,
    form="time",
    connect=False,
    context=None,
    timeout=5.0,
    connection_callback=None,
    access_callback=None,
    callback=None,
    **kwargs
):
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
    if context is None:
        context = PV._default_context

    pv = PV(
        pvname,
        form=form,
        connection_callback=connection_callback,
        access_callback=access_callback,
        callback=callback,
        **kwargs
    )
    pv._reference_count = 0
    if connect:
        pv.wait_for_connection(timeout=timeout)
    return pv


def setup(logger):
    """Setup ophyd for use

    Must be called once per session using ophyd
    """
    # It's important to use the same context in the callback _dispatcher
    # as the main thread, otherwise not-so-savvy users will be very
    # confused
    global _dispatcher

    if _dispatcher is not None:
        logger.debug("ophyd already setup")
        return

    pyepics_compat._get_pv = pyepics_compat.get_pv
    pyepics_compat.get_pv = get_pv

    def _cleanup():
        """Clean up the ophyd session"""
        global _dispatcher
        if _dispatcher is None:
            return

        pyepics_compat.get_pv = pyepics_compat._get_pv

        if _dispatcher.is_alive():
            _dispatcher.stop()

        _dispatcher = None

    logger.debug("Installing event dispatcher")
    context = PV._default_context.broadcaster
    _dispatcher = EventDispatcher(
        thread_class=CaprotoCallbackThread, context=context, logger=logger
    )
    atexit.register(_cleanup)
    return _dispatcher
