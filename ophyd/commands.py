
"""Command Line Interface to opyd objects"""


import time
import functools
import sys
import warnings
from contextlib import contextmanager, closing
from operator import attrgetter
from io import StringIO
import collections

import IPython
from IPython.utils.coloransi import TermColors as tc

from epics import caget, caput

from . import (EpicsMotor, PositionerBase, PVPositioner, Device)
from .utils import DisconnectedError
from .utils.startup import setup as setup_ophyd
from prettytable import PrettyTable
import numpy as np


__all__ = ['mov',
           'movr',
           'set_pos',
           'wh_pos',
           'set_lm',
           'log_pos',
           'log_pos_diff',
           'log_pos_mov',
           'get_all_positioners',
           'get_logbook',
           'setup_ophyd',
           ]

# Global Defs of certain strings

FMT_LEN = 18
FMT_PREC = 6
DISCONNECTED = 'disconnected'


def scrape_namespace():
    """
    Get all public objects from the user namespace, sorted by name.

    If we are not in an IPython session, warn and return an empty list.
    """
    ip = IPython.get_ipython()
    if ip is None:
        warnings.warn('Unable to inspect Python global namespace; '
                      'use IPython to enable these features.')
        return []
    else:
        return [val for var, val in sorted(ip.user_ns.items())
                if not var.startswith('_')]


def instances_from_namespace(classes):
    '''Get all instances of `classes` from the user namespace

    Parameters
    ----------
    classes : type, or sequence of types
        Passed directly to isinstance(), only instances of these classes
        will be returned.
    '''
    return [val for val in scrape_namespace() if isinstance(val, classes)]


def ducks_from_namespace(attr):
    '''Get all instances that have a given attribute.

    "Ducks" is a reference to "duck-typing." If it looks like a duck....

    Parameters
    ----------
    attr : str
        name of attribute
    '''
    return [val for val in scrape_namespace() if hasattr(val, attr)]


def get_all_positioners():
    '''Get all positioners defined in the IPython namespace'''
    devices = instances_from_namespace((Device, PositionerBase))
    positioners = []
    for device in devices:
        positioners.extend(_recursive_positioner_search(device))
    return positioners


def _recursive_positioner_search(device):
    "Return a flat list the device and any subdevices that can be 'set'."
    # TODO Refactor this as a method on Device.
    res = []

    try:
        if hasattr(device, 'position'):  # duck-typed as a Positioner
            res.append(device)
    except DisconnectedError:
        res.append(device)

    if isinstance(device, Device):  # only Devices have `_signals`
        for d in device._signals.values():
            if isinstance(d, (Device, PositionerBase)):
                res.extend(_recursive_positioner_search(d))
    return res


def _normalize_positioners(positioners):
    "input normalization used by wh_pos, log_pos, log_pos_mov"
    if positioners is None:
        # Grab IPython namespace, recursively find Positioners.
        res = get_all_positioners()
    elif isinstance(positioners, (Device, PositionerBase)):
        # Explore children in case this is a composite Device.
        res = _recursive_positioner_search(positioners)
    else:
        # Assume this is a list of Devices.
        res = []
        for device in positioners:
            if not isinstance(device, (Device, PositionerBase)):
                raise TypeError("Input is not a Device: %r" % device)
            res.extend(_recursive_positioner_search(device))
    return list(sorted(set(res), key=attrgetter('name')))


def var_from_namespace(var):
    ip = IPython.get_ipython()
    if ip is not None:
        return ip.user_ns[var]
    else:
        raise RuntimeError('No IPython session')


def get_logbook():
    '''Get the logbook instance from the user namespace'''
    try:
        return var_from_namespace('logbook')
    except (KeyError, RuntimeError):
        return None


def ensure(*ensure_args):
    def wrap(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            # First check if we have an iterable first on the first arg.
            # If not, then make these all lists
            if len(args) > 0:
                if not hasattr(args[0], "__iter__"):
                    args = tuple([[a] for a in args])
            # Now do type checking ignoring None
            for n, (arg, t) in enumerate(zip(args, ensure_args)):
                if t is None:
                    # Ignore when type is specified as None
                    continue

                invalid = [x for x in arg
                           if not isinstance(x, t)]

                if invalid:
                    raise TypeError('Incorrect type in parameter list.\n'
                                    'Parameter at 0-based position {} must be'
                                    'an instance of {}'.format(n, t))

            f(*args, **kwargs)
        return wrapper
    return wrap


@ensure(PositionerBase, None)
def mov(positioner, position):
    """Move positioners to given positions

    Move positioners using the move method of the Positioner class.

    Parameters
    ----------
    positioner : Positioner or list
        Positioners to move
    position : float or list of float
        Values to move positioners to.

    Examples
    --------
    Move a single positioner `slt1_xc` to 10::

    >>>mov(slt1_xc, 10)

    Move positioner `slt1_xg` and `slt1_yg` to 2 and 3 respectively::

    >>>mov([slt1_xg, slt1_yg], [2, 3])
    """

    print('\n   ', end='')
    print(tc.Green, end='')
    for p in positioner:
        print_string(p.name)
    print("\n")

    # Start Moving all Positioners in context manager to catch
    # Keyboard interrupts

    # TODO : This should be a utility function

    pos_prec = []
    for p in positioner:
        if hasattr(p, 'precision'):
            pos_prec.append(p.precision)
        else:
            pos_prec.append(FMT_PREC)

    with catch_keyboard_interrupt(positioner):
        stat = [p.move(v, wait=False) for p, v in
                zip(positioner, position)]

        # The loop below ensures that at least a couple prints
        # will happen
        flag = 0
        done = False

        while not all(s.done for s in stat) or (flag < 2):
            print(tc.LightGreen, end='')
            print('   ', end='')
            for p, prec in zip(positioner, pos_prec):
                print_value(p.position, egu=p.egu, prec=prec)
            print('\n')
            print('\033[2A', end='')
            time.sleep(0.01)
            done = all(s.done for s in stat)
            if done:
                flag += 1

    print(tc.Normal + '\n')
    for err in [s for s in stat if not s.success]:
        device = err.pos
        reason = "Unknown"
        if isinstance(device, EpicsMotor):
            if device.high_limit_switch.get():
                reason = "Motor reached the high limit switch."
            elif device.low_limit_switch.get():
                reason = "Motor reached the low limit switch."

        print('Warning: {} failed to reach the target position. '
              'Reason: {}'.format(device.name, reason))


@ensure(PositionerBase, None)
def movr(positioner, position):
    """Move positioners relative to their current positon.

    See Also
    --------
    mov : move positioners to an absolute position.
    """

    _start_val = [p.position for p in positioner]
    for v in _start_val:
        if v is None:
            raise IOError("Unable to read motor position for relative move")

    _new_val = [a + b for a, b in zip(_start_val, position)]
    mov(positioner, _new_val)


@ensure(PositionerBase, None)
def set_lm(positioner, limits):
    """Set the limits of the positioner

    Sets the limits of the positioner or list of positioners. For EpicsMotors
    the fields .HLM and .LLM are set to the high and low limits respectively.
    For PVPositioners the .DRVH and .DRVL fields are set on the setopoint
    record. If neither method works then an IOError is raised.

    Parameters
    ----------
    positioner : positioner or list of positioners
    limits : single or list of tuple of form (+ve, -ve) limits

    Raises
    ------
    IOError
        If the caput (EPICS put) fails then an IOError is raised.

    Examples
    --------
    Set the limits of motor `m1` to (10, -10)::

    >>>set_lm(slt1_xc, (10, -10))

    Set the limits of motors `m1` and `m2` to (2, -2) and (3, -3)
    respectively::

    >>>set_lm([m1, m2], [[2,-2], [3, -3]])
    """

    print('')
    msg = ''

    high_fields = []
    low_fields = []
    for p in positioner:
        if isinstance(p, EpicsMotor):
            high_fields.append(p.prefix + '.HLM')
            low_fields.append(p.prefix + '.LLM')
        elif isinstance(p, PVPositioner):
            high_fields.append(p.setpoint_pvname[0] + '.DRVH')
            low_fields.append(p.setpoint_pvname[0] + '.DRVL')
        else:
            raise TypeError("Positioners must be EpicsMotors or PVPositioners"
                            "to set the limits")

    for p, lim, high_field, low_field in zip(positioner,
                                             limits,
                                             high_fields, low_fields):
        lim1 = max(lim)
        lim2 = min(lim)
        if not caput(high_field, lim1):
            raise IOError("Unable to set high limit for {}"
                          " writing to PV {}.".format(p.name, high_field))
        msg += "Upper limit set to {:.{prec}g} for positioner {}\n".format(
               lim1, p.name, prec=FMT_PREC)

        if not caput(low_field, lim2):
            raise IOError("Unable to set low limit for {}"
                          " writing to PV {}.".format(p.name, low_field))
        msg += "Lower limit set to {:.{prec}g} for positioner {}\n".format(
               lim2, p.name, prec=FMT_PREC)

    print(msg)
    logbook = get_logbook()
    if logbook:
        logbook.log(msg)


@ensure(PositionerBase, (float, int))
def set_pos(positioner, position):
    """Set the position of a positioner

    Set the position of a positioner or positioners to the value position.
    This function only works for EpicsMotors (Based on the EPICS Motor Record)
    and uses the .OFF field to set the current position to the value passed to
    the function.

    Parameters
    ----------
    positioner : Positioner or list of positioners.
    position : float or list of floats.
        New position of positioners

    Raises
    ------
    TypeError
        If positioner is not an instance of an EpicsMotor.

    Examples
    --------
    Set the position of motor m1 to 4::

    >>>set_pos(m1, 4)

    Set the position of motors m1 and m2 to 1 and 2 respectively::

    >>>set_pos([m1, m2], [1, 2])

    Raises:
        TypeError: If positioner is not an instance of an EpicsMotor.
    """
    for p in positioner:
        if not isinstance(p, EpicsMotor):
            raise TypeError("Positioner {} must be an EpicsMotor"
                            "to set position.".format(p.name))

    # Get the current offset

    offset_pvs = [p.prefix + ".OFF" for p in positioner]
    dial_pvs = [p.prefix + ".DRBV" for p in positioner]

    old_offsets = [caget(p) for p in offset_pvs]
    dial = [caget(p) for p in dial_pvs]

    for v in old_offsets + dial:
        if v is None:
            raise ValueError("Could not read or invalid value for current"
                             "position of positioners")

    new_offsets = [a - b for a, b in zip(position, dial)]

    msg = ''
    for o, old_o, p in zip(new_offsets, old_offsets, positioner):
        if caput(p.prefix + '.OFF', o):
            msg += 'Motor {0} set to position {1} (Offset = {2} was {3})\n'\
                   .format(p.name, p.position, o, old_o)
        else:
            print('Unable to set position of positioner {0}'.format(p.name))

    print(msg)
    logbook = get_logbook()
    if logbook:
        lmsg = logbook_add_objects(positioner, dial_pvs + offset_pvs)
        logbook.log(msg + '\n' + lmsg)


def wh_pos(positioners=None):
    """Get the current position of Positioners and print to screen.

    Print to the screen the position of the positioners in a formated table.

    Parameters
    ----------
    positioners : Positioner, list of Positioners or None

    See Also
    --------
    log_pos : Log positioner values to logbook

    Examples
    --------
    List all positioners::

    >>>wh_pos()

    List positioners `m1`, `m2` and `m3`::

    >>>wh_pos([m1, m2, m3])
    """
    positioners = _normalize_positioners(positioners)
    _print_pos(positioners, file=sys.stdout)


def log_pos(positioners=None, extra_msg=None):
    """Get the current position of Positioners and make a logbook entry.

    Print to the screen the position of the positioners and make a logbook text
    entry. This routine also creates session information in the logbook so
    positions can be recovered.

    Parameters
    ----------
    positioners : Positioner, list of Positioners or None

    Returns
    -------
    int
        The ID of the logbook entry returned by the logbook.log method.
    """
    positioners = _normalize_positioners(positioners)
    logbook = get_logbook()
    if extra_msg:
        msg = extra_msg + '\n'
    else:
        msg = ''

    with closing(StringIO()) as sio:
        _print_pos(positioners, file=sio)
        msg += sio.getvalue()

    # Add the text representation of the positioners

    # Create the property for storing motor posisions
    pdict = {}
    pdict['values'] = {}

    msg += logbook_add_objects(positioners)

    for p in positioners:
        try:
            pdict['values'][p.name] = p.position
        except DisconnectedError:
            pdict['values'][p.name] = DISCONNECTED

    pdict['objects'] = repr(positioners)
    pdict['values'] = repr(pdict['values'])

    if logbook:
        id_ = logbook.log(msg, properties={'OphydPositioners': pdict},
                          ensure=True)

        print('Logbook positions added as Logbook ID {}'.format(id_))
        return id_


def log_pos_mov(id=None, dry_run=False, positioners=None, **kwargs):
    """Move to positions located in logboook

    This function moves to positions recorded in the experimental logbook using
    the :py:func:`log_pos` function.

    Parameters
    ----------
    id : integer, optional
        ID of logbook entry to search for and move positions to.
    dry_run : bool, optional
        If True, do not move motors, but execute a dry_run
    positioners : list, optional
        List of string names of positioners to compare and move. Other
        positioners in the log entry will be ignored.
    """
    positioners = _normalize_positioners(positioners)
    logpos, objects = logbook_to_objects(id, **kwargs)
    objects = collections.OrderedDict(sorted(objects.items()))

    keys = set(positioners).intersection(set(objects.keys()))
    objects = {x: objects[x] for x in keys}

    print('')
    stat = []
    for key, value in objects.items():
        newpos = logpos[key]
        if newpos == DISCONNECTED:
            print('{}[!!] Unable to move positioner {} {}: position was stored'
                  'as disconnected'.format(tc.Red, key, tc.Normal))
            continue

        try:
            oldpos = value.position
        except DisconnectedError:
            print('{}[!!] Unable to move positioner {} {}: disconnected'
                  ''.format(tc.Red, key, tc.Normal))
            continue

        try:
            if not dry_run:
                stat.append(value.move(newpos, wait=False))
        except Exception as ex:
            print('{}[!!] Unable to move positioner {} {} ({}: {})'
                  ''.format(tc.Red, key, tc.Normal, ex.__class__.__name__, ex))
        else:
            print('{}[**] Moving positioner {} to {}'
                  ' from current position of {}{}`'
                  ''.format(tc.Green, key, newpos, oldpos, tc.Normal))

    print('\n{}Waiting for positioners to complete .....'
          ''.format(tc.LightGreen), end='')

    sys.stdout.flush()

    if len(stat) > 0:
        while all(s.done for s in stat):
            time.sleep(0.01)

    print(' Done{}\n'.format(tc.Normal))


def log_pos_diff(id=None, positioners=None, **kwargs):
    """Move to positions located in logboook

    This function compares positions recorded in the experimental logbook
    using the :py:func:`log_pos` function.

    Parameters
    ----------
    id : integer
        ID of logbook entry to search for and move positions to.
    positioners : list
        List of string names of positioners to compare. Other positioners
        in the log entry will be ignored.
    """

    positioners = _normalize_positioners(positioners)
    logpos, objects = logbook_to_objects(id, **kwargs)
    objects = collections.OrderedDict(sorted(objects.items()))

    # Cycle through positioners and compare position with old value
    # If we have an error, print a warning

    diff = []
    pos = []
    values = []

    keys = set(positioners).intersection(set(objects.keys()))
    objects = {x: objects[x] for x in keys}

    print('')
    for key, value in objects.items():
        oldpos = logpos[key]
        if oldpos == DISCONNECTED:
            print('{}[!!] Unable to compare position {} {}: position was stored'
                  'as disconnected'.format(tc.Red, key, tc.Normal))
            continue

        try:
            newpos = value.position
        except DisconnectedError:
            print('{}[!!] Unable to compare position {} {}: disconnected'
                  ''.format(tc.Red, key, tc.Normal))
            continue

        try:
            diff.append(newpos - oldpos)
        except Exception as ex:
            print('{}[!!] Unable to compare position {}{}: ({}: {})'
                  .format(tc.Red, key, tc.Normal, ex.__class__.__name__, ex))
        else:
            pos.append(value)
            values.append(newpos)

    header_len = 3 * (FMT_LEN + 3) + 1
    print_header(len=header_len)
    print_string('Positioner', pre='| ', post=' | ')
    print_string('Value', post=' | ')
    print_string('Difference', post=' |\n')

    print_header(len=header_len)

    for p, v, d in zip(pos, values, diff):
        print_string(p.name, pre='| ', post=' | ')
        print_value(v, egu=p.egu, post=' | ')
        print_value(d, egu=p.egu, post=' |\n')

    print_header(len=header_len)
    print('')


def logbook_to_objects(id=None, **kwargs):
    """Search the logbook and return positioners"""

    logbook = get_logbook()
    if logbook is None:
        raise RuntimeError("No logbook is available")

    entry = logbook.find(id=id, **kwargs)
    if len(entry) != 1:
        raise ValueError("Search of logbook was not unique, please refine"
                         "search")
    try:
        prop = entry[0]['properties']['OphydPositioners']
    except KeyError:
        raise KeyError('No property in log entry with positioner information')

    try:
        obj = eval(prop['objects'])
        val = eval(prop['values'])
    except Exception as ex:
        raise RuntimeError('Unable to create objects from log entry '
                           '(%s)' % ex)

    objects = {o.name: o for o in obj}
    return val, objects


def logbook_add_objects(objects, extra_pvs=None):
    """Add to the logbook aditional information on ophyd objects.

    This routine takes objects and possible extra pvs and adds to the log entry
    information which is not printed to stdout/stderr.

    Parameters
    ----------
    objects : Ophyd objects
        Objects to add to log entry.
    extra_pvs : List of strings
        Extra PVs to include in report
    """

    msg = ''
    msg += '{:^43}|{:^22}|{:^50}\n'.format('PV Name', 'Name', 'Value')
    msg += '{:-^120}\n'.format('')

    # Make a list of all PVs and positioners
    reports = [o.report for o in objects]
    pvs = [report.get('pv', str(None)) for report in reports]
    names = [o.name for o in objects]
    values = [str(v) for report in reports
              for k, v in report.items() if k != 'pv']

    if extra_pvs is not None:
        pvs += extra_pvs
        names += ['None' for e in extra_pvs]
        values += [caget(e) for e in extra_pvs]

    for a, b, c in zip(pvs, names, values):
        msg += 'PV:{:<40} {:<22} {:<50}\n'.format(a, b, c)

    return msg


def print_header(title='', char='-', len=80, file=sys.stdout):
    print('{:{char}^{len}}'.format(title, char=char, len=len), file=file)


def print_string(val, size=FMT_LEN, pre='', post=' ', file=sys.stdout):
    print('{}{:<{size}}{}'.format(pre, val, post, size=size), end='', file=file)


def print_value(val, prec=FMT_PREC, egu='', **kwargs):
    if val is not None:
        print_string('{: .{fmt}f} {}'.format(val, egu, fmt=prec), **kwargs)
    else:
        print_string('', **kwargs)


def blink(on=True, file=sys.stdout):
    if on:
        print("\x1b[?25h", end='', file=file)
    else:
        print("\x1b[?25l", end='', file=file)


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
        print(tc.Red + "[!!] ABORTED "
              ": Commanding all positioners to stop.")
        for p in positioners:
            p.stop()
            print("{}[--] Stopping {}{}".format(tc.Red, tc.LightRed, p.name))
        print(tc.Normal, end='')
        blink(True)
        raise
    print(tc.Normal, end='')
    blink(True)


def _print_pos(positioners, file=sys.stdout):
    """Pretty Print the positioners to file"""

    print('', file=file)
    pos = []
    for p in positioners:
        try:
            pos.append(p.position)
        except (DisconnectedError, TypeError):
            pos.append(None)

    # Print out header
    pt = PrettyTable(['Positioner', 'Value', 'Low Limit', 'High Limit'])
    pt.align = 'r'
    pt.align['Positioner'] = 'l'
    pt.float_format = '8.5'

    for p, v in zip(positioners, pos):
        if pos is None:
            continue
        if v is not None:
            try:
                prec = p.precision
            except (AttributeError, DisconnectedError):
                prec = FMT_PREC
            value = np.round(v, decimals=prec)
        else:
            value = DISCONNECTED

        try:
            low_limit, high_limit = p.low_limit, p.high_limit
        except DisconnectedError:
            low_limit = high_limit = DISCONNECTED

        pt.add_row([p.name, value, low_limit, high_limit])

    print(pt, file=file)
