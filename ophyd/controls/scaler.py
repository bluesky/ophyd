from __future__ import print_function
import logging

from .signal import EpicsSignal
from .detector import SignalDetector
from ..utils.epics_pvs import record_field

logger = logging.getLogger(__name__)


class EpicsScaler(SignalDetector):
    '''SynApps Scaler Record interface'''
    def __init__(self, record, numchan=8, *args, **kwargs):
        super(EpicsScaler, self).__init__(*args, **kwargs)
        self._record = record
        self._numchan = numchan
        '''Which record fields do we need to expose here (minimally)?

        CNT     -- start/stop counting
        CONT    -- OneShot/AutoCount
        G1..16  -- Gate Control, Yes/No
        S1..16  -- Counts
        T       -- Elapsed time
        TP      -- Preset time (duration to count over)

        Eventually need to provide PR1..16 -- preset counts too.
        '''
        name = self.name
        signals = [EpicsSignal(record_field(record, 'CNT'),
                               alias='_count',
                               name=''.join([name, '_count'])),
                   EpicsSignal(record_field(record, 'CONT'),
                               alias='_count_mode',
                               name=''.join([name, '_count_mode'])),
                   EpicsSignal(record_field(record, 'T'),
                               alias='_time',
                               name=''.join([name, '_time'])),
                   EpicsSignal(record_field(record, 'TP'),
                               alias='_preset_time',
                               name=''.join([name, '_preset_time']))
                   ]

        for ch in range(1, numchan + 1):
            pv = '{}{}'.format(record_field(record, 'S'), ch)
            signals.append(EpicsSignal(pv, rw=False,
                                       alias='_chan{}'.format(ch),
                                       name='{}_chan{}'.format(name, ch)))

        for sig in signals:
            self.add_signal(sig)

        self._acq_signal = self._count

    def __repr__(self):
        repr = ['record={0._record!r}'.format(self),
                'numchan={0._numchan!r}'.format(self),
                ]

        return self._get_repr(repr)

    def configure(self, **kwargs):
        """Configure Scaler

        Configure the scaler by setting autocount to off. The state will
        be restored by deconfigure

        TODO: Could set acquisition time here
        """
        self._autocount = self._count_mode.value
        self._count_mode.value = 0

    def deconfigure(self, **kwargs):
        """Deconfigure Scaler

        Reset thet autocount status
        """
        self._count_mode.value = self._autocount
