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

from collections import OrderedDict

import numpy as np

from ..utils import TimeoutError
from .positioner import Positioner


logger = logging.getLogger(__name__)


class PseudoSingle(Positioner):
    '''A single axis of a PseudoPositioner'''

    def __init__(self, master, idx, **kwargs):
        name = '%s.%s' % (master.name, master._pseudo_names[idx])

        Positioner.__init__(self, name=name, **kwargs)

        self._master = master
        self._idx = idx

        self._master.subscribe(self._sub_proxy, event_type=self.SUB_START)
        self._master.subscribe(self._sub_proxy, event_type=self.SUB_DONE)
        self._master.subscribe(self._sub_proxy_idx, event_type=self.SUB_READBACK)

    def __repr__(self):
        return self._get_repr(['idx={0._idx!r}'.format(self)])

    def _sub_proxy(self, obj=None, **kwargs):
        '''Master callbacks such as start of motion, motion finished,
        etc. will be simply passed through.
        '''
        return self._run_subs(obj=self, **kwargs)

    def _sub_proxy_idx(self, obj=None, value=None, **kwargs):
        if hasattr(value, '__getitem__'):
            value = value[self._idx]

        return self._run_subs(obj=self, value=value, **kwargs)

    def check_value(self, pos):
        self._master.check_single(self._idx, pos)

    @property
    def moving(self):
        return self._master.moving

    @property
    def position(self):
        return self._master.position[self._idx]

    def stop(self):
        return self._master.stop()

    @property
    def sequential(self):
        return self._master.sequential

    @property
    def concurrent(self):
        return self._master.concurrent

    # Don't allow the base class to specify whether it has started moving
    def _get_started(self):
        return self._master._started_moving

    def _set_started(self, value):
        pass

    _started_moving = property(_get_started, _set_started)

    def move(self, pos, **kwargs):
        return self._master.move_single(self._idx, pos, **kwargs)


class PseudoPositioner(Positioner):
    '''A pseudo positioner which can be comprised of multiple positioners

    Parameters
    ----------
    positioners : sequence
        A list of real positioners to control. Positioners must be named.
    forward : callable
        Pseudo -> real positioner calculation function
        Optionally, subclass PseudoPositioner and replace _calc_forward.
    reverse : callable
        Real -> pseudo positioner calculation function
        Optionally, subclass PseudoPositioner and replace _calc_reverse.
    concurrent : bool, optional
        If set, all real motors will be moved concurrently. If not, they will be
        moved in order of how they were defined initially
    pseudo : list of strings, optional
        List of pseudo positioner names
    '''
    def __init__(self, name, positioners,
                 forward=None,
                 reverse=None,
                 concurrent=True,
                 pseudo=None,
                 **kwargs):

        Positioner.__init__(self, name=name, **kwargs)

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
        self._real_cur_pos = {}

        for real in self._real:
            real.subscribe(self._real_finished,
                           event_type=real.SUB_DONE,
                           run=False)

            self._real_cur_pos[real] = real.position

            real.subscribe(self._real_pos_update,
                           event_type=real.SUB_READBACK,
                           run=False)

        if pseudo is None:
            self._pseudo_names = ('pseudo', )
        elif isinstance(pseudo, str):
            self._pseudo_names = (pseudo, )
        else:
            self._pseudo_names = tuple(pseudo)

        self._pseudo_pos = [PseudoSingle(self, i) for i
                            in range(len(self._pseudo_names))]

        # TODO will calculations ever be too complex to make caching x number of
        #      fwd/rev calculation results worthwhile?
        if not self._pseudo_names or not self._real:
            raise ValueError('Must have at least 1 positioner and pseudo-positioner')

    def __repr__(self):
        repr = ['positioners={0._real!r}'.format(self),
                'concurrent={0._concurrent!r}'.format(self),
                'pseudo={0._pseudo_names!r}'.format(self),
                'forward={0._calc_forward!r}'.format(self),
                'reverse={0._calc_reverse!r}'.format(self),
                ]

        return self._get_repr(repr)

    def stop(self):
        for pos in self._real:
            pos.stop()

        Positioner.stop(self)

    def check_single(self, idx, position):
        '''Check if a new position for a single pseudo positioner is valid'''
        if isinstance(idx, str):
            idx = self._pseudo_names.index(idx)

        target = list(self.position)
        target[idx] = position
        return self.check_value(target)

    def check_value(self, position):
        '''Check if a new position for all pseudo positioners is valid'''
        if np.size(position) != len(self._pseudo_pos):
            raise ValueError('Number of positions and pseudo positioners does not match')

        position = np.array(position, ndmin=1)
        pos_kw = dict((pseudo, value) for pseudo, value in
                      zip(self._pseudo_names, position))

        real_pos = self.calc_forward(**pos_kw)

        for real, pos in zip(self._real, real_pos):
            real.check_value(pos)

    @property
    def moving(self):
        return any(pos.moving for pos in self._real)

    @property
    def sequential(self):
        '''If sequential is set, motors will move in the sequence they were defined in
        (i.e., in series)
        '''
        return not self._concurrent

    @property
    def concurrent(self):
        '''If concurrent is set, motors will move concurrently (in parallel)'''
        return self._concurrent

    # Don't allow the base class to specify whether it has started moving
    def _get_started(self):
        return any(pos._started_moving for pos in self._real)

    def _set_started(self, value):
        pass

    _started_moving = property(_get_started, _set_started)

    @property
    def pseudos(self):
        '''Dictionary of pseudo motors by name

        Keys are in the order of creation
        '''
        return OrderedDict((name, pseudo) for name, pseudo in
                           zip(self._pseudo_names, self._pseudo_pos))

    @property
    def reals(self):
        '''Dictionary of real motors by name'''
        return OrderedDict((real.name, real) for real in self._real)

    def _update_position(self):
        pos_kw = dict((real.name, pos) for real, pos in self._real_cur_pos.items())
        new_pos = self.calc_reverse(**pos_kw)
        self._set_position(new_pos)
        return new_pos

    def _real_pos_update(self, obj=None, value=None, **kwargs):
        '''A single real positioner has moved'''
        real = obj
        self._real_cur_pos[real] = value
        self._update_position()

    def _real_finished(self, obj=None, **kwargs):
        '''A single real positioner has finished moving.

        Used for asynchronous motion, if all have finished
        moving then fire a callback (via `Positioner._done_moving`)
        '''
        real = obj

        if real in self._real_waiting:
            self._real_waiting.remove(real)

            if not self._real_waiting:
                self._done_moving()

    def move_single(self, idx, position, **kwargs):
        if isinstance(idx, str):
            idx = self._pseudo_names.index(idx)

        target = list(self.position)
        target[idx] = position
        return self.move(target, **kwargs)

    def move(self, position, wait=True, timeout=30.0,
             **kwargs):
        if np.size(position) != len(self._pseudo_pos):
            raise ValueError('Number of positions and pseudo positioners does not match')

        position = np.array(position, ndmin=1)
        pos_kw = dict((pseudo, value) for pseudo, value in
                      zip(self._pseudo_names, position))

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
        '''Override me'''
        return [0.0] * len(self._real)

    def calc_forward(self, *args, **kwargs):
        ''' '''
        real_pos = self._calc_forward(**kwargs)

        if np.size(real_pos) != np.size(self._real):
            raise ValueError('Forward calculation did not return right position count')

        return real_pos

    def _calc_reverse(self, *args, **kwargs):
        '''Override me'''
        return [0.0] * len(self._pseudo_pos)

    def calc_reverse(self, *args, **kwargs):
        pseudo_pos = self._calc_reverse(**kwargs)

        if np.size(pseudo_pos) != np.size(self._pseudo_pos):
            raise ValueError('Reverse calculation did not return right position count')

        return pseudo_pos

    def __getitem__(self, key):
        '''Get either a single pseudo or real positioner by name'''
        try:
            return self.pseudos[key]
        except:
            return self.reals[key]

    def __setitem__(self, key, value):
        pos = self[key]
        pos.move(value)

    def __contains__(self, key):
        try:
            self.__getitem__(key)
            return True
        except:
            return False
