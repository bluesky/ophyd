from __future__ import print_function

# import time
# import threading
# import logging
#
# import numpy as np
#
# from .errors import (AlarmError, MajorAlarmError, MinorAlarmError)
# from .errors import alarms

from .cas import (CasRecord, casAsyncCompletion)
from ..controls.positioner import (Positioner, )
from ..controls.pseudopos import (PseudoPositioner, )


STATUS_BITS = {'direction': 0,         # last raw direction; (0:Negative, 1:Positive)
               'done': 1,              # motion is complete.
               'plus_ls': 2,           # plus limit switch has been hit.
               'homels': 3,            # state of the home limit switch.

               'position': 5,          # closed-loop position control is enabled.
               'slip_stall': 6,        # Slip/Stall detected (eg. fatal following error)
               'home': 7,              # if at home position.
               'enc_present': 8,       # encoder is present.
               'problem': 9,           # driver stopped polling, or hardware problem
               'moving': 10,           # non-zero velocity present.
               'gain_support': 11,     # motor supports closed-loop position control.
               'comm_err': 12,         # Controller communication error.
               'minus_ls': 13,         # minus limit switch has been hit.
               'homed': 14,            # the motor has been homed.
               }


class CasMotor(CasRecord):
    _rtype = 'motor'
    _fld_readback = 'RBV'
    _fld_tweak_fwd = 'TWF'
    _fld_tweak_rev = 'TWR'
    _fld_tweak_val = 'TWV'
    _fld_egu = 'EGU'
    _fld_moving = 'MOVN'
    _fld_done_move = 'DMOV'
    _fld_stop = 'STOP'
    _fld_status = 'MSTA'
    _fld_low_lim = 'LLS'
    _fld_high_lim = 'HLS'
    _fld_calib_set = 'SET'
    _fld_limit_viol = 'LVIO'

    def __init__(self, name, positioner,
                 tweak_value=1.0,
                 **kwargs):

        if not isinstance(positioner, Positioner):
            raise ValueError('The positioner must be derived from Positioner')
        elif isinstance(positioner, PseudoPositioner):
            if len(positioner.pseudos) > 1:
                raise ValueError('Cannot use with multiple-pseudo positioner. '
                                 'Instead, create CasMotors on individual axes.')

        self._pos = positioner
        self._status = 0

        CasRecord.__init__(self, name, self._pos.position,
                           rtype=self._rtype, **kwargs)

        self.add_field(self._fld_readback, self._pos.position)
        self.add_field(self._fld_egu, self._pos.egu)
        self.add_field(self._fld_tweak_val, tweak_value)
        self.add_field(self._fld_tweak_fwd, 0, written_cb=self.tweak_forward)
        self.add_field(self._fld_tweak_rev, 0, written_cb=self.tweak_reverse)
        self.add_field(self._fld_stop, 0, written_cb=lambda **kwargs: self._pos.stop())
        self.add_field(self._fld_moving, self._pos.moving)
        self.add_field(self._fld_done_move, not self._pos.moving)
        self.add_field(self._fld_status, 0)
        self.add_field(self._fld_low_lim, 0)
        self.add_field(self._fld_high_lim, 0)
        self.add_field(self._fld_calib_set, 0)
        self.add_field(self._fld_limit_viol, 0)

        self._pos.subscribe(self._readback_updated, self._pos.SUB_READBACK)
        self._pos.subscribe(self._move_started, self._pos.SUB_START)
        self._pos.subscribe(self._move_done, self._pos.SUB_DONE)

        self._update_status(moving=self._pos.moving)

    def written_to(self, timestamp=None, value=None,
                   status=None, severity=None):
        if status or severity:
            return

        if self._check_limits(value):
            self._pos.move(value, wait=False,
                           moved_cb=lambda **kwargs: self.async_done())

            raise casAsyncCompletion

    def _readback_updated(self, value=None, **kwargs):
        self[self._fld_readback] = value

    def _check_limits(self, pos):
        low_lim, high_lim = self._pos.limits

        # TODO: better way to do this. also, limits on .VAL will only update
        # when a move request has been started
        self.limits.hilim = self.limits.hihi = self.limits.high = high_lim
        self.limits.lolim = self.limits.lolo = self.limits.low = low_lim

        if low_lim != high_lim:
            if pos > high_lim:
                self._update_status(minus_ls=0, plus_ls=1)
                return False
            elif pos < low_lim:
                self._update_status(minus_ls=1, plus_ls=0)
                return False

        self._update_status(minus_ls=0, plus_ls=0)
        return True

    def tweak(self, amount):
        # pos = self._pos.position + amount
        pos = self.value + amount
        self.value = pos

        if self._check_limits(pos):
            self._pos.move(pos, wait=False)

    def tweak_reverse(self, **kwargs):
        tweak_val = self[self._fld_tweak_val].value
        return self.tweak(-tweak_val)

    def tweak_forward(self, **kwargs):
        tweak_val = self[self._fld_tweak_val].value
        return self.tweak(tweak_val)

    def _move_started(self, **kwargs):
        self._update_status(moving=1)

    def _move_done(self, **kwargs):
        self._update_status(moving=0)

    def _update_status(self, **kwargs):
        old_status = self._status

        for arg, value in kwargs.iteritems():
            bit = STATUS_BITS[arg]
            if value:
                self._status |= (1 << bit)
            else:
                self._status &= ~(1 << bit)

        field = self[self._fld_status]
        if old_status != self._status:
            field.value = self._status

        moving = kwargs.get('moving', None)
        if moving is not None:
            self[self._fld_moving] = moving
            self[self._fld_done_move] = not moving

        plus_ls = kwargs.get('plus_ls', None)
        if plus_ls is not None:
            self[self._fld_high_lim] = plus_ls

        minus_ls = kwargs.get('minus_ls', None)
        if minus_ls is not None:
            self[self._fld_low_lim] = minus_ls
