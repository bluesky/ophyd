class OpException(Exception):
    '''Ophyd base exception class'''
    pass


class ReadOnlyError(OpException):
    '''Signal is read-only'''
    pass


class LimitError(ValueError, OpException):
    '''Value is outside of defined limits'''
    pass


class DisconnectedError(OpException):
    '''Signal or SignalGroup is not connected to EPICS'''
    pass


class ExceptionBundle(RuntimeError, OpException):
    '''One or more exceptions was raised during a loop of try/except blocks'''
    def __init__(self, msg, exceptions):
        super().__init__(msg)
        self.exceptions = exceptions


class RedundantStaging(OpException):
    pass
