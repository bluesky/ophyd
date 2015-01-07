#!/usr/bin/env python2.7
'''
An example of using :class:`CasFunction`, a decorator that makes a Python
function accessible over channel access (using ophyd's built-in EPICS channel access
server)
'''
from __future__ import print_function
import time

import numpy as np

from ophyd.controls import EpicsSignal
from ophyd.controls.cas import CasFunction

import config

logger = config.logger


# Keyword arguments only allowed, since default values must be specified.
# (prefix defaults to 'function_name:' when not specified)
@CasFunction()
def async_func(a=0, b=0.0, **kwargs):
    # Note that since 0 is an integer, `a` will be an integer in EPICS
    # Note that since 0.0 is a float, `b` will be a float in EPICS
    logger.info('async_func called: a=%s b=%s, kw=%s' % (a, b, kwargs))

    # Function is called asynchronously, so it's OK to block:
    time.sleep(0.5)

    ret = a + b
    logger.info('async_func returning: %s' % ret)
    return ret


# Keyword arguments only allowed, since default values must be specified.
@CasFunction(async=False, prefix='test:sync:')
def sync_func(a=0, b=0.0, **kwargs):
    logger.info('sync_func called: a=%s b=%s, kw=%s' % (a, b, kwargs))

    # Not an asynchronous PV, don't block
    return a * b


@CasFunction(return_value='test')
def string_func(value='test'):
    logger.info('string_func called: value=%s' % value)

    # Not a asynchronous PV, don't block
    return value.upper()


# Keyword arguments get passed onto CasPV for the return value, so you can specify
# more about the return type:
@CasFunction(type_=np.int32, count=10)
def array_func(value=0.0):
    logger.info('array_func called: value=%s' % (value, ))

    return np.arange(10) * value


@CasFunction(type_=np.int32, count=10)
def no_arg_func():
    logger.info('no_arg_func called')

    return np.arange(10)


# Keyword arguments get passed onto CasPV for the return value, so you can specify
# more about the return type:
@CasFunction()
def array_input_func(value=np.array([1., 2., 3.], dtype=np.float)):
    logger.info('array_input_func called: value=%s' % (value, ))

    return np.average(value)


# Can't use positional arguments:
try:
    @CasFunction(prefix='test:')
    def test1(a, b=1):
        pass
except ValueError:
    logger.debug('(Failed as expected)')


# Can't use variable arguments:
try:
    @CasFunction(prefix='test:')
    def test2(a=1, *b):
        pass
except ValueError:
    logger.debug('(Failed as expected)')


def test_async():
    logger.info('asynchronous function')
    pvnames = async_func.get_pvnames()

    sig_a = EpicsSignal(pvnames['a'])
    sig_b = EpicsSignal(pvnames['b'])
    sig_proc = EpicsSignal(pvnames['process'])
    sig_ret = EpicsSignal(pvnames['retval'])

    a, b = 3.0, 4.0

    sig_a.value = a
    sig_b.value = b
    sig_proc.value = 1

    time.sleep(0.1)
    logger.info('result through channel access: %s' % sig_ret.value)

    logger.info('called normally: %r' % async_func(a=a, b=b))


def test_sync():
    logger.info('synchronous function')
    pvnames = sync_func.get_pvnames()

    sig_a = EpicsSignal(pvnames['a'])
    sig_b = EpicsSignal(pvnames['b'])
    sig_proc = EpicsSignal(pvnames['process'])
    sig_ret = EpicsSignal(pvnames['retval'])

    a, b = 3.0, 4.0
    sig_a.value = a
    sig_b.value = b
    sig_proc.value = 1

    time.sleep(0.1)
    logger.info('result through channel access: %r' % sig_ret.value)

    logger.info('called normally: %r' % sync_func(a=a, b=b))


def test_string():
    logger.info('string function')
    pvnames = string_func.get_pvnames()

    sig_value = EpicsSignal(pvnames['value'])
    sig_proc = EpicsSignal(pvnames['process'])
    sig_ret = EpicsSignal(pvnames['retval'])

    sig_value.value = 'hello'
    sig_proc.value = 1

    time.sleep(0.1)
    logger.info('result through channel access: %r' % sig_ret.value)

    logger.info('called normally: %r' % string_func(value='hello'))


def test_array():
    logger.info('array function')
    pvnames = array_func.get_pvnames()

    sig_value = EpicsSignal(pvnames['value'])
    sig_proc = EpicsSignal(pvnames['process'])
    sig_ret = EpicsSignal(pvnames['retval'])

    sig_value.value = 2.0
    sig_proc.value = 1

    time.sleep(0.1)
    logger.info('result through channel access: %r' % sig_ret.value)

    logger.info('called normally: %r' % array_func(value=2.0))


def test_array_input():
    logger.info('array input function')
    pvnames = array_input_func.get_pvnames()

    sig_value = EpicsSignal(pvnames['value'])
    sig_proc = EpicsSignal(pvnames['process'])
    sig_ret = EpicsSignal(pvnames['retval'])

    input_ = np.array([5, 10, 15])
    sig_value.value = input_
    sig_proc.value = 1

    time.sleep(0.1)
    logger.info('result through channel access: %r' % sig_ret.value)

    logger.info('called normally: %r' % array_input_func(value=input_))


def test_no_arg():
    logger.info('no argument function')
    pvnames = no_arg_func.get_pvnames()

    sig_proc = EpicsSignal(pvnames['process'])
    sig_ret = EpicsSignal(pvnames['retval'])

    sig_proc.value = 1

    time.sleep(0.1)
    logger.info('result through channel access: %r' % sig_ret.value)

    logger.info('called normally: %r' % no_arg_func())


def test():
    loggers = ('ophyd.controls.cas',
               'ophyd.controls.cas.function',
               )

    config.setup_loggers(loggers)

    test_async()
    test_sync()
    test_string()
    test_array()
    test_array_input()
    test_no_arg()


if __name__ == '__main__':
    test()
