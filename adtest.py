from __future__ import print_function

import logging
import unittest

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

import epics

from ophyd.controls import OphydDevice
from ophyd.controls import (SimDetector, TIFFPlugin)
from ophyd.controls.device import (Component as Cpt, )
from ophyd.controls.signal import Signal
logger = logging.getLogger(__name__)


class MyDetector(SimDetector):
    tiff1 = Cpt(TIFFPlugin, 'TIFF1:')


prefix = 'XF:31IDA-BI{Cam:Tbl}'
det = MyDetector(prefix)

print(det.describe())
print(det.tiff1.capture.describe())


class FakeSignal(Signal):
    def __init__(self, read_pv, *, name=None, parent=None):
        self.read_pv = read_pv
        super().__init__(name=name, parent=parent)

    def get(self):
        return self.name


class SubDevice(OphydDevice):
    cpt1 = Cpt(FakeSignal, '1', lazy=True)
    cpt2 = Cpt(FakeSignal, '2', lazy=True)
    cpt3 = Cpt(FakeSignal, '3', lazy=True)


class MyDevice(OphydDevice):
    sub_cpt1 = Cpt(SubDevice, '1')
    sub_cpt2 = Cpt(SubDevice, '2')
    cpt3 = Cpt(FakeSignal, '3')


device = MyDevice('prefix')

# compare device.sub_cpt.signal_names vs det.tiff1.signal_names
# with the 'test block' in device.py commented and otherwise
