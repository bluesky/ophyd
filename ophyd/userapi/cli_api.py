"""
Command Line Interface to opyd objects

"""

# Green = \033[0;32m{}\033[0m
# Red = \033[0;31m{}\033[0m

from __future__ import print_function
import time
import functools
import sys
from contextlib import contextmanager, closing
from StringIO import StringIO

import numpy as np
from epics import caget, caput

from ..controls.positioner import EpicsMotor, Positioner
from ..session import get_session_manager

session_mgr = get_session_manager()

try:
    logbook = session_mgr['olog_client']
except KeyError:
    logbook = None

__all__ = ['mov',
           'movr',
           'set_pos',
           'wh_pos',
           'set_lm',
           'log_pos'
           ]

# Global Defs of certain strings

FMT_LEN = 18
FMT_PREC = 6


def logbook_add_objects(objects, extra_pvs=None):
    """Add to the logbook aditional information on ophyd objects.

    :param objects: Objects to add to log entry.
    :type objects: Ophyd objects
    :param extra_pvs: Extra PVs to include in report
    :type extra_pvs: List of strings

    This routine takes objects and possible extra pvs and adds to the log
    entry information which is not printed to stdout/stderr.

    """

    msg = ''
    msg += '{:^43}|{:^22}|{:^50}\n'.format('PV Name', 'Name', 'Value')
    msg += '{:-^120}\n'.format('')

    # Make a list of all PVs and positioners
    pvs = [o.report['pv'] for o in objects]
    names = [o.name for o in objects]
    values = [str(o.value) for o in objects]
    if extra_pvs is not None:
        pvs += extra_pvs
        names += ['None' for e in extra_pvs]
        values += [caget(e) for e in extra_pvs]

    for a, b, c in zip(pvs, names, values):
        msg += 'PV:{:<40} {:<22} {:<50}\n'.format(a, b, c)

    return msg


def _list_of(value, type_=str):
    """Return a list of types defined by type_"""
    if value is None:
        return None
    elif isinstance(value, type_):
        return [value]

    if any([not isinstance(s, type_) for s in value]):
        raise ValueError("The list is of incorrect type")

    return [s for s in value]


def print_header(title='', char='-', len=80, file=sys.stdout):
    print('{:{char}^{len}}'.format(title, char=char, len=len), file=file)


def print_string(val, size=FMT_LEN, pre='', post=' ', file=sys.stdout):
    print('{}{:<{size}}{}'.format(pre, val, post, size=size), end='', file=file)


def print_value(val, prec=FMT_PREC, egu='', **kwargs):
    if val is not None:
        print_string('{:.{fmt}} {}'.format(val, egu, fmt=prec), **kwargs)
    else:
        print_string('', **kwargs)


def print_value_aligned(val, size=FMT_LEN, prec=FMT_PREC, egu='', **kwargs):
    fmt1 = '{{0:>{0}}}.{{1:<{1}}}'.format(size-prec-6, prec)
    fmt2 = '{{:.{}f}}'.format(prec)
    s = fmt2.format(val).rstrip('0').split('.')
    if len(s) == 1:
        s = (s[0], '0')
    elif s[1] == '':
        s[1] = '0'
    s[1] = '{} {}'.format(s[1], egu)
    print_string(fmt1.format(*(s[:2])), **kwargs)


def blink(on=True, file=sys.stdout):
    if on:
        print("\x1b[?25h", end='', file=file)
    else:
        print("\x1b[?25l", end='', file=file)


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


@contextmanager
def catch_keyboard_interrupt(positioners):
    """Context manager to capture Keyboard Interrupt and stop motors

    This context manager should be used when moving positioners via the cli
    to capture the keyboardInterrupt and ensure that motors are stopped and
    clean up the output to the screen.

    """

    blink(False)

    try:
        yield
    except KeyboardInterrupt:
        print("[!!] ABORTED : Commanding all positioners to stop.")
        for p in positioners:
            p.stop()
            print("[--] Stopping {}".format(p.name))

    blink(True)


@_ensure_positioner_pair
def mov(positioner, position, quiet=False):
    """Move a positioner to a given position

    :param positioner: A single positioner or a collection of
                       positioners to move
    :param position: A single position or a collection of positions.

    """

    print('\n   ', end='')
    for p in positioner:
        print_string(p.name)
    print("\n")

    # Start Moving all Positioners in context manager to catch
    # Keyboard interrupts

    with catch_keyboard_interrupt(positioner):
        stat = [p.move(v, wait=False) for p, v in
                zip(positioner, position)]

        # The loop below ensures that at least a couple prints
        # will happen
        flag = 0
        done = False
        while not all(s.done for s in stat) or (flag < 2):
            if not quiet:
                print('   ', end='')
                for p in positioner:
                    print_value(p.position, egu=p.egu)
                print('', end='\r')
            time.sleep(0.05)
            done = all(s.done for s in stat)
            if done:
                flag += 1

    print('\n')


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
            raise ValueError("Unable to read motor position for relative move")

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
    msg = ''

    for p in positioner:
        if not isinstance(p, EpicsMotor):
            raise ValueError("Positioners must be EpicsMotors to set limits")

    for p, lim in zip(positioner, limits):
        lim1 = max(lim)
        lim2 = min(lim)
        if not caput(p._record + ".HLM", lim1):
            # Fixme : Add custom exception class
            raise Exception("Unable to set limits for %s", p.name)
        msg += "Upper limit set to {:.{prec}g} for positioner {}\n".format(
               lim1, p.name, prec=FMT_PREC)

        if not caput(p._record + ".LLM", lim2):
            raise Exception("Unable to set limits for %s", p.name)
        msg += "Lower limit set to {:.{prec}g} for positioner {}\n".format(
               lim2, p.name, prec=FMT_PREC)

    print(msg)
    if logbook:
        logbook.log(msg)


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
            raise TypeError("Positioner {} must be an EpicsMotor"
                            "to set position.".format(p.name))

    # Get the current offset

    offset_pvs = [p._record + ".OFF" for p in positioner]
    dial_pvs = [p._record + ".DRBV" for p in positioner]

    old_offsets = [caget(p) for p in offset_pvs]
    dial = [caget(p) for p in dial_pvs]

    for v in old_offsets + dial:
        if v is None:
            raise ValueError("Could not read or invalid value for current"
                             "position of positioners")

    new_offsets = [a - b for a, b in zip(position, dial)]

    msg = ''
    for o, old_o, p in zip(new_offsets, old_offsets, positioner):
        if caput(p._record + '.OFF', o):
            msg += 'Motor {0} set to position {1} (Offset = {2} was {3})\n'\
                   .format(p.name, p.position, o, old_o)
        else:
            print('Unable to set position of positioner {0}'.format(p.name))

    print(msg)

    lmsg = logbook_add_objects(positioner, dial_pvs + offset_pvs)
    logbook.log(msg + '\n' + lmsg)


@ensure((Positioner,), {'positioners': Positioner})
def wh_pos(positioners=None):
    """Print the current position of Positioners

    Print to the screen positioners and their current values.

    Parameters
    ----------
    positioners : Positioner, list of Positioners or None
                  Positioners to output. If None print all
                  positioners positions.
    """
    if positioners is None:
        positioners = [session_mgr.get_positioners()[d]
                       for d in sorted(session_mgr.get_positioners())]

    _print_pos(positioners, file=sys.stdout)


@ensure((Positioner,), {'positioners': Positioner})
def log_pos(positioners=None):
    """Log the current position of Positioners

    Print to the screen positioners and their current values.

    Parameters
    ----------
    positioners : Positioner, list of Positioners or None
                  Positioners to output. If None print all
                  positioners positions.
    """
    if positioners is None:
        positioners = [session_mgr.get_positioners()[d]
                       for d in sorted(session_mgr.get_positioners())]

    msg = ''

    with closing(StringIO()) as sio:
        _print_pos(positioners, file=sio)
        msg += sio.getvalue()

    print(msg)

    # Add the text representation of the positioners

    msg += logbook_add_objects(positioners)

    # Create the property for storing motor posisions
    pdict = {}
    pdict['objects'] = repr(positioners)
    pdict['values'] = repr({p.name: p.position for p in positioners})
    p = ['OphydPositioners', pdict]

    # make the logbook entry
    id = logbook.log(msg, properties=[p])

    print('Logbook positions added as Logbook ID {}'.format(id))


def _print_pos(positioners, file=sys.stdout):
    """Pretty Print the positioners to file"""
    print('', file=file)

    pos = [p.position for p in positioners]

    # Print out header

    print_header(len=4*(FMT_LEN+3)+1, file=file)
    print_string('Positioner', pre='| ', post=' | ', file=file)
    print_string('Value', post=' | ', file=file)
    print_string('Low Limit', post=' | ', file=file)
    print_string('High Limit', post=' |\n', file=file)

    print_header(len=4*(FMT_LEN+3)+1, file=file)

    for p, v in zip(positioners, pos):
        print_string(p.name, pre='| ', post=' | ', file=file)
        print_value_aligned(v, egu=p.egu, post=' | ', file=file)
        print_value_aligned(p.low_limit, egu=p.egu, post=' | ', file=file)
        print_value_aligned(p.high_limit, egu=p.egu, post=' |\n', file=file)

    print_header(len=4*(FMT_LEN+3)+1, file=file)
    print('', file=file)
