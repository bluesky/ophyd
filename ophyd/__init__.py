import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

from .controls import *
from .session import get_session_manager

from .commands import (mov, movr, set_pos, wh_pos, set_lm, log_pos,
                       log_pos_diff, log_pos_mov)

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
