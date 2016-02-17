# vi: ts=4 sw=4
'''
:mod:`ophyd.control.pseudopos` - Pseudo positioners
===================================================

.. module:: ophyd.control.pseudopos
   :synopsis: Pseudo positioner support
'''


import logging
import time
import threading

from collections import (OrderedDict, namedtuple)

from .utils import DisconnectedError
from .positioner import PositionerBase
from .device import Device


logger = logging.getLogger(__name__)


class PseudoSingle(PositionerBase):
    '''A single axis of a PseudoPositioner'''

    def __init__(self, prefix=None, *, limits=None, parent=None, name=None,
                 idx=None, **kwargs):
        super().__init__(name=name, parent=parent, **kwargs)

        self._target = None

        if limits is None:
            limits = (0, 0)

        self._limits = tuple(limits)
        self._idx = idx

        self._parent.subscribe(self._sub_proxy, event_type=self.SUB_START)
        self._parent.subscribe(self._sub_proxy, event_type=self.SUB_DONE)
        self._parent.subscribe(self._sub_proxy_idx,
                               event_type=self.SUB_READBACK)

    @property
    def limits(self):
        return self._limits

    def _repr_info(self):
        yield from super()._repr_info()

        yield ('idx', self._idx)

    def _sub_proxy(self, obj=None, **kwargs):
        '''Master callbacks such as start of motion, motion finished, etc. will
        be simply passed through.
        '''
        return self._run_subs(obj=self, **kwargs)

    def _sub_proxy_idx(self, obj=None, value=None, **kwargs):
        if hasattr(value, '__getitem__'):
            value = value[self._idx]

        return self._run_subs(obj=self, value=value, **kwargs)

    @property
    def target(self):
        '''Last commanded target position'''
        if self._target is None:
            return self.position
        else:
            return self._target

    def sync(self):
        '''Synchronize target position with current readback position'''
        self._target = None

    def check_value(self, pos):
        self._parent.check_single(self, pos)

    @property
    def moving(self):
        return self._parent.moving

    @property
    def position(self):
        return self._parent.position[self._idx]

    def stop(self):
        return self._parent.stop()

    @property
    def connected(self):
        '''For signal compatibility'''
        return True

    @property
    def _started_moving(self):
        return self._parent._started_moving

    @_started_moving.setter
    def _started_moving(self, value):
        # Don't allow the base class to specify whether it has started moving
        pass

    def move(self, pos, **kwargs):
        self._target = pos
        return self._parent.move_single(self, pos, **kwargs)

    def read(self):
        d = OrderedDict()
        d[self.name] = {'value': self.position,
                        'timestamp': time.time()}
        return d

    def describe(self):
        desc = OrderedDict()
        desc[self.name] = {'dtype': 'number',
                           'shape': [],
                           'source': 'computed',
                           }
        return desc

    def read_configuration(self):
        return OrderedDict()

    def describe_configuration(self):
        return OrderedDict()


class PseudoPositioner(Device, PositionerBase):
    '''A pseudo positioner which can be comprised of multiple positioners

    Parameters
    ----------
    concurrent : bool, optional
        If set, all real motors will be moved concurrently. If not, they will
        be moved in order of how they were defined initially
    read_attrs : sequence of attribute names
        The signals to be read during data acquisition (i.e., in read() and
        describe() calls)
    name : str, optional
        The name of the device
    parent : instance or None
        The instance of the parent device, if applicable
    '''
    def __init__(self, prefix, *, concurrent=True, read_attrs=None,
                 configuration_attrs=None, monitor_attrs=None, name=None,
                 **kwargs):

        self._finished_lock = threading.RLock()
        self._concurrent = bool(concurrent)
        self._finish_thread = None
        self._real_waiting = []
        self._move_queue = []

        if self.__class__ is PseudoPositioner:
            raise TypeError('PseudoPositioner must be subclassed with the '
                            'correct signals set in the class definition.')

        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs,
                         monitor_attrs=monitor_attrs,
                         name=name, **kwargs)

        self._real = [getattr(self, attr)
                      for attr, cpt in self._get_real_positioners()]
        self._pseudo = [getattr(self, attr)
                        for attr, cpt in self._get_pseudo_positioners()]

        if not self._pseudo or not self._real:
            raise ValueError('Must have at least 1 positioner and '
                             'pseudo-positioner')

        self.RealPosition = self._real_position_tuple()
        self.PseudoPosition = self._pseudo_position_tuple()

        logger.debug('Real positioners: %s', self._real)
        logger.debug('Pseudo positioners: %s', self._pseudo)

        for idx, pseudo in enumerate(self._pseudo):
            pseudo._idx = idx

        self._real_cur_pos = OrderedDict((real, None) for real in self._real)

        for real in self._real:
            # Subscribe to events from all the real motors and update the
            # internal state of their position
            real.subscribe(self._real_pos_update, event_type=real.SUB_READBACK,
                           run=True)

    @property
    def pseudo_positioners(self):
        '''Pseudo positioners'''
        return self.PseudoPosition(*self._pseudo)

    @property
    def real_positioners(self):
        '''Real positioners'''
        return self.RealPosition(*self._real)

    @classmethod
    def _real_position_tuple(cls):
        '''A namedtuple for a real motor position'''
        name = cls.__name__ + 'RealPos'
        return namedtuple(name, [name for name, cpt in
                                 cls._get_real_positioners()])

    @classmethod
    def _pseudo_position_tuple(cls):
        '''A namedtuple for a pseudo motor position'''
        name = cls.__name__ + 'PseudoPos'
        return namedtuple(name, [name for name, cpt in
                                 cls._get_pseudo_positioners()])

    @classmethod
    def _get_pseudo_positioners(cls):
        '''Inspect the components and find the pseudo positioners'''
        if hasattr(cls, '_pseudo'):
            for pseudo in cls._pseudo:
                yield pseudo, getattr(cls, pseudo)
        else:
            for attr, cpt in cls._sig_attrs.items():
                if issubclass(cpt.cls, PseudoSingle):
                    yield attr, cpt

    @classmethod
    def _get_real_positioners(cls):
        '''Inspect the components and find the real positioners'''
        if hasattr(cls, '_real'):
            for real in cls._real:
                yield real, getattr(cls, real)
        else:
            for attr, cpt in cls._sig_attrs.items():
                is_pseudo = issubclass(cpt.cls, PseudoSingle)
                is_positioner = issubclass(cpt.cls, PositionerBase)
                if is_positioner and not is_pseudo:
                    yield attr, cpt

    def _repr_info(self):
        yield from super()._repr_info()
        yield ('concurrent', self._concurrent)

    @property
    def connected(self):
        return all(mtr.connected for mtr in self._real)

    def stop(self):
        try:
            del self._move_queue[:]
            for pos in self._real:
                pos.stop()
        finally:
            super().stop(self)

    def check_single(self, pseudo_single, single_pos):
        '''Check if a new position for a single pseudo positioner is valid'''
        idx = pseudo_single._idx
        target = list(self.target)
        target[idx] = single_pos
        return self.check_value(self.PseudoPosition(*target))

    def check_value(self, pseudo_pos):
        '''Check if a new position for all pseudo positioners is valid'''
        try:
            pseudo_pos = self.PseudoPosition(*pseudo_pos)
        except TypeError as ex:
            raise ValueError('Not all required values for a PseudoPosition: {}'
                             '({})'.format(self.PseudoPosition._fields, ex))

        for pseudo, pos in zip(self._pseudo, pseudo_pos):
            low, high = pseudo.limits
            if (high > low) and not (low <= pos <= high):
                raise ValueError('Position is outside of pseudo single limits:'
                                 ' {}, {} < {} < {}'.format(pseudo.name, low,
                                                            pos, high))

        real_pos = self.forward(pseudo_pos)
        for real, pos in zip(self._real, real_pos):
            real.check_value(pos)

    @property
    def moving(self):
        return any(pos.moving for pos in self._real)

    @property
    def sequential(self):
        '''If sequential is set, motors will move in the sequence they were
        defined in (i.e., in series)
        '''
        return not self._concurrent

    @property
    def concurrent(self):
        '''If concurrent is set, motors will move concurrently (in parallel)'''
        return self._concurrent

    @property
    def _started_moving(self):
        return any(pos._started_moving for pos in self._real)

    @_started_moving.setter
    def _started_moving(self, value):
        # Don't allow the base class to specify whether it has started moving
        pass

    @property
    def position(self):
        '''Pseudo motor position namedtuple'''
        return self.inverse(self.real_position)

    @property
    def real_position(self):
        '''Real motor position namedtuple'''
        return self.RealPosition(*self._real_cur_pos.values())

    def _update_position(self):
        real_cur_pos = self.real_position
        if None in real_cur_pos:
            raise DisconnectedError('Not all positioners connected')

        calc_pseudo_pos = self.inverse(real_cur_pos)
        self._set_position(calc_pseudo_pos)
        return calc_pseudo_pos

    def _real_pos_update(self, obj=None, value=None, **kwargs):
        '''A single real positioner has moved'''
        real = obj
        self._real_cur_pos[real] = value
        # Only update the position if all real motors are connected
        try:
            self._update_position()
        except DisconnectedError:
            pass

    def _done_moving(self, success=True):
        del self._real_waiting[:]
        super()._done_moving(success=success)

    def _real_finished(self, obj=None):
        '''A single real positioner has finished moving.

        Used for asynchronous motion, if all have finished moving then fire a
        callback (via `Positioner._done_moving`)
        '''
        with self._finished_lock:
            real = obj
            logger.debug('Real motor %s finished moving', real.name)

            if real in self._real_waiting:
                self._real_waiting.remove(real)

                if not self._real_waiting:
                    self._done_moving()

    def move_single(self, pseudo, position, **kwargs):
        idx = pseudo._idx
        target = list(self.target)
        target[idx] = position
        return self.move(self.PseudoPosition(*target), **kwargs)

    @property
    def target(self):
        '''Last commanded target positions'''
        return self.PseudoPosition(*(pos.target for pos in self._pseudo))

    def _sequential_move(self, real_pos, timeout=None, **kwargs):
        '''Move all real positioners to a certain position, in series'''
        # without proper timeout support for status callbacks, we can't safely
        # chain motions on other callbacks for sequential motion.  so,
        # 'sequential_move' above always blocks
        # this is a big TODO

        self._move_queue[:] = zip(self._real, real_pos)
        pending_status = []
        t0 = time.time()

        def move_next(obj=None):
            # last motion complete message came from 'obj'
            logger.debug('[%s:sequential] move_next called', self.name)
            with self._finished_lock:
                if pending_status:
                    last_status = pending_status[-1]
                    if not last_status.success:
                        logger.error('Failing due to last motion')
                        self._done_moving(success=False)
                        return

                try:
                    real, position = self._move_queue.pop(0)
                except IndexError:
                    self._done_moving(success=True)
                    return

                logger.debug('[%s:sequential] Moving next motor: %s',
                             self.name, real.name)

                elapsed = time.time() - t0
                if timeout is None:
                    sub_timeout = None
                else:
                    sub_timeout = timeout - elapsed

                logger.debug('[%s:sequential] Moving %s to %s (timeout=%s)',
                             self.name, real.name, position, sub_timeout)

                if sub_timeout is not None and sub_timeout < 0:
                    logger.error('Motion timeout')
                    self._done_moving(success=False)
                else:
                    status = real.move(position, wait=False,
                                       timeout=sub_timeout,
                                       moved_cb=move_next,
                                       **kwargs)
                    pending_status.append(status)
                    logger.debug('[%s:sequential] waiting on %s',
                                 self.name, real.name)

        logger.debug('[%s:sequential] started', self.name)
        move_next()

    def _concurrent_move(self, real_pos, **kwargs):
        '''Move all real positioners to a certain position, in parallel'''
        self._real_waiting.extend(self._real)

        for real, value in zip(self._real, real_pos):
            logger.debug('[concurrent] Moving %s to %s', real.name, value)
            real.move(value, wait=False, moved_cb=self._real_finished,
                      **kwargs)

    def move(self, position, wait=True, timeout=10.0, **kwargs):
        real_pos = self.forward(position)

        # Clear all old statuses for not yet completed real motions
        del self._real_waiting[:]

        # Remove the 'finished moving' callback, otherwise callbacks will
        # happen when individual motors finish moving
        moved_cb = kwargs.pop('moved_cb', None)

        st = super().move(position, moved_cb=moved_cb, timeout=timeout)

        with self._finished_lock:
            # ensure we don't get any motion complete messages before motion
            # setup is finished
            if self.sequential:
                self._sequential_move(real_pos, timeout=timeout)
            else:
                self._concurrent_move(real_pos, timeout=timeout)

        if wait:
            st.wait()

        return st

    def forward(self, pseudo_pos):
        ''' '''
        return self.RealPosition()

    def __call__(self, pseudo_pos):
        return self.forward(pseudo_pos)

    def inverse(self, real_pos):
        '''Override me'''
        return self.PseudoPosition()
