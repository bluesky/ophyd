'''
'''

from __future__ import print_function
import functools
import inspect
import logging
import time

import epics

from .pv import CasPV
from .errors import casAsyncCompletion
from . import caServer

logger = logging.getLogger(__name__)


class CasFunction(object):
    '''
    Channel Access Server function decorator
    '''

    _to_attach = []

    def __init__(self, prefix='', server=None,
                 async=True, failed_cb=None,
                 process_pv='Proc', use_process=True,
                 retval_pv='Val',
                 return_value=0.0,
                 ):
        '''
        '''

        if server is None and caServer.default_instance is not None:
            server = caServer.default_instance

        self._prefix = str(prefix)
        self._server = server
        self._async = bool(async)
        self._functions = {}
        self._failed_cb = failed_cb
        self._async_threads = {}
        self._process_pv = str(process_pv)
        self._use_process = bool(use_process)
        self._retval_pv = str(retval_pv)
        self._default_retval = return_value

        if not self._use_process:
            self._async = False

    def attach_server(self, server):
        if self._server is not None:
            raise ValueError('Server already attached')

        self._server = server

        for name in self._functions.keys():
            try:
                self._add_fcn(name)
            except Exception as ex:
                print('Failed to add function: %s (%s)' % (name, ex))
                logger.error('Failed to add function: %s (%s)' % (name, ex), exc_info=ex)
                del self._functions[name]

        if self in CasFunction._to_attach:
            CasFunction._to_attach.remove(self)

    def _add_fcn(self, name):
        server = self._server
        if server is None:
            # The next caServer created will attach to these functions
            if self not in CasFunction._to_attach:
                CasFunction._to_attach.append(self)

            return

        fcn_prefix = self._prefix
        if not fcn_prefix:
            fcn_prefix = '%s:' % name

        info = self._functions[name]
        params = info['parameters']

        pv_kw = {}
        if self._use_process:
            proc_pv = CasPV(''.join((fcn_prefix, self._process_pv)), 0,
                            written_cb=info['wrapped'])
        else:
            pv_kw['written_cb'] = info['wrapped']
            proc_pv = None

        retval_pv = CasPV(''.join((fcn_prefix, self._retval_pv)), self._default_retval)

        param_pvs = [CasPV(''.join((fcn_prefix, param)), value, **pv_kw)
                     for param, value in params]

        added = []
        try:
            for pv in param_pvs + [proc_pv, retval_pv]:
                if pv is not None:
                    print('Adding', pv)
                    server.add_pv(pv)
                    added.append(pv)
        except Exception as ex:
            logger.error('Failed to add function: %s (%s)' % (name, ex), exc_info=ex)

            # If failed in adding any of the PVs, remove all that were added
            for pv in added:
                server.remove_pv(pv)

            raise

        info['process_pv'] = proc_pv
        info['retval_pv'] = retval_pv
        info['param_pvs'] = param_pvs

    def _failed(self, name, msg, ex, kwargs):
        failed_cb = self._failed_cb

        if failed_cb is not None:
            try:
                failed_cb(name=name, ex=ex, kwargs=kwargs)
            except:
                pass
        else:
            logger.error(msg, exc_info=ex)

    def _run_function(self, name, **kwargs):
        info = self._functions[name]
        fcn = info['function']

        kwargs = self.get_kwargs(name, **kwargs)

        try:
            ret = fcn(**kwargs)
        except Exception as ex:
            self._failed(name, 'CAS function failed: %s (%s)' % (name, ex.__class__.__name__),
                         ex, kwargs)

        try:
            info['retval_pv'].value = ret
        except Exception as ex:
            self._failed(name, 'CAS retval invalid: %s (%s)' % (name, ex.__class__.__name__),
                        ex, kwargs)

        if self._async and name in self._async_threads:
            del self._async_threads[name]

            info['process_pv'].async_done()

        return ret

    def _run_async(self, name, **kwargs):
        thread = epics.ca.CAThread(target=self._run_function,
                                   args=(name, ), kwargs=kwargs)
        self._async_threads[name] = thread
        thread.start()

    def get_kwargs(self, name, **override):
        info = self._functions[name]
        param_pvs = zip(info['parameters'], info['param_pvs'])
        ret = dict((param, pv.value)
                   for (param, default), pv in param_pvs)

        ret.update(override)
        return ret

    def get_pvnames(self, name):
        if not self._server:
            raise RuntimeError('Server not yet configured (i.e., no prefix yet)')

        info = self._functions[name]
        param_pvs = zip(info['parameters'], info['param_pvs'])
        ret = dict((param, pv.full_pvname)
                   for (param, default), pv in param_pvs)

        ret['retval'] = info['retval_pv'].full_pvname
        if self._use_process:
            ret['process'] = info['process_pv'].full_pvname

        return ret

    def __call__(self, fcn):
        @functools.wraps(fcn)
        def wrapped_sync(**cas_kw):
            # Block until async request finishes
            while name in self._async_threads:
                time.sleep(0.05)

            return self._run_function(name)

        @functools.wraps(fcn)
        def wrapped_async(**cas_kw):
            self._run_async(name)
            raise casAsyncCompletion()

        if self._async:
            wrapped = wrapped_async
        else:
            wrapped = wrapped_sync

        spec = inspect.getargspec(fcn)
        args, var_args, var_kws, defaults = spec
        if len(args) != len(defaults) or var_args:
            raise ValueError('All arguments must have defaults')

        name = fcn.__name__
        if name in self._functions:
            raise ValueError('Function already registered')

        info = self._functions[name] = {}

        info['parameters'] = list(zip(args, defaults))
        info['function'] = fcn
        info['wrapped'] = wrapped
        self._add_fcn(name)

        wrapped_sync.wrapper = self
        wrapped_async.wrapper = self

        def get_pvnames():
            return self.get_pvnames(name)

        wrapped_sync.get_pvnames = get_pvnames
        return wrapped_sync
