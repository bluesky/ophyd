# vi: ts=4 sw=4
'''

'''

from __future__ import print_function
import logging
from ..context import get_session_manager
from .signal import (EpicsSignal, SignalGroup)

logger = logging.getLogger(__name__)


class Positioner(SignalGroup):
    SUB_DONE = 'done_moving'

    def __init__(self, *args, **kwargs):
        SignalGroup.__init__(self, *args, **kwargs)

        self._default_sub = None

    def move(self, position, wait=True,
             moved_cb=None):
        pass

    def _stopped(self, status):
        self._run_sub(self.SUB_DONE, status)

    def stop(self):
        pass

    def get_position(self):
        pass

    @property
    def moving(self):
        return self._moving


class EpicsMotor(Positioner):
    # TODO: EpicsMotor could potentially be just a special case of a PVPositioner,
    # but there's a lot of additional info we can grab, knowing that it's a
    # motor record. (the fact that the additional fields are rarely used
    # properly is another story though...)

    def __init__(self, record, **kwargs):
        self._record = record

        Positioner.__init__(self, record, **kwargs)

        signals = [EpicsSignal(self._field_pv('RBV'), rw=False, alias='user_readback'),
                   EpicsSignal(self._field_pv('VAL'), alias='user_request'),
                   EpicsSignal(self._field_pv('MOVN'), alias='is_moving'),
                   EpicsSignal(self._field_pv('EGU'), alias='egu'),
                   ]

        for signal in signals:
            self.add_signal(signal)

        self._moving = False

    def _field_pv(self, field):
        return '%s.%s' % (self._record, field.upper())

    def move(self, position):
        self.user_request.request = position
        self._stopped(True)

    def __str__(self):
        return 'EpicsMotor(record={0}, val={1}, rbv={2}, egu={3})'.format(
            self._record, self.user_request.readback, self.user_readback.readback,
            self.egu.readback)


class PVPositioner(Positioner):
    def __init__(self, setpoint, readback=None,
                 act=None, act_val=1,
                 stop=None, stop_val=1,
                 done=None, done_val=1,
                 **kwargs):
        Positioner.__init__(self, **kwargs)

        signals = [EpicsSignal(setpoint, alias='setpoint')]

        if readback is not None:
            signals.append(EpicsSignal(readback, alias='readback'))

        if act is not None:
            signals.append(EpicsSignal(act, alias='actuate'))

        if stop is not None:
            signals.append(EpicsSignal(stop, alias='stop'))

        if done is not None:
            signals.append(EpicsSignal(done, alias='done'))

            self.done.readback.subscribe(self._move_changed)

        for signal in signals:
            self.add_signal(signal)

    def _field_pv(self, field):
        return '%s.%s' % (self._record, field.upper())

    def move(self, position):
        self.user_request.request = position

    def _move_changed(self, pvname=None, value=None, timestamp=None,
                      **kwargs):
        logger.debug('Stopped ')
        self._moving = (value != self._stop_value)

        self._stopped(self._moving, (timestamp, value))
