__version__ = 'v0.0.6'

import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

from .controls import *
from .session import get_session_manager

from commands import (mov, movr, set_pos, wh_pos, set_lm, log_pos,
                     log_pos_diff, log_pos_mov)

from scans import (Scan, Count, AScan, DScan)
