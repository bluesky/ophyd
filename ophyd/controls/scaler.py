from __future__ import print_function
import logging

from collections import OrderedDict

from .signal import (EpicsSignal, EpicsSignalRO)
from .device import OphydDevice
from .device import (Component as C, DynamicComponent as DC)

logger = logging.getLogger(__name__)


def _scaler_fields(attr_base, field_base, range_, **kwargs):
    defn = OrderedDict()
    for i in range_:
        attr = '{attr}{i}'.format(attr=attr_base, i=i)
        suffix = '{field}{i}'.format(field=field_base, i=i)
        defn[attr] = (EpicsSignalRO, suffix, kwargs)

    return defn


class EpicsScaler(OphydDevice):
    '''SynApps Scaler Record interface'''

    count = C(EpicsSignal, '.CNT', trigger_value=1)
    count_mode = C(EpicsSignal, '.CONT', string=True)
    time = C(EpicsSignal, '.T')
    preset_time = C(EpicsSignal, '.TP')
    auto_count_time = C(EpicsSignal, '.TP1')
    channels = DC(_scaler_fields('chan', '.S', range(1, 33)))
    presets = DC(_scaler_fields('preset', '.PR', range(1, 33)))
    gates = DC(_scaler_fields('gate', '.G', range(1, 33)))

    def configure(self, state=None):
        """Configure Scaler

        Configure the scaler by setting autocount to off. The state will be
        restored by deconfigure
        """
        if state is None:
            state = {}
        self._old_count_mode = self._count_mode.get()
        self.count_mode.put(0)

    def deconfigure(self):
        """Deconfigure Scaler

        Reset the autocount status
        """
        self.count_mode.put(self._old_count_mode)
