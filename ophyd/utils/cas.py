from __future__ import print_function

import time
import threading
import logging

import numpy as np
from pcaspy import cas

from .errors import (AlarmError, MajorAlarmError, MinorAlarmError)
from .errors import alarms
from .epics_pvs import (split_record_field, record_field)


logger = logging.getLogger(__name__)


def patch_swig(mod):
    '''
    ref: http://sourceforge.net/p/swig/bugs/1255/
    Workaround for setters failing with swigged classes
    '''

    def fix(self, class_type, name, value, static=1):
        if name == "thisown":
            return self.this.own(value)
        elif name == "this" and type(value).__name__ == 'SwigPyObject':
            self.__dict__[name] = value
            return

        method = class_type.__swig_setmethods__.get(name, None)
        if method:
            return method(self, value)
        elif not static:
            object.__setattr__(self, name, value)
        else:
            raise AttributeError("You cannot add attributes to %s" % self)

    cas.epicsTimeStamp.__repr__ = cas.epicsTimeStamp.__str__

    if hasattr(mod, '_swig_setattr_nondynamic'):
        mod._swig_setattr_nondynamic = fix
        logger.debug('patched SWIG setattr')


patch_swig(cas)


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


class caServer(cas.caServer):
    type_map = {list: cas.aitEnumEnum16,
                tuple: cas.aitEnumEnum16,
                str: cas.aitEnumString,
                float: cas.aitEnumFloat64,
                int: cas.aitEnumInt32,

                np.int8: cas.aitEnumInt8,
                np.uint8: cas.aitEnumUint8,
                np.int16: cas.aitEnumInt16,
                np.uint16: cas.aitEnumUint16,
                np.int32: cas.aitEnumInt32,
                np.uint32: cas.aitEnumUint32,
                np.float32: cas.aitEnumFloat32,
                np.float64: cas.aitEnumFloat64,
                }

    string_types = (cas.aitEnumString, cas.aitEnumFixedString, cas.aitEnumUint8)
    enum_types = (cas.aitEnumEnum16, )
    numerical_types = (cas.aitEnumFloat64, cas.aitEnumInt32)

    def __init__(self, prefix, start=True):
        cas.caServer.__init__(self)

        self._pvs = {}
        self._thread = None
        self._running = False
        self._prefix = str(prefix)

        if start:
            self.start()

    # TODO asCaStop when all are stopped:
    #  cas.asCaStop()

    def _get_prefix(self):
        '''
        The channel access prefix, shared by all PVs added to this server.
        '''
        return self._prefix

    def _set_prefix(self, prefix):
        if prefix != self._prefix:
            # TODO any special handling?
            logger.debug('New PV prefix %s -> %s' % (self._prefix, prefix))
            self._prefix = prefix

    prefix = property(_get_prefix, _set_prefix)

    def __getitem__(self, pv):
        return self.get_pv(pv)

    def get_pv(self, pv):
        pv = self._strip_prefix(pv)

        if '.' in pv:
            record, field = split_record_field(pv)
            if record in self._pvs:
                rec = self._pvs[record]
                return rec[field]

        return self._pvs[pv]

    def add_pv(self, pvi):
        name = self._strip_prefix(pvi.name)

        if name in self._pvs:
            raise ValueError('PV already exists')

        self._pvs[name] = pvi

    def _strip_prefix(self, pvname):
        '''
        Remove the channel access server prefix from the pv name
        '''
        if pvname[:len(self._prefix)] == self._prefix:
            return pvname[len(self._prefix):]
        else:
            return pvname

    def pvExistTest(self, context, addr, pvname):
        if not pvname.startswith(self._prefix):
            return cas.pverDoesNotExistHere

        try:
            self.get_pv(pvname)
        except KeyError:
            return cas.pverDoesNotExistHere
        else:
            logger.debug('Responded %s exists' % pvname)
            return cas.pverExistsHere

    def pvAttach(self, context, pvname):
        try:
            pvi = self.get_pv(pvname)
        except KeyError:
            print('not found', pvname)
            return casPVNotFoundError.ret

        logger.debug('PV attach %s' % (pvname, ))
        return pvi

    def initAccessSecurityFile(self, filename, **subst):
        # TODO
        macros = ','.join(['%s=%s' % (k, v)
                           for k, v in subst.items()])
        cas.asInitFile(filename, macros)
        cas.asCaStart()

    def _process_loop(self, timeout=0.1):
        self._running = True

        while self._running:
            cas.process(timeout)

    def start(self):
        if self._thread is not None:
            return

        self._thread = threading.Thread(target=self._process_loop)
        self._thread.daemon = True
        self._thread.start()

    @property
    def running(self):
        return self._running

    def stop(self, wait=True):
        if self._running:
            self._running = False

            if wait:
                self._thread.join()
            self._thread = None

    def cleanup(self):
        self.stop()
        self._pvs.clear()


class PythonPV(cas.casPV):
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

        if limits is None:
            self.limits = Limits()
        elif isinstance(limits, dict):
            self.limits = Limits(**limits)
        else:
            # TODO: Don't copy so limits can easily be
            #       updated for a group?
            self.limits = limits

        self._value = value
        self._enums = []
        self._alarm = AlarmError.severity
        self._severity = AlarmError.severity
        self._updating = False

        if self._ca_type in caServer.numerical_types:
            alarm_fcn = self._check_numerical
        elif self._ca_type in caServer.enum_types:
            self._enums = list(self._value)
            self._value = self._value[0]

            alarm_fcn = self._check_enum

            self.minor_states = list(minor_states)
            self.major_states = list(major_states)
        elif self._ca_type in caServer.string_types:
            alarm_fcn = self._check_string
        elif type_ is np.ndarray and isinstance(value, np.ndarray):
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
        return 'PythonPV({0.name}, value={0.value},' \
               'alarm={0.alarm}, severity={0.severity})'.format(self)

    __repr__ = __str__


class PythonRecord(PythonPV):
    '''
    A channel access server record, starting out with just a
    VAL field. Additional fields can be added dynamically.
    '''

    def __init__(self, name, val_field,
                 **kwargs):

        assert '.' not in name, 'Record name cannot have periods'

        PythonPV.__init__(self, name, val_field, **kwargs)

        self.fields = {}
        self.add_field('VAL', None, pv=self)

    def field_pvname(self, field):
        return record_field(self.name, field)

    def __getitem__(self, field):
        return self.fields[field]

    def add_field(self, field, value, pv=None, **kwargs):
        field = field.upper()
        if field in self.fields:
            raise ValueError('Field already exists')

        if pv is None:
            field_pv = self.field_pvname(field)
            kwargs.pop('server', '')
            pv = PythonPV(field_pv, value, **kwargs)

        self.fields[field] = pv

    def __str__(self):
        return 'PythonRecord({0.name}, value={0.value},' \
               'alarm={0.alarm}, severity={0.severity})'.format(self)

    __repr__ = __str__
