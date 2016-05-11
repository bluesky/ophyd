import logging

import atexit
import epics
import time

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

__all__ = ['setup', 'logger']

_dispatcher = None


def setup():
    '''Setup ophyd for use

    Must be called once per session using ophyd
    '''
    # It's important to use the same context in the callback dispatcher
    # as the main thread, otherwise not-so-savvy users will be very
    # confused
    global _dispatcher

    if _dispatcher is not None:
        logger.debug('ophyd already setup')
        return

    epics.ca.use_initial_context()

    from .epics_pvs import MonitorDispatcher
    logger.debug('Installing monitor dispatcher')
    _dispatcher = MonitorDispatcher()
    atexit.register(_cleanup)
    return _dispatcher


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
