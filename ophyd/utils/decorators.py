# vi: ts=4 sw=4 sts=4 expandtab
'''
:mod:`ophyd.utils.decorators` - Useful decorators
=================================================

.. module:: ophyd.utils.decorators
   :synopsis:
'''

import functools


def memoize(max_size=128):
    '''
    Function decorator

    Caches the wrapped function's return value.
    Defaults to maximum 128 items in the cache.

    .. note:: keyword arguments are not supported (TODO)
    .. note:: naive random cache clearing, should improve (TODO)
    '''
    def factory(func):
        cache = {}
        
        @functools.wraps(func)
        def wrapper(*args):
            if args in cache:
                return cache[args]
            result = func(*args)
            if len(cache) > max_size:
                del cache[random.choice(cache.keys())]
            cache[args] = result
            return result
            
        return wrapper
        
    return factory


def cached_retval(fcn):
    '''Function decorator

    Caches the wrapped functions return value

    .. note:: parameters are not taken into account (TODO)
    '''
    status = {'called': False,
              'retval': None}

    @functools.wraps(fcn)
    def wrapped():
        if not status['called']:
            status['called'] = True
            status['retval'] = fcn()

        return status['retval']

    return wrapped
