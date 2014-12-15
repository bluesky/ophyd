# vi: ts=4 sw=4
'''
:mod:`ophyd.control.pseudopos` - Pseudo positioners
===================================================

.. module:: ophyd.control.pseudopos
   :synopsis: Pseudo positioner support

'''

from __future__ import print_function
import logging
import time

import numpy as np

from ..utils import TimeoutError
from .positioner import Positioner


logger = logging.getLogger(__name__)


class PseudoPositioner(Positioner):
    def __init__(self, positioners,
                 forward=None,
                 reverse=None,
                 concurrent=True,
                 pseudo=None,
                 master=None,
                 **kwargs):

        Positioner.__init__(self, **kwargs)

        if forward is not None:
            if not callable(forward):
                raise ValueError('Forward calculation must be callable')

            self._calc_forward = forward

        if reverse is not None:
            if not callable(reverse):
                raise ValueError('Reverse calculation must be callable')

            self._calc_reverse = reverse

        self._real = list(positioners)
        self._concurrent = bool(concurrent)
        self._finish_thread = None
        self._real_waiting = []

        for real in self._real:
            real.subscribe(self._real_finished,
                           event_type=real.SUB_DONE,
                           run=False)

        if pseudo is None:
            pseudo = ('value', )
        elif isinstance(pseudo, str):
            self._pseudo = (pseudo, )
        else:
            self._pseudo = tuple(pseudo)

        # TODO will calculations ever be too complex to make caching x number of
        #      fwd/rev calculation results worthwhile?
        if not self._pseudo or not self._real:
            raise ValueError('Must have at least 1 positioner and pseudo-positioner')

    def stop(self):
        for pos in self._real:
            pos.stop()

        Positioner.stop(self)

    @property
    def moving(self):
        return any(pos.moving for pos in self._real)

    @property
    def sequential(self):
        '''
        If sequential is set, motors will move in the sequence they were defined in
        (i.e., in series)
        '''
        return not self._concurrent

    @property
    def concurrent(self):
        '''
        If concurrent is set, motors will move concurrently (in parallel)
        '''
        return self._concurrent

    # Don't allow the base class to specify whether it has started moving
    def _get_started(self):
        return any(pos._started_moving for pos in self._real)

    def _set_started(self, value):
        pass

    _started_moving = property(_get_started, _set_started)

    @property
    def position(self):
        pos_kw = dict((real.name, real.position) for real in self._real)
        return self.calc_reverse(**pos_kw)

    def _real_finished(self, obj=None, **kwargs):
        '''
        A single real positioner has finished moving.

        Used for asynchronous motion, if all have finished
        moving then fire a callback (via `Positioner._done_moving`)
        '''
        real = obj

        if real in self._real_waiting:
            self._real_waiting.remove(real)

            if not self._real_waiting:
                self._done_moving()

    def move(self, position, wait=True, timeout=30.0,
             **kwargs):
        if np.size(position) != len(self._pseudo):
            raise ValueError('Number of positions and pseudo positioners does not match')

        position = np.array(position, ndmin=1)
        pos_kw = dict((pseudo, value) for pseudo, value in
                      zip(self._pseudo, position))

        real_pos = self.calc_forward(**pos_kw)

        # Remove the 'finished moving' callback, otherwise callbacks will
        # happen when individual motors finish moving
        moved_cb = kwargs.pop('moved_cb', None)

        if self.sequential:
            for real, value in zip(self._real, real_pos):
                if timeout <= 0:
                    raise TimeoutError('Failed to move all positioners within %s s' % timeout)

                t0 = time.time()

                try:
                    real.move(value, wait=True, timeout=timeout,
                              **kwargs)
                except:  # Exception as ex:
                    # TODO tag something onto exception message?
                    raise

                elapsed = time.time() - t0
                timeout -= elapsed

        else:
            del self._real_waiting[:]
            self._real_waiting.extend(self._real)

            for real, value in zip(self._real, real_pos):
                real.move(value, wait=False, **kwargs)

        ret = Positioner.move(self, position, moved_cb=moved_cb,
                              wait=wait,
                              **kwargs)

        if self.sequential or (wait and not self.moving):
            self._done_moving()

        return ret

    def _calc_forward(self, *args, **kwargs):
        '''
        Override me
        '''
        return [0.0] * len(self._real)

    def calc_forward(self, *args, **kwargs):
        '''
        '''
        real_pos = self._calc_forward(**kwargs)

        if len(real_pos) != len(self._real):
            raise ValueError('Forward calculation did not return right position count')

        return real_pos

    def _calc_reverse(self, *args, **kwargs):
        '''
        Override me
        '''
        return [0.0] * len(self._pseudo)

    def calc_reverse(self, *args, **kwargs):
        pseudo_pos = self._calc_reverse(**kwargs)

        if len(pseudo_pos) != len(self._pseudo):
            raise ValueError('Reverse calculation did not return right position count')

        return pseudo_pos
