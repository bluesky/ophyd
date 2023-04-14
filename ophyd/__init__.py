# type: ignore

import logging
import os
import types

from ophyd.log import set_handler  # noqa: F401

logger = logging.getLogger(__name__)

cl = None


def set_cl(control_layer=None, *, pv_telemetry=False):
    global cl
    known_layers = ("pyepics", "caproto", "dummy")

    if control_layer is None:
        control_layer = os.environ.get("OPHYD_CONTROL_LAYER", "any").lower()

    if control_layer == "any":
        for c_type in known_layers:
            try:
                set_cl(c_type, pv_telemetry=pv_telemetry)
            except ImportError:
                continue
            else:
                return
        else:
            raise ImportError("no valid control layer found")

    # TODO replace this with fancier meta-programming
    # TODO handle control_layer being a module/nampspace directly
    if control_layer == "pyepics":
        # If using pyepics and ophyd.v2 (p4p and aioca), need to use the same
        # libCom and libCa as provided by epicscorelibs
        # https://github.com/BCDA-APS/apstools/issues/836
        try:
            import epicscorelibs.path.pyepics  # noqa
        except ImportError:
            # No epicscorelibs, let pyepics use bundled CA
            pass
        from . import _pyepics_shim as shim
    elif control_layer == "caproto":
        from . import _caproto_shim as shim
    elif control_layer == "dummy":
        from . import _dummy_shim as shim
    else:
        raise ValueError("unknown control_layer")

    shim.setup(logger)

    exports = (
        "setup",
        "caput",
        "caget",
        "get_pv",
        "thread_class",
        "name",
        "release_pvs",
        "get_dispatcher",
    )
    # this sets the module level value
    cl = types.SimpleNamespace(**{k: getattr(shim, k) for k in exports})
    if pv_telemetry:
        from collections import Counter
        from functools import wraps

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
        raise RuntimeError("control layer not set, " "unsure how you got to this state")
    return cl


set_cl()

# Areadetector-related
from .areadetector import *  # noqa: F401, F402, E402, F403
from .device import (  # noqa: F401, F402, E402
    ALL_COMPONENTS,
    Component,
    Device,
    DynamicDeviceComponent,
    FormattedComponent,
    do_not_wait_for_lazy_connection,
    kind_context,
    wait_for_lazy_connection,
)
from .epics_motor import EpicsMotor, MotorBundle  # noqa: F401, F402, E402
from .mca import EpicsDXP, EpicsMCA  # noqa: F401, F402, E402
from .ophydobj import (  # noqa: F401, F402, E402
    Kind,
    register_instances_in_weakset,
    register_instances_keyed_on_name,
    select_version,
)

# Positioners
from .positioner import PositionerBase, SoftPositioner  # noqa: F401, F402, E402
from .pseudopos import PseudoPositioner, PseudoSingle  # noqa: F401, F402, E402
from .pv_positioner import (  # noqa: F401, F402, E402
    PVPositioner,
    PVPositionerDone,
    PVPositionerIsClose,
    PVPositionerPC,
)
from .quadem import APS_EM, NSLS_EM, QuadEM, TetrAMM  # noqa: F401, F402, E402

# Devices
from .scaler import EpicsScaler  # noqa: F401, F402, E402

# Signals
from .signal import (  # noqa: F401, F402, E402
    DerivedSignal,
    EpicsSignal,
    EpicsSignalNoValidation,
    EpicsSignalRO,
    Signal,
    SignalRO,
)
from .status import StatusBase, wait  # noqa: F401, F402, E402
from .utils.startup import setup as setup_ophyd  # noqa: F401, F402, E402

try:
    # Use live version from git
    from setuptools_scm import get_version

    # Warning: If the install is nested to the same depth, this will always succeed
    __version__ = get_version(root="..", relative_to=__file__)
    del get_version
except (ImportError, LookupError):
    # Use installed version
    from ._version import __version__  # noqa: F401
