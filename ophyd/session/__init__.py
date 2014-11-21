'''

'''
from __future__ import print_function
import sys
import logging
import signal

import epics

import atexit
from ophyd.utils.epics_pvs import MonitorDispatcher

LOG_FORMAT = "%(asctime)-15s [%(name)5s:%(levelname)s] %(message)s"
OPHYD_LOGGER = 'ophyd_session'


def get_session_manager():
    from .sessionmgr import SessionManager

    # TODO: Session manager singleton
    try:
        return SessionManager._instance
    except AttributeError:
        return None


def register_object(obj, set_vars=True):
    '''
    Register the object with the current running ophyd session.

    :param object obj: The object to register
    :param bool set_vars: If set, obj._session and obj._ses_logger
        are set to the current session and its associated logger.
    :return: The current session
    :rtype: :class:`SessionManager` or None
    '''
    ses = get_session_manager()

    if ses is None:
        # TODO setup additional logger when no session present?
        ses_logger = logger
    else:
        ses_logger = ses.register(obj)

    if set_vars:
        obj._session = ses
        obj._ses_logger = ses_logger

    return ses


def setup_epics():

    def stop_dispatcher():
        dispatcher.stop_event.set()

    # It's important to use the same context in the callback dispatcher
    # as the main thread, otherwise not-so-savvy users will be very
    # confused
    epics.ca.use_initial_context()
    dispatcher = MonitorDispatcher()

    atexit.register(stop_dispatcher)


def setup_loggers(logger_names, fmt=LOG_FORMAT):
    fmt = logging.Formatter(LOG_FORMAT)
    for name in logger_names:
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(fmt)
        logger.addHandler(handler)

# setup logging
setup_loggers((OPHYD_LOGGER, ))
logger = logging.getLogger(OPHYD_LOGGER)


def load_ipython_extension(ipython):
    print('Loading Ophyd Session Manager...')

    # config libca params
    setup_epics()

    from .sessionmgr import SessionManager
    #SessionManager will insert itself into ipython user namespace
    session_mgr = SessionManager(logger=logger, ipy=ipython)

    # import caget, caput, camonitor, cainfo
    from epics import (caget, caput, camonitor, cainfo)
    ipython.push('caget caput camonitor cainfo')

    # MAYBE? push signal handler into ipy.user_ns
    print('...Done loading Ophyd Session Manager')
