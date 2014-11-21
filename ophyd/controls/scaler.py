from __future__ import print_function
import logging
import time

from .signal import (SignalGroup, EpicsSignal)
from ..utils.epics_pvs import record_field


logger = logging.getLogger(__name__)


class EpicsScaler(SignalGroup):

    def __init__(self, record, numchan=8, *args, **kwargs):
        '''SynApps Scaler Record interface.'''
        self._record = record
        self._numchan = numchan

        SignalGroup.__init__(self, *args, **kwargs)

        '''
        Which record fields do we need to expose here (minimally)?

        CNT     -- start/stop counting
        CONT    -- OneShot/AutoCount
        G1..16  -- Gate Control, Yes/No
        NM1..16 -- Channel 1..16 Name
        S1..16  -- Counts
        T       -- Elapsed time
        TP      -- Preset time (duration to count over)

        Eventually need to provide PR1..16 -- preset counts too.
        '''
        signals = [EpicsSignal(record_field(record, 'CNT'),
                                alias='_count_ctl'),
                   EpicsSignal(record_field(record, 'CONT'),
                                alias='_count_mode'),
                   EpicsSignal(record_field(record, 'T'),
                                alias='_elapsed_time'),
                   EpicsSignal(record_field(record, 'TP'),
                                alias='_preset_time')
                  ]

        # create the 'NM1..numchan' channel name Signals
        ch_names = []
        for ch in range(1, numchan + 1):
            name = ''.join([record_field(record, 'NM'), str(ch)])
            ch_names.append(EpicsSignal(name,
                            alias=''.join(['_ch', str(ch), '_name'])))
        signals += ch_names
        # create the 'S1..numchan' channel count Signals (read-only)
        ch_names = []
        for ch in range(1, numchan + 1):
            name = ''.join([record_field(record, 'S'), str(ch)])
            ch_names.append(EpicsSignal(name, rw=False,
                            alias=''.join(['_ch', str(ch), '_count'])))
        signals += ch_names

        for sig in signals:
            self.add_signal(sig)

    def start(self):
        self._count_ctl._set_request(1, wait=False)

    # TODO: should this be a non-blocking write?
    # TODO: should writes be non-blocking by default?
    def stop(self):
        self._count_ctl.request = 0

    @property
    def count_mode(self):
        return self._count_mode.value

    @count_mode.setter
    def count_mode(self, mode):
        self._count_mode.request = mode

    @property
    def preset_time(self):
        return self._preset_time.value

    @preset_time.setter
    def preset_time(self, time):
        self._preset_time.request = time

    def read(self, channels=None):
        '''
        Trigger a counting period and return all or selected channels.

        :param channels: a tuple enumerating the channels to return.
        :returns: a dict {channel x: counts,}
        '''
        # Block waiting for counting to complete
        self._count_ctl._set_request(1, wait=True)

        if channels is None:
            channels = range(1, self._numchan + 1)

        # TODO: super-F'ugly... Add synchronous 'gets' in symmetry
        # with the sync-puts (put-completion)
        time.sleep(0.005)

        return {ch: getattr(self, '_ch%s_count' % ch).value for ch in channels}
