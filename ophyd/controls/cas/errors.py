from pcaspy import cas

__all__ = ['casError',
           'casSuccess',
           'casPVNotFoundError',
           'casUndefinedValueError',
           'casAsyncCompletion',
           'casAsyncRunning',
           ]


class casError(Exception):
    ret = cas.S_casApp_success


class casSuccess(casError):
    ret = cas.S_casApp_success


class casPVNotFoundError(casError):
    ret = cas.S_casApp_pvNotFound


class casUndefinedValueError(casError):
    ret = cas.S_casApp_undefined


class casAsyncCompletion(casError):
    ret = cas.S_casApp_asyncCompletion


class casAsyncRunning(casError):
    ret = cas.S_casApp_postponeAsyncIO
