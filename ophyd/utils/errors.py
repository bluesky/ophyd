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

# Severities
class EpicsAlarms(object):
    alarms = ('NO_ALARM',
              'READ_ALARM',
              'WRITE_ALARM',
              'HIHI_ALARM',
              'HIGH_ALARM',
              'LOLO_ALARM',
              'LOW_ALARM',
              'STATE_ALARM',
              'COS_ALARM',
              'COMM_ALARM',
              'TIMEOUT_ALARM',
              'HW_LIMIT_ALARM',
              'CALC_ALARM',
              'SCAN_ALARM',
              'LINK_ALARM',
              'SOFT_ALARM',
              'BAD_SUB_ALARM',
              'UDF_ALARM',
              'DISABLE_ALARM',
              'SIMM_ALARM',
              'READ_ACCESS_ALARM',
              'WRITE_ACCESS_ALARM'
              )

    def __init__(self):
        for index, alarm in enumerate(self.alarms):
            setattr(self, alarm, index)

    def get_name(self, idx):
        return self.alarms[idx]


alarms = EpicsAlarms()


class AlarmError(OpException):
    severity = 0

    def __init__(self, msg, alarm='NO_ALARM', **kwargs):
        if isinstance(alarm, str):
            self.alarm = getattr(alarms, alarm)
        else:
            self.alarm = int(alarm)

        self.alarm_name = alarms.get_name(self.alarm)

        OpException.__init__(self, msg, **kwargs)


class MinorAlarmError(AlarmError):
    severity = 1


class MajorAlarmError(AlarmError):
    severity = 2


def get_alarm_class(severity):
    '''
    Get the corresponding alarm exception class for
    the specified severity.
    '''
    severity_error_class = {
        MinorAlarmError.severity: MinorAlarmError,
        MajorAlarmError.severity: MajorAlarmError,
    }

    return severity_error_class[severity]
