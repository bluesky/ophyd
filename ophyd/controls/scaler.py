from __future__ import print_function
import logging

from .signal import EpicsSignal
from .detector import SignalDetector
from ..utils.epics_pvs import record_field

logger = logging.getLogger(__name__)


class EpicsScaler(SignalDetector):
    '''SynApps Scaler Record interface'''
    def __init__(self, record, numchan=8, *args, **kwargs):
        self._record = record
        self._numchan = numchan

        super(EpicsScaler, self).__init__(*args, **kwargs)

        self.add_signal(EpicsSignal(record_field(record, 'CNT'),
                        alias='_count',
                        name=''.join([self.name, '_count'])),
                        recordable=False)
        self.add_signal(EpicsSignal(record_field(record, 'CONT'),
                        alias='_count_mode',
                        name=''.join([self.name, '_count_mode'])),
                        recordable=False)
        self.add_signal(EpicsSignal(record_field(record, 'T'),
                        alias='_time',
                        name=''.join([self.name, '_time'])))
        self.add_signal(EpicsSignal(record_field(record, 'TP'),
                        alias='_preset_time',
                        name=''.join([self.name, '_preset_time'])),
                        recordable=False, add_property=True)
        self.add_signal(EpicsSignal(record_field(record, 'TP1'),
                        alias='_auto_count_time',
                        name=''.join([self.name, '_auto_count_time'])),
                        recordable=False, add_property=True)

        for ch in range(1, numchan + 1):
            pv = '{}{}'.format(record_field(record, 'S'), ch)
            sig = EpicsSignal(pv, rw=False,
                              alias='_chan{}'.format(ch),
                              name='{}_chan{}'.format(self.name, ch))
            self.add_signal(sig, add_property=True)

            pv = '{}{}'.format(record_field(record, 'PR'), ch)
            sig = EpicsSignal(pv, rw=True,
                              alias='_preset{}'.format(ch),
                              name='{}_preset{}'.format(self.name, ch))
            self.add_signal(sig, add_property=True, recordable=False)

            pv = '{}{}'.format(record_field(record, 'G'), ch)
            sig = EpicsSignal(pv, rw=True,
                              alias='_gate{}'.format(ch),
                              name='{}_gate{}'.format(self.name, ch))
            self.add_signal(sig, add_property=True, recordable=False)

        self.add_acquire_signal(self._count)

    @property
    def auto_count(self):
        """Return the autocount status"""
        return (self._count_mode.value == 1)

    @auto_count.setter
    def auto_count(self, val):
        """Set the autocount status"""
        if val:
            self._count_mode.value = 1
        else:
            self._count_mode.value = 0

    def __repr__(self):
        repr = ['record={0._record!r}'.format(self),
                'numchan={0._numchan!r}'.format(self)]
        return self._get_repr(repr)

    def configure(self, **kwargs):
        """Configure Scaler

        Configure the scaler by setting autocount to off. The state will
        be restored by deconfigure

        """
        self._autocount = self._count_mode.value
        self._count_mode.value = 0

    def deconfigure(self, **kwargs):
        """Deconfigure Scaler

        Reset thet autocount status
        """
        self._count_mode.value = self._autocount
