from __future__ import print_function
import logging

from .signal import EpicsSignal
from .detector import SignalDetector, DetectorStatus

logger = logging.getLogger(__name__)


class EpicsScaler(SignalDetector):
    '''SynApps Scaler Record interface'''
    _SUB_REQ_DONE = '_req_done'  # requested move finished subscription
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
        signals = [EpicsSignal(self._field_pv('CNT'),
                               alias='count',
                               name=''.join([name, '_count'])),
                   EpicsSignal(self._field_pv('CONT'),
                               alias='count_mode',
                               name=''.join([name, '_count_mode'])),
                   EpicsSignal(self._field_pv('T'),
                               alias='time',
                               name=''.join([name, '_time'])),
                   EpicsSignal(self._field_pv('TP'),
                               alias='preset_time',
                               name=''.join([name, '_preset_time']))
                   ]

        for ch in range(1, numchan + 1):
            pv = '{}{}'.format(self._field_pv('S'), ch)
            signals.append(EpicsSignal(pv, rw=False,
                                       alias='chan{}'.format(ch),
                                       name='{}_chan{}'.format(name, ch)))

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
        self._autocount = self.count_mode.value
        self.count_mode.value = 0

    def deconfigure(self, **kwargs):
        """Deconfigure Scaler

        Reset thet autocount status
        """
        self.count_mode.value = self._autocount

    def _done_acquiring(self, timestamp=None, value=None, **kwargs):
        '''Call when acquisition has completed.  Runs SUB_DONE subscription.'''

        self._run_subs(sub_type=self._SUB_REQ_DONE, timestamp=timestamp,
                       value=value, success=True,
                       **kwargs)
        self._reset_sub(self._SUB_REQ_DONE)

    def acquire(self, **kwargs):
        """Start the scaler counting and return status

        Returns
        -------
        DetectorStatus : Status of detector
        """

        def done_counting(**kwargs):
            self._done_acquiring()

        self.count.put(1, wait=False,
                       callback=done_counting)
        status = DetectorStatus(self)
        self.subscribe(status._finished,
                       event_type=self._SUB_REQ_DONE, run=False)
        return status
