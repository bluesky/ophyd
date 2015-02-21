from __future__ import print_function
import logging
import time

from .signal import EpicsSignal
from .detector import Detector

logger = logging.getLogger(__name__)


class EpicsScaler(Detector):
    '''SynApps Scaler Record interface

    Parameters
    ----------
    record : str
        The scaler record prefix
    numchan : int, optional
        The number of channels to use
    '''

    def __init__(self, record, numchan=8, *args, **kwargs):
        self._record = record
        self._numchan = numchan
        super(EpicsScaler, self).__init__(*args, **kwargs)
        '''Which record fields do we need to expose here (minimally)?

        CNT     -- start/stop counting
        CONT    -- OneShot/AutoCount
        G1..16  -- Gate Control, Yes/No
        NM1..16 -- Channel 1..16 Name
        S1..16  -- Counts
        T       -- Elapsed time
        TP      -- Preset time (duration to count over)

        Eventually need to provide PR1..16 -- preset counts too.
        '''
        signals = [EpicsSignal(self._field_pv('CNT'),
                               alias='_count_ctl',
                               name=''.join([self.name, '_cnt'])),
                   EpicsSignal(self._field_pv('CONT'),
                               alias='_count_mode',
                               name=''.join([self.name, '_cont'])),
                   EpicsSignal(self._field_pv('T'),
                               alias='_elapsed_time',
                               name=''.join([self.name, '_t'])),
                   EpicsSignal(self._field_pv('TP'),
                               alias='_preset_time',
                               name=''.join([self.name, '_preset']))
                   ]

        # create the 'S1..numchan' channel count Signals (read-only)
        ch_names = []
        for ch in range(1, numchan + 1):
            name = '{}{}'.format(self._field_pv('S'), ch)
            ch_names.append(EpicsSignal(name, rw=False,
                            name=''.join([self.name, '_s', str(ch)]),
                            alias=''.join(['_ch', str(ch), '_count'])))
        signals += ch_names

        for sig in signals:
            self.add_signal(sig)

    def _field_pv(self, field):
        return '{}.{}'.format(self._record, field)

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

    def acquire(self, **kwargs):
        """Start the scaler counting and return status

        Returns
        -------
        DetectorStatus : Status of detector
        """

        def done_counting(**kwargs):
            self._done_acquiring()

        self._count_ctl.put(1, wait=False,
                            callback=done_counting)
        return Detector.acquire(self, **kwargs)

    def read(self, **kwargs):
        '''Trigger a counting period and return all or selected channels.

        Returns
        -------
        channel_dict : dict
            Where channel numbers are the keys and values are the counts,
            i.e., {channel_x: counts}
        '''
        channels = range(1, self._numchan + 1)

        rtn = {}
        for ch in channels:
            sig = getattr(self, '_ch{}_count'.format(ch))
            rtn.update({sig.name: {'value': sig.value,
                                  'timestamp': sig.timestamp}})
        return rtn
