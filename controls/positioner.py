# vi: ts=4 sw=4
'''

'''

from __future__ import print_function
import logging
from .signal import (EpicsSignal, SignalGroup, OpTimeoutError)

import time


logger = logging.getLogger(__name__)


class Positioner(SignalGroup):
    SUB_DONE = 'done_moving'

    def __init__(self, *args, **kwargs):
        SignalGroup.__init__(self, *args, **kwargs)

        self._default_sub = None
        self._moved_callbacks = []

    def move(self, position, wait=True,
             moved_cb=None, timeout=10.0):
        # TODO session manager handles ctrl-C to stop move?

        if wait:
            t0 = time.time()
            while self._moving:
                time.sleep(0.05)

                if timeout is not None and (time.time() - t0) > timeout:
                    raise OpTimeoutError('Failed to move %s to %s in %s s' %
                                         (self, position, timeout))

        elif moved_cb is not None:
            self._moved_callbacks.append(moved_cb)

    def _done_moving(self, timestamp=None, value=None, **kwargs):
        self._run_sub(sub_type=self.SUB_DONE, timestamp=timestamp,
                      value=value, **kwargs)

        if self._moved_callbacks:
            for cb in self._moved_callbacks:
                cb(timestamp=timestamp, value=value, **kwargs)

            del self._moved_callbacks[:]

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
                   EpicsSignal(self._field_pv('RDBD'), alias='retry_deadband'),
                   ]

        for signal in signals:
            self.add_signal(signal)

        self.is_moving.subscribe(self._move_changed)
        self._moving = False

    def _field_pv(self, field):
        return '%s.%s' % (self._record, field.upper())

    def move(self, position, wait=True,
             **kwargs):
        self.user_request.request = position

        time.sleep(0.05)

        deadband = self.retry_deadband.value
        if not self._moving and abs(position - self.user_readback.value) <= deadband:
            self._move_changed(timestamp=time.time(), value=0)
            ## TODO better handling

        Positioner.move(self, position, wait=wait,
                        **kwargs)

    def __str__(self):
        return 'EpicsMotor(record={0}, val={1}, rbv={2}, egu={3})'.format(
            self._record, self.user_request.value, self.user_readback.value,
            self.egu.value)

    def _move_changed(self, timestamp=None, value=None,
                      **kwargs):
        was_moving = self._moving
        self._moving = (value != 0)

        logger.debug('[%s] %s moving: %s (value=%s)' % (timestamp, self, self._moving, value))

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

            self.done.subscribe(self._move_changed)

        for signal in signals:
            self.add_signal(signal)

    def _field_pv(self, field):
        return '%s.%s' % (self._record, field.upper())

    def move(self, position, wait=True,
             **kwargs):
        self.user_request.request = position

        Positioner.move(self, position, wait=wait,
                        **kwargs)

    def _move_changed(self, timestamp=None, value=None,
                      **kwargs):
        was_moving = self._moving
        self._moving = (value != 0)

        logger.debug('[%s] %s moving: %s (value=%s)' % (timestamp, self, self._moving, value))

        if was_moving and not self._moving:
            self._done_moving(timestamp=timestamp, value=value)
