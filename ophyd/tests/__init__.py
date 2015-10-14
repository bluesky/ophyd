from __future__ import print_function
import sys
import logging
import unittest

import epics

from ophyd.session import get_session_manager
from ophyd.session.sessionmgr import SessionManager

logger = logging.getLogger('ophyd_session_test')


def setup_package():
    session = get_session_manager()
    session.cas.prefix = '{__TEST__}'


def teardown_package():
    session = get_session_manager()
    session._cleanup()


def get_caserver():
    return get_session_manager().cas


def main(is_main):
    # fmt = '%(asctime)-15s [%(levelname)s] %(message)s'
    # logging.basicConfig(format=fmt, level=logging.DEBUG)
    epics.ca.use_initial_context()

    OPHYD_LOGGER = 'ophyd_session'
    logger = logging.getLogger(OPHYD_LOGGER)
    logger.setLevel(logging.INFO)

    if is_main:
        setup_package()
        unittest.main()
        teardown_package()
