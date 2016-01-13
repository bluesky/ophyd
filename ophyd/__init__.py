import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

from . import *


# Signals
from .signal import (Signal, EpicsSignal, EpicsSignalRO)

# Positioners
from .positioner import Positioner
from .epics_motor import EpicsMotor
from .pv_positioner import (PVPositioner, PVPositionerPC)
from .pseudopos import (PseudoPositioner, PseudoSingle)

# Devices
from .scaler import EpicsScaler
from .device import (Device, Component, DynamicDeviceComponent)
from .mca import EpicsMCA, EpicsDXP

# Areadetector-related
from .areadetector import *
from ._version import get_versions

from .commands import (mov, movr, set_pos, wh_pos, set_lm, log_pos,
                       log_pos_diff, log_pos_mov)

__version__ = get_versions()['version']
del get_versions
