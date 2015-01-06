'''
Channel access server implementation, based on pcaspy
'''

from __future__ import print_function

import threading
import logging

import numpy as np
from pcaspy import cas

from ...utils.epics_pvs import split_record_field
from .errors import casPVNotFoundError

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


class caServer(cas.caServer):
    type_map = {list: cas.aitEnumEnum16,
                tuple: cas.aitEnumEnum16,
                str: cas.aitEnumString,
                float: cas.aitEnumFloat64,
                int: cas.aitEnumInt32,
                bool: cas.aitEnumInt32,

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
    default_instance = None

    def __init__(self, prefix, start=True, default=True):
        cas.caServer.__init__(self)

        self._pvs = {}
        self._thread = None
        self._running = False
        self._prefix = str(prefix)

        if start:
            self.start()

        if default and caServer.default_instance is None:
            caServer.default_instance = self

            self._attach_cas_functions()

    # TODO asCaStop when all are stopped:
    #  cas.asCaStop()

    def _attach_cas_functions(self):
        from . import CasFunction

        for fcn in list(CasFunction._to_attach):
            if fcn._server is None:
                fcn.attach_server(self)

        del CasFunction._to_attach[:]

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
        '''
        Add a PV instance to the server
        '''
        name = self._strip_prefix(pvi.name)

        if name in self._pvs:
            raise ValueError('PV already exists')

        self._pvs[name] = pvi
        pvi._server = self

    def remove_pv(self, pvi):
        '''
        Remove a PV instance from the server
        '''
        if isinstance(pvi, str):
            name = pvi
        else:
            name = pvi.name

        name = self._strip_prefix(name)

        if name not in self._pvs:
            raise ValueError('PV not in server')

        del self._pvs[name]
        pvi._server = None

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
