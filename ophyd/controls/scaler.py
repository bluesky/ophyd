from __future__ import print_function
import logging

from ..utils.epics_pvs import raise_if_disconnected
from .descriptors import (DevSignal, DevSignalRO, DevSignalRange)
from .device import OphydDevice

logger = logging.getLogger(__name__)


class EpicsScaler(OphydDevice):
    '''SynApps Scaler Record interface'''
    def _get_range(self, devsig):
        return range(self._chan_start,
                     self._numchan + self._chan_start)

    count = DevSignal('.CNT', trigger=1)
    count_mode = DevSignal('.CONT')
    time = DevSignal('.T')
    preset_time = DevSignal('.TP')
    auto_count_time = DevSignal('.TP1')
    channels = DevSignalRange(DevSignalRO, '.S{index:d}',
                              range_=_get_range)
    presets = DevSignalRange(DevSignal, '.PR{index:d}', range_=_get_range)
    gates = DevSignalRange(DevSignal, '.G{index:d}', range_=_get_range)

    def __init__(self, record, numchan=8, chan_start=1, **kwargs):
        self._record = record
        self._numchan = numchan
        self._chan_start = chan_start

        super().__init__(record, **kwargs)

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

    def __repr__(self):
        repr = ['record={0._record!r}'.format(self),
                'numchan={0._numchan!r}'.format(self)]
        return self._get_repr(repr)

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
