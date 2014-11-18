'''
:mod:`ophyd.utils.errors` - Ophyd exceptions
============================================

.. module:: ophyd.utils.errors
   :synopsis: Exceptions and error-handling routines that
       are specific to Ophyd
'''


class OpException(Exception):
    '''Ophyd base exception class'''
    pass


class TimeoutError(OpException):
    pass


# - Alarms
class AlarmError(OpException):
    pass


class MinorAlarmError(AlarmError):
    pass


class MajorAlarmError(AlarmError):
    pass


# EPICS alarm severities
EPICS_SEV_MINOR, EPICS_SEV_MAJOR = 1, 2


def get_alarm_class(severity):
    '''
    Get the corresponding alarm exception class for
    the specified severity.
    '''
    severity_error_class = {
        EPICS_SEV_MINOR: MinorAlarmError,
        EPICS_SEV_MAJOR: MajorAlarmError,
    }

    return severity_error_class[severity]
