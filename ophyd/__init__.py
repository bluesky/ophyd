import logging
import types
import os

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

cl = None


def set_cl(control_layer=None, *, pv_telemetry=False):
    global cl
    known_layers = ('pyepics', 'caproto', 'dummy')

    if control_layer is None:
        control_layer = os.environ.get('OPHYD_CONTROL_LAYER', 'any').lower()

    if control_layer == 'any':
        for c_type in known_layers:
            try:
                set_cl(c_type)
            except ImportError:
                continue
            else:
                return
        else:
            raise ImportError('no valid control layer found')

    # TODO replace this with fancier meta-programming
    # TODO handle control_layer being a module/nampspace directly
    if control_layer == 'pyepics':
        from . import _pyepics_shim as shim
    elif control_layer == 'caproto':
        from . import _caproto_shim as shim
    elif control_layer == 'dummy':
        from . import _dummy_shim as shim
    else:
        raise ValueError('unknown control_layer')

    exports = ('setup', 'caput', 'caget', 'get_pv', 'pv_form', 'thread_class')
    # this sets the module level value
    cl = types.SimpleNamespace(**{k: getattr(shim, k)
                                  for k in exports})
    cl.setup(logger)
    if pv_telemetry:
        from functools import wraps
        from collections import Counter

        def decorate_get_pv(func):
            c = Counter()

            @wraps(func)
            def get_pv(pvname, *args, **kwargs):
                c[pvname] += 1
                return func(pvname, *args, **kwargs)
            get_pv.counter = c
            return get_pv

        cl.get_pv = decorate_get_pv(cl.get_pv)


def get_cl():
    if cl is None:
        raise RuntimeError("control layer not set, "
                           "unsure how you got to this state")
    return cl


set_cl()

from .ophydobj import Kind

# Signals
from .signal import (Signal, EpicsSignal, EpicsSignalRO, DerivedSignal)

# Positioners
from .positioner import (PositionerBase, SoftPositioner)
from .epics_motor import EpicsMotor, MotorBundle
from .pv_positioner import (PVPositioner, PVPositionerPC)
from .pseudopos import (PseudoPositioner, PseudoSingle)

# Devices
from .scaler import EpicsScaler
from .device import (Device, Component, FormattedComponent,
                     DynamicDeviceComponent,
                     ALL_COMPONENTS, kind_context)
from .status import StatusBase
from .mca import EpicsMCA, EpicsDXP
from .quadem import QuadEM, NSLS_EM, TetrAMM, APS_EM

# Areadetector-related
from .areadetector import *
from ._version import get_versions

from .utils.startup import setup as setup_ophyd


__version__ = get_versions()['version']
del get_versions
