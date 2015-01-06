#!/usr/bin/env python2.7
'''
An example of using :class:`caServer`, an EPICS channel access server
implementation based on pcaspy
'''
from __future__ import print_function
import time

from ophyd.controls.cas import CasFunction
import config

logger = config.logger


# Keyword arguments only allowed, since default values must be specified.
# (prefix defaults to 'function_name:' when not specified)
@CasFunction()
def async_func(a=0, b=0.0, **kwargs):
    logger.info('async_func called: a=%s b=%s, kw=%s' % (a, b, kwargs))

    # Function is called asynchronously, so it's OK to block:
    time.sleep(0.5)

    return a + b


# Keyword arguments only allowed, since default values must be specified.
@CasFunction(async=False, prefix='test:sync:')
def sync_func(a=0, b=0.0, **kwargs):
    logger.info('sync_func called: a=%s b=%s, kw=%s' % (a, b, kwargs))

    # Not a asynchronous PV, don't block
    return a * b


@CasFunction(return_value='test')
def string_func(value='test'):
    logger.info('string_func called: value=%s' % value)

    # Not a asynchronous PV, don't block
    return value.upper()

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



from ophyd.controls import EpicsSignal

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


def test():
    loggers = ('ophyd.controls.cas',
               'ophyd.controls.cas.function',
               )

    config.setup_loggers(loggers)


if __name__ == '__main__':
    test()

    test_async()
    test_sync()
    test_string()
