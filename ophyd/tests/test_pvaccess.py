import logging
import time
import copy
import pytest

from ophyd import (Signal, EpicsSignal, EpicsSignalRO, DerivedSignal,
                   get_cl, set_cl)
from ophyd.areadetector import SimDetectorCam
from ophyd.areadetector.plugins import PluginBase
from ophyd.status import wait


logger = logging.getLogger(__name__)


@pytest.fixture(scope='module')
def cl_p4p():
    set_cl('p4p')
    return get_cl()


@pytest.fixture(scope='module')
def cl_pyepics():
    set_cl('pyepics')
    return get_cl()


@pytest.fixture
def pva_areadetector_prefix(cleanup, cl_pyepics):
    prefix = '13SIM1:'
    sig = EpicsSignalRO(f'{prefix}Pva1:PluginType_RBV')
    cleanup.add(sig)

    try:
        if not sig.get().startswith('NDPluginPva'):
            raise TypeError('skip me')
    except (TimeoutError, TypeError):
        raise pytest.skip('areaDetector pva plugin unavailable')
    else:
        return prefix


@pytest.fixture(scope='function')
def pva_image_signal(cleanup, cl_p4p, pva_areadetector_prefix):
    set_cl('pyepics')
    cam = SimDetectorCam(f'{pva_areadetector_prefix}cam1:', name='cam')
    cleanup.add(cam)
    cam.wait_for_connection()

    plugin = PluginBase(f'{pva_areadetector_prefix}Pva1:', name='PvaPlugin')
    cleanup.add(plugin)
    plugin.wait_for_connection()

    plugin.enable.put(1, wait=True)
    cam.acquire_time.put(0.001, wait=True)
    cam.acquire_period.put(0.001, wait=True)
    cam.image_mode.put(0, wait=True)
    cam.acquire.put(1)

    sig = EpicsSignalRO(f'{pva_areadetector_prefix}Pva1:Image', name='image',
                        cl=cl_p4p)
    cleanup.add(sig)

    sig.wait_for_connection()
    return sig


def test_get(pva_image_signal):
    image = pva_image_signal.get()
    print(image)
    assert len(image.shape) == 2
