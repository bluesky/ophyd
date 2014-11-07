# vi: ts=4 sw=4
'''

'''

from __future__ import print_function
import logging
from .signal import (EpicsSignal, SignalGroup)

import time


logger = logging.getLogger(__name__)


class Positioner(SignalGroup):
    SUB_DONE = 'done_moving'

    def __init__(self, *args, **kwargs):
        SignalGroup.__init__(self, *args, **kwargs)

        self._default_sub = None

    def move(self, position, wait=True,
             moved_cb=None):
        if wait:
            while self._moving:
                time.sleep(0.05)

    def _done_moving(self, timestamp=None, value=None, **kwargs):
        self._run_sub(self.SUB_DONE, timestamp=timestamp,
                      value=value, **kwargs)

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

        self.is_moving.subscribe(self._move_changed)
        self._moving = False

    def _field_pv(self, field):
        return '%s.%s' % (self._record, field.upper())

    def move(self, position):
        self.user_request.request = position

    def __str__(self):
        return 'EpicsMotor(record={0}, val={1}, rbv={2}, egu={3})'.format(
            self._record, self.user_request.readback, self.user_readback.readback,
            self.egu.readback)

    def _move_changed(self, sub_type, timestamp=None, value=None,
                      **kwargs):
        was_moving = self._moving
        self._moving = (value != 1)

        logger.debug('[%s] %s moving: %s' % (timestamp, self, self._moving))

        if was_moving and not self._moving:
            self._done_moving(timestamp=timestamp, value=value)


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

    def move(self, position, wait=True):
        self.user_request.request = position

        Positioner.move(self, position, wait=True)

    def _move_changed(self, sub_type, timestamp=None, value=None,
                      **kwargs):
        was_moving = self._moving
        self._moving = (value != 0)

        logger.debug('[%s] %s moving: %s' % (timestamp, self, self._moving))

        if was_moving and not self._moving:
            self._done_moving(timestamp=timestamp, value=value)
