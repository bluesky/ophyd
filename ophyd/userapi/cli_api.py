"""
Command Line Interface to opyd objects

"""

#
# Motor help routines
#
#
from __future__ import print_function
import logging
import time

from ..controls.positioner import EpicsMotor, Positioner

from epics import caget, caput

# Global Defs of certain strings

STRING_FMT = '^14'
VALUE_FMT  = '^ 14f'

def _list_of(value, type_=str):
  """Return a list of types defined by type_""" 
  if value is None:
    return None
  elif isinstance(value, type_):
    return [value]
    
  if any([not isinstance(s, type_) for s in value]):
    raise ValueError("The list is of incorrect type")

  return [s for s in value]

#def _print_green(text):
#  print("\033[0;32m{}\033[0m".format(text), end = '')
#
#def _print_red(text):
#  print("\033[0;31m{}\033[0m".format(text), end = '')

def _print_string(val):
  print('{:{fmt}} '.format(val, fmt = STRING_FMT), end = '')

def _print_value(val):
  if val is not None:
    print('{:{fmt}} '.format(val, fmt = VALUE_FMT), end = '')
  else:
    _print_string('')

def _blink(on = True):
  if on:
    print("\x1b[?25h\n")
  else:
    print("\x1b[?25l\n")

def _ensure_positioner_pair(func):
  def inner(positioner, position, *args, **kwargs):
    pos = _list_of(positioner, Positioner)
    val = _list_of(position, (float, int))
    return func(pos, val, *args, **kwargs)
  return inner

def _ensure_positioner_tuple(func):
  def inner(positioner, tup, *args, **kwargs):
    pos = _list_of(positioner, Positioner)
    t = _list_of(tup, (tuple, list))
    return func(pos, t, *args, **kwargs)
  return inner

def _ensure_positioner(func):
  def inner(positioner, *args, **kwargs):
    pos = _list_of(positioner, Positioner)
    return func(pos, *args, **kwargs)
  return inner

@_ensure_positioner_pair
def mov(positioner, position, quiet = False):
  """Move a positioner to a given position

  :param positioner: A single positioner or a collection of positioners to move
  :param position: A single position or a collection of positions.
  :param quiet: Do not print any output to console.
 
  """

  try:

    if not quiet:
      _blink(False)
      for p in positioner:
        _print_string(p.name)
      print("\n")

    # Start Moving all Positioners

    for p, v in zip(positioner, position):
      p.move(v, wait = False)
    time.sleep(0.01)

    flag = 0
    moving = True
    while moving or (flag < 2):
      if not quiet:
        for p in positioner:
          _print_value(p.position)
        print('', end = '\r')
      time.sleep(0.01)
      moving = any([p.moving for p in positioner])
      if not moving:
        flag += 1

  except KeyboardInterrupt:
    for p in positioner:
      p.stop()
    print("\n\n")
    print("ABORTED : Commanded all positioners to stop")

  if not quiet:
    _blink()

@_ensure_positioner_pair
def movr(positioner, position):
  """Move a positioner to a relative position

  :param positioner: A single positioner or a collection of positioners to move
  :param position: A single position or a collection of positions.
  :param quiet: Do not print any output to console.
 
  """
  # Get current positions

  _start_val = [p.position for p in positioner]
  for v in _start_val:
    if v is None:
      raise Exception("Unable to read motor position for relative move")

  _new_val = [a + b for a,b in zip(_start_val, position)] 
  mov(positioner, _new_val)

@_ensure_positioner
def set_lm(positioner, limits):
  """Set the positioner limits

  Note : Currently this only works for EpicsMotor instances
  :param positioner: A single positioner or a collection of positioners to move
  :param limits: A single tupple or a collection of tuples for the form (+ve, -ve) limits.

  """

  print('')

  for p in positioner:
    if not isinstance(p, EpicsMotor): 
      raise ValueError("Positioners must be EpicsMotors to set limits")
  
  for p,lim in zip(positioner, limits):
    lim1 = max(lim)
    lim2 = min(lim)
    if not caput(p._record + ".HLM", lim1):
      raise Exception("Unable to set limits for %s", p.name)
    print("Upper limit set to {:{fmt}} for positioner {}".format(lim1, p.name, fmt = VALUE_FMT))

    if not caput(p._record + ".LLM", lim2):
      raise Exception("Unable to set limits for %s", p.name)
    print("Lower limit set to {:{fmt}} for positioner {}".format(lim2, p.name, fmt = VALUE_FMT))


@_ensure_positioner_pair
def set_pos(positioner, position):
  """Set the position of a positioner

  Note : Currently this only works for EpicsMotor instances
  :param positioner: A single positioner or a collection of positioners to move
  :param position: A single position or a collection of positions.

  """
  # TODO : Loggin of motors
  for p in positioner:
    if not isinstance(p, EpicsMotor):
      raise ValueError("Positioners must be EpicsMotors to set position")

  # Get the current position
 

  new_val = position
 
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
      print('Motor {0} set to position {1} (Offset = {2} was {3})'.format(
             p.name, p.position, o, old_o))
    else:
      print('Unable to set position of positioner {0}'.format(p.name))

  print('') 

@_ensure_positioner
def get_pos(positioner):
  """Get the current position of Positioners"""

  print('')

  pos = [p.position for p in positioner]

  for p,v,n in zip(positioner, pos, range(len(pos))):
    _print_string(p.name)
    print(' = ', end = '')
    _print_value(v)
    if n % 2:
      print('')
    else:
      print('  ', end = '')
    
  print('')
