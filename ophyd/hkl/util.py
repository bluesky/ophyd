from __future__ import print_function
import logging
import sys
import numpy as np

try:
    from gi.repository import Hkl as hkl_module
    from gi.repository import GLib
except ImportError as ex:
    hkl_module = None
    GLib = None

    print('[!!] Failed to import Hkl library; diffractometer support '
          'disabled ({})'.format(ex), file=sys.stderr)


logger = logging.getLogger(__name__)


def new_detector(dtype=0):
    '''
    Create a new HKL-library detector
    '''
    return hkl_module.Detector.factory_new(hkl_module.DetectorType(dtype))


if hkl_module:
    diffractometer_types = tuple(sorted(hkl_module.factories().keys()))
    UserUnits = hkl_module.UnitEnum.USER
    DefaultUnits = hkl_module.UnitEnum.DEFAULT

    units = {'user': UserUnits,
             'default': DefaultUnits
             }
else:
    diffractometer_types = ()
    units = {}


class UsingEngine(object):
    """
    Context manager that uses a calculation engine temporarily (i.e., for the
    duration of the context manager)
    """
    def __init__(self, calc, engine):
        self.calc = calc

    def __enter__(self):
        self.old_engine = self.calc.engine

    def __exit__(self, type_, value, traceback):
        if self.old_engine is not None:
            self.calc.engine = self.old_engine


def to_numpy(mat):
    """Convert an hkl ``Matrix`` to a numpy ndarray

    Parameters
    ----------
    mat : Hkl.Matrix

    Returns
    -------
    ndarray
    """
    if isinstance(mat, np.ndarray):
        return mat

    ret = np.zeros((3, 3))
    for i in range(3):
        for j in range(3):
            ret[i, j] = mat.get(i, j)

    return ret


def to_hkl(arr):
    """Convert a numpy ndarray to an hkl ``Matrix``

    Parameters
    ----------
    arr : ndarray

    Returns
    -------
    Hkl.Matrix
    """
    if isinstance(arr, hkl_module.Matrix):
        return arr

    arr = np.array(arr)

    hklm = hkl_euler_matrix(0, 0, 0)
    hklm.init(*arr.flatten())
    return hklm


def hkl_euler_matrix(euler_x, euler_y, euler_z):
    return hkl_module.Matrix.new_euler(euler_x, euler_y, euler_z)


def _gi_info(gi_val):
    def get(attr):
        try:
            getter = getattr(gi_val, attr)
            # inspect.signature doesn't work on gi functions...
            return getter()
        except Exception as ex:
            try:
                return getter(units['user'])
            except Exception:
                return '({}: {})'.format(ex.__class__.__name__, ex)

    return {attr: get(attr)
            for attr in dir(gi_val)
            if attr.endswith('_get')
            }
