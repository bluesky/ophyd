import logging
import types
import os
from ophyd.log import set_handler  # noqa: F401

logger = logging.getLogger(__name__)

cl = None


def set_cl(control_layer=None, *, pv_telemetry=False):
    global cl
    known_layers = ('pyepics', 'caproto', 'dummy')

    if control_layer is None:
        control_layer = os.environ.get('OPHYD_CONTROL_LAYER', 'any').lower()

    if control_layer == 'any':
        for c_type in known_layers:
            try:
                set_cl(c_type, pv_telemetry=pv_telemetry)
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

    shim.setup(logger)

    exports = ('setup', 'caput', 'caget', 'get_pv', 'thread_class', 'name',
               'release_pvs', 'get_dispatcher')
    # this sets the module level value
    cl = types.SimpleNamespace(**{k: getattr(shim, k)
                                  for k in exports})
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

from .ophydobj import (Kind, select_version,  # noqa: F401, F402, E402
                       register_instances_in_weakset,
                       register_instances_keyed_on_name)

# Signals
from .signal import (Signal, EpicsSignal, EpicsSignalRO, DerivedSignal)  # noqa: F401, F402, E402

# Positioners
from .positioner import (PositionerBase, SoftPositioner)  # noqa: F401, F402, E402
from .epics_motor import EpicsMotor, MotorBundle  # noqa: F401, F402, E402
from .pv_positioner import (PVPositioner, PVPositionerPC)  # noqa: F401, F402, E402
from .pseudopos import (PseudoPositioner, PseudoSingle)  # noqa: F401, F402, E402

# Devices
from .scaler import EpicsScaler  # noqa: F401, F402, E402
from .device import (Device, Component, FormattedComponent,  # noqa: F401, F402, E402
                     DynamicDeviceComponent, ALL_COMPONENTS, kind_context,
                     wait_for_lazy_connection, do_not_wait_for_lazy_connection)
from .status import StatusBase, wait  # noqa: F401, F402, E402
from .mca import EpicsMCA, EpicsDXP  # noqa: F401, F402, E402
from .quadem import QuadEM, NSLS_EM, TetrAMM, APS_EM  # noqa: F401, F402, E402

# Areadetector-related
from .areadetector import *  # noqa: F401, F402, E402, F403
from ._version import get_versions  # noqa: F402, E402

from .utils.startup import setup as setup_ophyd  # noqa: F401, F402, E402


__version__ = get_versions()['version']
del get_versions
