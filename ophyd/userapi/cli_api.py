"""
Command Line Interface to opyd objects

"""

# Green = \033[0;32m{}\033[0m
# Red = \033[0;31m{}\033[0m

from __future__ import print_function
import time
import functools

from ..controls.positioner import EpicsMotor, Positioner
from ..session import get_session_manager

session_mgr = get_session_manager()
logger = session_mgr._logger

from epics import caget, caput
import numpy as np

__all__ = ['mov',
           'movr',
           'set_pos',
           'wh_pos',
           'set_lm'
           ]

# Global Defs of certain strings

STRING_FMT = '^14'
VALUE_FMT = '^ 14f'


def _list_of(value, type_=str):
    """Return a list of types defined by type_"""
    if value is None:
        return None
    elif isinstance(value, type_):
        return [value]

    if any([not isinstance(s, type_) for s in value]):
        raise ValueError("The list is of incorrect type")

    return [s for s in value]


def _print_string(val):
    print('{:{fmt}} '.format(val, fmt=STRING_FMT), end='')


def _print_value(val):
    if val is not None:
        print('{:{fmt}} '.format(val, fmt=VALUE_FMT), end='')
    else:
        _print_string('')


def _blink(on=True):
    if on:
        print("\x1b[?25h\n")
    else:
        print("\x1b[?25l\n")


def _ensure_positioner_pair(func):
    @functools.wraps(func)
    def inner(positioner, position, *args, **kwargs):
        pos = _list_of(positioner, Positioner)
        val = _list_of(position, (float, int))
        return func(pos, val, *args, **kwargs)
    return inner


def _ensure_positioner_tuple(func):
    @functools.wraps(func)
    def inner(positioner, tup, *args, **kwargs):
        pos = _list_of(positioner, Positioner)
        t = _list_of(tup, (tuple, list, np.array))
        return func(pos, t, *args, **kwargs)
    return inner


def _ensure_positioner(func):
    @functools.wraps(func)
    def inner(positioner, *args, **kwargs):
        pos = _list_of(positioner, Positioner)
        return func(pos, *args, **kwargs)
    return inner


def ensure(ensure_tuple, ensure_dict):
    def ensure_decorator(func):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            args = tuple([_list_of(a, v) for a, v in zip(args, ensure_tuple)])
            for key, value in ensure_dict.iteritems():
                if key in kwargs:
                    kwargs[key] = _list_of(kwargs[key], value)
            return func(*args, **kwargs)
        return inner
    return ensure_decorator


@_ensure_positioner_pair
def mov(positioner, position, quiet=False):
    """Move a positioner to a given position

    :param positioner: A single positioner or a collection of
                       positioners to move
    :param position: A single position or a collection of positions.

    """

    try:
        _blink(False)
        for p in positioner:
            _print_string(p.name)
        print("\n")

        # Start Moving all Positioners

        stat = [p.move(v, wait=False) for p, v in
                zip(positioner, position)]

        # The loop below ensures that at least a couple prints
        # will happen
        flag = 0
        done = False
        while not all(s.done for s in stat) or (flag < 2):
            if not quiet:
                for p in positioner:
                    _print_value(p.position)
                print('', end='\r')
            time.sleep(0.01)
            done = all(s.done for s in stat)
            if done:
                flag += 1

    except KeyboardInterrupt:
        for p in positioner:
            p.stop()
        print("\n\n")
        print("ABORTED : Commanded all positioners to stop")

    _blink()


@_ensure_positioner_pair
def movr(positioner, position, quiet=False):
    """Move a positioner to a relative position

    :param positioner: A single positioner or a collection of
                       positioners to move
    :param position: A single position or a collection of positions.
    :param quiet: Do not print any output to console.

    """
    # Get current positions

    _start_val = [p.position for p in positioner]
    for v in _start_val:
        if v is None:
            raise Exception("Unable to read motor position for relative move")

    _new_val = [a + b for a, b in zip(_start_val, position)]
    mov(positioner, _new_val, quiet)


@_ensure_positioner
def set_lm(positioner, limits):
    """Set the positioner limits

    Note : Currently this only works for EpicsMotor instances
    :param positioner: A single positioner or a collection of
                       positioners to move
    :param limits: A single tupple or a collection of tuples for
                       the form (+ve, -ve) limits.

    """

    print('')

    for p in positioner:
        if not isinstance(p, EpicsMotor):
            raise ValueError("Positioners must be EpicsMotors to set limits")

    for p, lim in zip(positioner, limits):
        lim1 = max(lim)
        lim2 = min(lim)
        if not caput(p._record + ".HLM", lim1):
            # Fixme : Add custom exception class
            raise Exception("Unable to set limits for %s", p.name)
        msg = "Upper limit set to {:{fmt}} for positioner {}".format(
              lim1, p.name, fmt=VALUE_FMT)
        print(msg)
        logger.info(msg)

        if not caput(p._record + ".LLM", lim2):
            raise Exception("Unable to set limits for %s", p.name)
        msg = "Lower limit set to {:{fmt}} for positioner {}".format(
              lim2, p.name, fmt=VALUE_FMT)
        print(msg)
        logger.info(msg)


@_ensure_positioner_pair
def set_pos(positioner, position):
    """Set the position of a positioner

    Note : Currently this only works for EpicsMotor instances
    :param positioner: A single positioner or a collection of
                       positioners to move
    :param position: A single position or a collection of positions.

    """
    for p in positioner:
        if not isinstance(p, EpicsMotor):
            raise ValueError("Positioners must be EpicsMotors to set position")

    # Get the current offset

    old_offsets = [caget(p._record + ".OFF") for p in positioner]
    dial = [caget(p._record + ".DRBV") for p in positioner]

    for v in old_offsets + dial:
        if v is None:
            raise Exception("Cannot get values for EpicsMotor")

    new_offsets = [a - b for a, b in zip(position, dial)]

    print('')

    for o, old_o, p in zip(new_offsets, old_offsets, positioner):
        if caput(p._record + '.OFF', o):
            msg = 'Motor {0} set to position {1} (Offset = {2} was {3})'.format(
                  p.name, p.position, o, old_o)
            print(msg)
            logger.info(msg)
        else:
            print('Unable to set position of positioner {0}'.format(p.name))

    print('')


@ensure((Positioner,), {'positioners': Positioner})
def wh_pos(positioners=None):
    """Print the current position of Positioners

    Parameters
    ----------
    positioners : Positioner, list of Positioners or None
                  Positioners to output. If None print all
                  positioners positions.
    """

    print('')

    if positioners is None:
        positioners = [session_mgr.get_positioners()[d]
                       for d in sorted(session_mgr.get_positioners())]

    pos = [p.position for p in positioners]

    for p, v, n in zip(positioners, pos, range(len(pos))):
        _print_string(p.name)
        print(' = ', end='')
        _print_value(v)
        if n % 2:
            print('')
        else:
            print('  ', end='')

    print('')
