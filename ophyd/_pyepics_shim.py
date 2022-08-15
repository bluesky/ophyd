import atexit
import logging

import epics
from epics import ca, caget, caput
from packaging.version import parse

from ._dispatch import EventDispatcher, _CallbackThread, wrap_callback

_min_pyepics = "3.4.2"

if parse(epics.__version__) < parse(_min_pyepics):
    raise ImportError(
        "Version of pyepics too old. "
        f"Ophyd requires at least {_min_pyepics}"
        f"but {epics.__version__} is installed"
    )

try:
    ca.find_libca()
except ca.ChannelAccessException:
    raise ImportError("libca not found; pyepics is unavailable")
else:
    thread_class = ca.CAThread


module_logger = logging.getLogger(__name__)
name = "pyepics"
_dispatcher = None
get_pv = epics.get_pv


def get_dispatcher():
    "The event dispatcher for the pyepics control layer"
    return _dispatcher


class PyepicsCallbackThread(_CallbackThread):
    def attach_context(self):
        super().attach_context()
        ca.attach_context(self.context)

    def detach_context(self):
        super().detach_context()
        if ca.current_context() is not None:
            ca.detach_context()


class PyepicsShimPV(epics.PV):
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
        )

        self._cache_key = (pvname, form, self.context)
        self._reference_count = 0

    def add_callback(
        self, callback=None, index=None, run_now=False, with_ctrlvars=True, **kw
    ):
        if not self.auto_monitor:
            self.auto_monitor = ca.DEFAULT_SUBSCRIPTION_MASK
        callback = wrap_callback(_dispatcher, "monitor", callback)
        return super().add_callback(
            callback=callback,
            index=index,
            run_now=run_now,
            with_ctrlvars=with_ctrlvars,
            **kw,
        )

    def put(
        self,
        value,
        wait=False,
        timeout=None,
        use_complete=False,
        callback=None,
        callback_data=None,
    ):
        callback = wrap_callback(_dispatcher, "get_put", callback)
        # pyepics does not accept an indefinite timeout
        if timeout is None:
            timeout = 315569520  # ten years
        return super().put(
            value,
            wait=wait,
            timeout=timeout,
            use_complete=use_complete,
            callback=callback,
            callback_data=callback_data,
        )

    def _getarg(self, arg):
        "wrapper for property retrieval"
        # NOTE: replaces epics.PV._getarg: does not call get() when value unset
        if self._args[arg] is None:
            if arg in (
                "status",
                "severity",
                "timestamp",
                "posixseconds",
                "nanoseconds",
            ):
                self.get_timevars(timeout=1, warn=False)
            else:
                self.get_ctrlvars(timeout=1, warn=False)
        return self._args.get(arg, None)

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


def release_pvs(*pvs):
    for pv in pvs:
        pv._reference_count -= 1
        if pv._reference_count == 0:
            pv.clear_callbacks()
            pv.clear_auto_monitor()
            if pv.chid is not None:
                # Clear the channel on the CA-level
                epics.ca.clear_channel(pv.chid)

            pv.chid = None
            pv.context = None

            # Ensure we don't get this same PV back again
            epics.pv._PVcache_.pop(pv._cache_key, None)


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

    epics.pv.default_pv_class = PyepicsShimPV

    def _cleanup():
        """Clean up the ophyd session"""
        global _dispatcher
        if _dispatcher is None:
            return
        epics.pv.default_pv_class = epics.PV

        if _dispatcher.is_alive():
            _dispatcher.stop()

        _dispatcher = None

    logger.debug("Installing event dispatcher")
    _dispatcher = EventDispatcher(
        thread_class=PyepicsCallbackThread, context=ca.current_context(), logger=logger
    )
    atexit.register(_cleanup)
    return _dispatcher


__all__ = (
    "setup",
    "caput",
    "caget",
    "get_pv",
    "thread_class",
    "name",
    "release_pvs",
    "get_dispatcher",
)
