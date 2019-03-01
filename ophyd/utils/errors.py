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
    '''Signal or Device is not connected to EPICS'''
    pass


class DestroyedError(RuntimeError, DisconnectedError):
    '''Signal or Device has been destroyed and is no longer usable'''
    pass


class ExceptionBundle(RuntimeError, OpException):
    '''One or more exceptions was raised during a loop of try/except blocks'''
    def __init__(self, msg, exceptions):
        super().__init__(msg)
        self.exceptions = exceptions


class RedundantStaging(OpException):
    pass


class PluginMisconfigurationError(TypeError, OpException):
    # Keeping TypeError for backward-compatibility
    pass


class UnprimedPlugin(RuntimeError, OpException):
    ...
