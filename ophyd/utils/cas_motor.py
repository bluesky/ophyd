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


class CasMotor(CasRecord):
    _rtype = 'motor'
    _readback_field = 'RBV'

    def __init__(self, name, positioner, **kwargs):
        if not isinstance(positioner, Positioner):
            raise ValueError('The positioner must be derived from Positioner')
        elif isinstance(positioner, PseudoPositioner):
            if len(positioner.pseudos) > 1:
                raise ValueError('Cannot use with multiple-pseudo positioner. '
                                 'Instead, create CasMotors on individual axes.')

        self._pos = positioner

        CasRecord.__init__(self, name, self._pos.position,
                           rtype=self._rtype, **kwargs)

        self.add_field(self._readback_field, positioner.position)

        positioner.subscribe(self._readback_updated, positioner.SUB_READBACK)

    def written_to(self, timestamp=None, value=None,
                   status=None, severity=None):
        if status or severity:
            print('rejecting value', value)
            return

        self._pos.move(value, wait=False,
                       moved_cb=lambda **kwargs: self.async_done())

        raise casAsyncCompletion

    def _readback_updated(self, value=None, **kwargs):
        self[self._readback_field] = value
