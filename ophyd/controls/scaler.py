from __future__ import print_function
import logging

from .signal import (EpicsSignal, EpicsSignalRO)
from ..utils.epics_pvs import raise_if_disconnected
from .device import OphydDevice
from .device import (Component as C, DynamicComponent as DC)

logger = logging.getLogger(__name__)


class EpicsScaler(OphydDevice):
    '''SynApps Scaler Record interface'''

    count = C(EpicsSignal, '.CNT', trigger_value=1)
    count_mode = C(EpicsSignal, '.CONT')
    time = C(EpicsSignal, '.T')
    preset_time = C(EpicsSignal, '.TP')
    auto_count_time = C(EpicsSignal, '.TP1')
    channels = DC(DC.make_def(EpicsSignalRO, 'chan{index}', '.S{index:d}',
                              range(1, 33)))
    # presets = DC('', DC.make_def(EpicsSignalRO, '.PR{index:d}')
    # gates = DC('', DC.make_def(EpicsSignalRO, '.G{index:d}')

    @property
    @raise_if_disconnected
    def count_time(self):
        return self.preset_time.value

    @count_time.setter
    @raise_if_disconnected
    def count_time(self, val):
        self.preset_time.put(val)

    @property
    @raise_if_disconnected
    def auto_count(self):
        """Return the autocount status"""
        return (self.count_mode.value == 1)

    @auto_count.setter
    @raise_if_disconnected
    def auto_count(self, val):
        """Set the autocount status"""
        if val:
            self.count_mode.value = 1
        else:
            self.count_mode.value = 0

    @raise_if_disconnected
    def configure(self, state=None):
        """Configure Scaler

        Configure the scaler by setting autocount to off. The state will be
        restored by deconfigure
        """
        if state is None:
            state = {}
        self._autocount = self._count_mode.value
        self.count_mode.value = 0

    @raise_if_disconnected
    def deconfigure(self):
        """Deconfigure Scaler

        Reset the autocount status
        """
        self.count_mode.value = self._autocount
