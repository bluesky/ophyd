from __future__ import print_function
import logging
import time

from .signal import (SignalGroup, EpicsSignal, OpTimeoutError)


logger = logging.getLogger(__name__)


class Scaler(SignalGroup):
    
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
        NM1..16 -- Channel 1..16 Name. Would be nice to map these to getter...
        S1..16  -- Counts
        T       -- Elapsed time
        TP      -- Preset time (duration to count over)

        Eventually need to provide PR1..16 -- preset counts too.
        ''' 
        signals = [EpicsSignal(self._field_pv('CNT'), alias='_count_ctl'),
                   EpicsSignal(self._field_pv('CONT'), alias='_count_mode'),
                   EpicsSignal(self._field_pv('T'), alias='_elapsed_time'),
                   EpicsSignal(self._field_pv('TP'), alias='_preset_time')
                  ]

        # create the 'NM1..numchan' channel name Signals
        ch_names = []
        for ch in range(1,numchan+1):
            name = ''.join([self._field_pv('NM'), str(ch)])
            ch_names.append(EpicsSignal(name, 
                            alias=''.join(['_ch',str(ch),'_name'])))
        signals += ch_names
        # create the 'S1..numchan' channel count Signals (read-only)
        ch_names = []
        for ch in range(1,numchan+1):
            name = ''.join([self._field_pv('S'), str(ch)])
            ch_names.append(EpicsSignal(name, rw=False, 
                            alias=''.join(['_ch',str(ch),'_count'])))
        signals += ch_names

        for sig in signals:
            self.add_signal(sig)
        
    # TODO: push into base class
    def _field_pv(self, field):
        '''
        Return a full PV from the field name
        '''
        return '%s.%s' % (self._record, field.upper())

    def start(self):
        self._count_ctl._set_request(1, wait=False)

    # TODO: should this be a non-blocking write?
    # TODO: should writes be non-blocking by default?
    def stop(self):
        self._count_ctl.request = 0

    # TODO: mode is a Property...
    def set_mode(self, mode):
        self._count_mode.request = mode

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

        return {ch: getattr(self, '_ch%s_count'%ch).value for ch in channels}
