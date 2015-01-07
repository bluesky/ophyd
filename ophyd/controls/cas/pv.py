from __future__ import print_function

import time
import threading
import logging

import numpy as np
from pcaspy import cas

from ...utils.errors import (AlarmError, MajorAlarmError, MinorAlarmError)
from ...utils.errors import alarms
from ...utils.epics_pvs import record_field

from .server import caServer
from .errors import (casAsyncCompletion, casAsyncRunning, casError, casSuccess,
                     casUndefinedValueError)


logger = logging.getLogger(__name__)


class Limits(object):
    def __init__(self,
                 lolim=0.0,
                 hilim=0.0,
                 hihi=0.0,
                 lolo=0.0,
                 high=0.0,
                 low=0.0):

        self.lolim = float(lolim)
        self.hilim = float(hilim)
        self.hihi = float(hihi)
        self.lolo = float(lolo)
        self.high = float(high)
        self.low = float(low)

    def check_alarm(self, value):
        """
        Raise an exception if an alarm is set

        :raises: AlarmError (MinorAlarmError, MajorAlarmError)
        """

        lolo = self.lolo
        low = self.low
        high = self.high
        hihi = self.hihi

        if lolo < hihi:
            if value >= hihi:
                raise MajorAlarmError('%s >= %s' % (value, hihi),
                                      alarm=alarms.HIHI_ALARM)
            elif value <= lolo:
                raise MajorAlarmError('%s <= %s' % (value, lolo),
                                      alarm=alarms.LOLO_ALARM)

        if low < high:
            if value >= high:
                raise MinorAlarmError('%s >= %s' % (value, high),
                                      alarm=alarms.HIGH_ALARM)
            elif value <= low:
                raise MinorAlarmError('%s <= %s' % (value, low),
                                      alarm=alarms.LOW_ALARM)


class CasPV(cas.casPV):
    '''
    Channel access server process variable
    '''

    def __init__(self, name, value,
                 count=0,
                 type_=None,
                 precision=1,
                 units='',
                 limits=None,
                 scan=0.0,
                 asg=None,

                 minor_states=[],
                 major_states=[],

                 server=None,
                 written_cb=None,
                 scan_cb=None,
                 ):

        '''
        Channel access server process variable

        :param str name: The PV name (should not include server prefix)
        :param value: The initial value, also used to guess the CA type
        :param int count: The number of elements in the array
            (must be >= len(value))
        :param type_: Override the default type detected from `value`
        :param int precision: The precision clients should use for display
        :param str units: The engineering units of the pv
        :param limits: Limit information (high, low, etc. See :class:`Limits`)
        :param scan: The rate at which to call scan()
        :param asg: Access security group information (TODO)
        :param minor_states: For enums, the minor alarm states
        :param major_states: For enums, the major alarm states
        :param server: The channel access server to attach to
        :param written_cb: A callback called when the value is written to via
            channel access. This overrides the default `written_to` method.
        :param scan_cb: A callback called when the scan event happens --
            when the PV should have its value updated. This overrides the
            default `scan` method.
        '''

        # TODO: asg
        if written_cb is None:
            written_cb = self.written_to
        elif not callable(written_cb):
            raise ValueError('written_cb is not callable')

        if scan_cb is None:
            scan_cb = self.scan
        elif not callable(scan_cb):
            raise ValueError('scan_cb is not callable')

        # PV type defaults to type(value)
        if type_ is None:
            type_ = type(value)
        elif value is not None:
            value = type_(value)

        if server is not None:
            name = server._strip_prefix(name)

        self._name = str(name)
        self._ca_type = caServer.type_map.get(type_, type_)
        self._precision = precision
        self._units = str(units)
        self._scan_rate = float(scan)
        self.scan = scan_cb
        self._written_cb = written_cb
        self._count = 0

        count = max(count, 0)

        if limits is None:
            self.limits = Limits()
        elif isinstance(limits, dict):
            self.limits = Limits(**limits)
        else:
            # TODO: Don't copy so limits can easily be
            #       updated for a group?
            self.limits = limits

        self._server = None
        self._value = value
        self._enums = []
        self._alarm = AlarmError.severity
        self._severity = AlarmError.severity
        self._updating = False

        if count == 0 and self._ca_type in caServer.numerical_types:
            alarm_fcn = self._check_numerical
        elif self._ca_type in caServer.enum_types:
            self._enums = list(self._value)
            self._value = self._value[0]

            alarm_fcn = self._check_enum

            self.minor_states = list(minor_states)
            self.major_states = list(major_states)
        elif self._ca_type in caServer.string_types:
            alarm_fcn = self._check_string
        elif count > 0 or (type_ is np.ndarray and isinstance(value, np.ndarray)):
            try:
                self._ca_type = caServer.type_map[value.dtype.type]
            except KeyError:
                raise ValueError('Unhandled numpy array type %s' % value.dtype)

            value = value.flatten()
            count = int(count)
            if count <= 0:
                self._count = value.size
            else:
                self._count = count

            alarm_fcn = lambda self: None

            if self._count < value.size:
                raise ValueError('Initial value too large for specified size')
            elif self._count > value.size:
                self._value = np.zeros(self._count, dtype=value.dtype)
                self._value[:value.size] = value
            else:
                self._value = value.copy()

        else:
            raise ValueError('Unhandled PV type "%s"' % type_)

        self._check_alarm = alarm_fcn

        self.touch()

        cas.casPV.__init__(self)

        if self._scan_rate > 0.0:
            self.thread = threading.Thread(target=self._scan_thread)
            self.thread.daemon = True
            self.thread.start()

        if server is not None:
            server.add_pv(self)

    @property
    def full_pvname(self):
        '''
        The full PV name, including the server prefix
        '''
        if self._server is None:
            raise ValueError('PV not yet added to a server')
        else:
            return ''.join((self._server.prefix, self._name))

    def __getitem__(self, idx):
        if self._count <= 0:
            raise IndexError('(%d) Not an array' % idx)
        else:
            return self._value[idx]

    def __setitem__(self, idx, value):
        self._value[idx] = value
        self.value = self._value

    def stop(self):
        '''
        Stop the scan loop
        '''
        self._updating = False

    def scan(self):
        '''
        Called at every `scan` second intervals

        Override this or specify scan_cb in the initializer.
        '''
        pass

    def _scan_loop(self):
        if self._scan_rate <= 0.0:
            return

        self._updating = True

        while self._updating:
            try:
                self.scan()
            except:
                self._updating = False
                raise

            time.sleep(self._scan_rate)

    def touch(self):
        '''
        Update the timestamp and alarm status (without changing the value)
        '''
        self._timestamp = cas.epicsTimeStamp()
        self._status, self._severity = self.check_alarm()

    @property
    def name(self):
        '''
        The PV name
        '''
        return self._name

    @property
    def alarm(self):
        '''
        Current alarm status
        '''
        return self._alarm

    @property
    def count(self):
        '''
        Array size
        '''
        return self._count

    @property
    def severity(self):
        '''
        Current alarm severity
        '''
        return self._severity

    def check_alarm(self, value=None):
        '''
        Check a value against this PV's alarm settings
        '''
        if value is None:
            value = self._value

        try:
            self._check_alarm(value)
        except (MinorAlarmError, MajorAlarmError) as ex:
            return (ex.alarm, ex.severity)

        return (alarms.NO_ALARM, 0)

    def _check_string(self, value):
        '''
        Alarm checking for string PVs
        '''
        pass

    def _check_numerical(self, value):
        '''
        Alarm checking for numerical PVs
        '''
        self.limits.check_alarm(value)

    def _check_enum(self, value):
        '''
        Alarm checking for enums
        '''
        if isinstance(value, int):
            value = self._enums[value]

        if value in self.major_states:
            raise MajorAlarmError('%s' % value,
                                  alarm=alarms.STATE_ALARM)
        elif value in self.minor_states:
            raise MinorAlarmError('%s' % value,
                                  alarm=alarms.STATE_ALARM)

    def _gdd_to_dict(self, gdd):
        '''
        Take a gdd value and dump the important parts into a dictionary
        '''
        timestamp = cas.epicsTimeStamp()
        gdd.getTimeStamp(timestamp)
        value = gdd.get()
        status, severity = self.check_alarm(value)
        return dict(timestamp=timestamp,
                    value=value,
                    status=status,
                    severity=severity)

    def _get_value(self):
        return self._value

    def _set_value(self, value, timestamp=None):
        if isinstance(value, cas.gdd):
            info = self._gdd_to_dict(value)

            self._timestamp = info['timestamp']
            self._value = info['value']
            self._status = info['status']
            self._severity = info['severity']
        else:
            gdd = cas.gdd()
            gdd.setPrimType(self._ca_type)

            if timestamp is None:
                timestamp = cas.epicsTimeStamp()

            self._timestamp = timestamp
            self._value = value
            self._status, self._severity = self.check_alarm()

            self._gdd_set_value(gdd)

            # Notify clients of the update
            self.postEvent(gdd)

    value = property(_get_value, _set_value)

    def resize(self, count=None, value=None):
        '''
        Resize an array PV, optionally specifying a new value

        If `count` is not specified, the size of `value` is used
        '''
        # TODO this works on server side, pyepics doesn't handle it
        #      well though
        raise NotImplementedError

        if self._count <= 0:
            raise ValueError('Cannot resize a scalar PV')
        elif count is None or count <= 0:
            if value is None:
                raise ValueError('Must specify count or value')

            count = value.size

        if value is not None:
            value = value.copy().flatten()
        else:
            value = self._value.copy()

        value.resize(count)

        self._count = count
        # Set the value and post the event
        self.value = value

    def written_to(self, timestamp=None, value=None,
                   status=None, severity=None):
        '''
        Default callback for when the PV is written to

        :raises: casAsyncCompletion (when asynchronous completion is desired)
        '''
        pass

    def get(self, **kwargs):
        '''
        Get the current value
        (acts like an epics.PV, otherwise just use pv.value)
        '''
        return self.value

    def put(self, value, **kwargs):
        '''
        Set the current value
        (acts like an epics.PV, otherwise just use pv.value = value)
        '''
        self.value = value

    def write(self, context, value):
        '''
        The PV was written to over channel access

        (internal function, override `written_to` instead)
        '''
        if self._written_cb is not None:
            try:
                info = self._gdd_to_dict(value)
                self._written_cb(**info)
            except casAsyncCompletion as ex:
                if self.hasAsyncWrite():
                    return casAsyncRunning.ret
                else:
                    self.startAsyncWrite(context)
                return ex.ret
            except casError as ex:
                return ex.ret
            except Exception as ex:
                logger.debug('written_cb failed: (%s) %s' % (ex.__class__.__name__, ex),
                             exc_info=ex)
                # TODO: no error for rejected values?
                return casSuccess.ret

        self.value = value
        return casSuccess.ret

    def async_done(self, ret=casSuccess.ret):
        '''
        Indicate to the server that the asynchronous write
        has completed
        '''
        if self.hasAsyncWrite():
            self.endAsyncWrite(ret)

    def writeNotify(self, context, value):
        '''
        An asynchronous write attempt was made

        (internal function)
        '''
        if self.hasAsyncWrite():
            # Another async task currently running
            return casAsyncRunning.ret

        return self.write(context, value)

    def _gdd_set_value(self, gdd):
        '''
        Update a gdd instance with the current value
        and alarm/severity
        '''
        if gdd.primitiveType() == cas.aitEnumInvalid:
            gdd.setPrimType(self._ca_type)

        if self._value is None:
            raise casUndefinedValueError()

        gdd.put(self._value)
        gdd.setStatSevr(self._alarm, self._severity)
        gdd.setTimeStamp(self._timestamp)

    # TODO can't get around writing these.
    #      underlying swigged C++ code needs to be modified.

    def _gdd_function(fcn, **kwargs):
        def wrapped(self, gdd):
            '''
            Internal pcaspy function; do not use
            '''
            try:
                ret = fcn(self, gdd, **kwargs)
            except casError as ex:
                logger.debug('caserror %s' % ex, exc_info=ex)
                return ex.ret
            except Exception as ex:
                logger.debug('gdd failed %s' % ex, exc_info=ex)
                return casUndefinedValueError.ret

            if ret is None:
                return casSuccess.ret

            return ret

        return wrapped

    def _gdd_attr(self, gdd, attr=''):
        '''
        Set the gdd value to (some attribute of this instance)
        '''
        try:
            value = getattr(self, attr)
        except:
            pass
        else:
            gdd.put(value)

    def _gdd_lim(self, gdd, attr=''):
        '''
        Set the gdd value to (some part of the limits)
        '''
        try:
            value = getattr(self.limits, attr)
        except:
            pass
        else:
            gdd.put(value)

    getValue = _gdd_function(_gdd_set_value)
    getPrecision = _gdd_function(_gdd_attr, attr='_precision')
    getHighLimit = _gdd_function(_gdd_lim, attr='hilim')
    getLowLimit = _gdd_function(_gdd_lim, attr='lolim')
    getHighAlarmLimit = _gdd_function(_gdd_lim, attr='hihi')
    getLowAlarmLimit = _gdd_function(_gdd_lim, attr='lolo')
    getHighWarnLimit = _gdd_function(_gdd_lim, attr='high')
    getLowWarnLimit = _gdd_function(_gdd_lim, attr='low')
    getUnits = _gdd_function(_gdd_attr, attr='_units')
    getEnums = _gdd_function(_gdd_attr, attr='_enums')

    def bestExternalType(self):
        '''
        Internal pcaspy function; do not use
        '''
        return self._ca_type

    def maxDimension(self):
        '''
        Internal pcaspy function; do not use
        '''
        if self._count >= 1:
            return 1
        else:
            return 0

    def maxBound(self, dims):
        '''
        Internal pcaspy function; do not use
        '''
        return self._count

    def __str__(self):
        return 'CasPV({0.name}, value={0.value},' \
               'alarm={0.alarm}, severity={0.severity})'.format(self)

    __repr__ = __str__


class CasRecord(CasPV):
    '''
    A channel access server record, starting out with just a
    VAL field. Additional fields can be added dynamically.
    '''

    def __init__(self, name, val_field, rtype=None,
                 desc='',
                 **kwargs):
        '''
        :param str name: The record prefix
        :param val_field: The default value for the value field
        :param str desc: The description field value
        :param str rtype: The record type to use
        '''
        assert '.' not in name, 'Record name cannot have periods'

        CasPV.__init__(self, name, val_field, **kwargs)

        self.fields = {}
        self.add_field('VAL', None, pv=self)

        if rtype is not None:
            self.add_field('RTYP', str(rtype))

        if desc is not None:
            self.add_field('DESC', str(desc))

    def field_pvname(self, field):
        return record_field(self.name, field)

    def __getitem__(self, field):
        return self.fields[field]

    def __setitem__(self, field, value):
        self.fields[field].value = value

    def add_field(self, field, value, pv=None, **kwargs):
        field = field.upper()
        if field in self.fields:
            raise ValueError('Field already exists')

        if pv is None:
            field_pv = self.field_pvname(field)
            kwargs.pop('server', '')
            pv = CasPV(field_pv, value, **kwargs)

        self.fields[field] = pv

    def __str__(self):
        return 'CasRecord({0.name!r}, value={0.value!r},' \
               'alarm={0.alarm}, severity={0.severity})'.format(self)

    __repr__ = __str__
