# vi: ts=4 sw=4
'''
:mod:`ophyd.controls.cas.function` - CAS Functions
==================================================

.. module:: ophyd.controls.cas.function
   :synopsis: RPC-like functionality via channel access for Python functions
              with a simple decorator
'''

from __future__ import print_function
import functools
import inspect
import logging
import time
from collections import OrderedDict

import epics

from .pv import CasPV
from .errors import casAsyncCompletion
from . import caServer

logger = logging.getLogger(__name__)


class CasFunction(object):
    '''Channel Access Server function decorator

    RPC-like functionality via channel access for Python functions

    Parameters
    ----------
    prefix : str, optional
        The prefix to use (defaults to the function name)
    server : caServer, optional
        The channel access server to use (defaults to the currently running one,
        or the next instantiated one if not specified)
    async : bool, optional
        Function should be called asynchronously, in its own thread (do not set
        to False when doing large calculations or any blocking in the function)
    failed_cb : callable, optional
        When an exception is raised inside the function, `failed_cb` will be
        called.
    process_pv : str, optional
        PV name for the Process PV, used to start the calculation
    use_process : bool, optional
        If True, process_pv is created. Otherwise, the function will be called
        when each parameter is written to.
    retval_pv : str, optional
        Return value PV name
    status_pv : str, optional
        Status PV name
    return_value : , optional
        Default value for the return value
    return_kwargs : , optional
        Keyword arguments are passed to the return value CasPV initializer. You
        can then specify `count`, `type_`, etc. here
    '''
    _to_attach = []

    def __init__(self, prefix='', server=None,
                 async=True, failed_cb=None,
                 process_pv='Proc', use_process=True,
                 retval_pv='Val',
                 status_pv='Sts',
                 return_value=0.0,
                 **return_kwargs
                 ):

        if server is None and caServer.default_instance is not None:
            server = caServer.default_instance

        self._prefix = str(prefix)
        self._server = server
        self._async = bool(async)
        self._functions = {}
        self._failed_cb = failed_cb
        self._async_threads = {}
        self._process_pv = str(process_pv)
        self._status_pv = str(status_pv)
        self._use_process = bool(use_process)
        self._retval_pv = str(retval_pv)
        self._default_retval = return_value
        self._return_kwargs = return_kwargs

        if not self._use_process:
            self._async = False

    def attach_server(self, server):
        '''Attach a channel access server instance'''
        if self._server is not None:
            raise ValueError('Server already attached')

        self._server = server

        for name in self._functions.keys():
            try:
                self._add_fcn(name)
            except Exception as ex:
                # print('Failed to add function: %s (%s)' % (name, ex))
                logger.error('Failed to add function: %s (%s)' % (name, ex), exc_info=ex)
                del self._functions[name]

        if self in CasFunction._to_attach:
            CasFunction._to_attach.remove(self)

    def _add_fcn(self, name):
        '''Add a function to the list being handled.

        If a channel access server isn't attached yet, queue this instance to be
        added at a later point.
        '''
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
        defaults = info['defaults']

        pv_kw = {}
        if self._use_process:
            proc_pv = CasPV(''.join((fcn_prefix, self._process_pv)), 0,
                            written_cb=info['wrapped'])
        else:
            pv_kw['written_cb'] = info['wrapped']
            proc_pv = None

        retval_pv = CasPV(''.join((fcn_prefix, self._retval_pv)),
                          self._default_retval,
                          **self._return_kwargs)

        status_pv = CasPV(''.join((fcn_prefix, self._status_pv)),
                          'status')

        param_pvs = [CasPV(''.join((fcn_prefix, param)),
                           default,
                           **pv_kw)
                     for param, default in zip(params, defaults)]

        added = []
        try:
            for pv in param_pvs + [proc_pv, retval_pv, status_pv]:
                if pv is not None:
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
        info['status_pv'] = status_pv
        info['param_pvs'] = param_pvs

        pv_dict = OrderedDict(zip(params, param_pvs))
        pv_dict['retval'] = retval_pv
        pv_dict['process'] = proc_pv
        pv_dict['status'] = status_pv

        info['param_dict'] = pv_dict

    def _failed(self, name, msg, ex, kwargs):
        '''Failure condition - since functions are called asynchronously in
        background threads, a few options are given to the user for error
        reporting. First, the status_pv for the corresponding function is
        updated. If a failure callback was specified in the decorator, it will
        then be called. If no failure callback is specified, the module logger
        will be used.
        '''
        failed_cb = self._failed_cb

        info = self._functions[name]
        status_pv = info['status_pv']
        if status_pv.server is not None:
            try:
                status_pv.value = msg
            except:
                pass

        if failed_cb is not None:
            try:
                failed_cb(name=name, ex=ex, kwargs=kwargs)
            except:
                pass
        else:
            logger.error(msg, exc_info=ex)

    def _run_function(self, name, **kwargs):
        '''Run the function in this thread, with the kwargs passed'''
        info = self._functions[name]
        fcn = info['function']

        kwargs = self.get_kwargs(name, **kwargs)

        try:
            ret = fcn(**kwargs)
        except Exception as ex:
            self._failed(name, '%s: %s (%s)' % (ex.__class__.__name__, ex, name),
                         ex, kwargs)
            ret = None

        try:
            if ret is not None:
                info['retval_pv'].value = ret
        except Exception as ex:
            self._failed(name, 'Retval: %s %s (%s)' % (ex.__class__.__name__, ex, name),
                         ex, kwargs)

        if self._async and name in self._async_threads:
            del self._async_threads[name]

            info['process_pv'].async_done()

        return ret

    def _run_async(self, name, **kwargs):
        '''Run a function asynchronously, in a separate thread'''
        thread = epics.ca.CAThread(target=self._run_function,
                                   args=(name, ), kwargs=kwargs)
        self._async_threads[name] = thread
        thread.start()

    def get_kwargs(self, name, **override):
        '''Get the keyword arguments to be passed to the function.

        These come from the current values stored in the channel access server
        process variables.
        '''
        info = self._functions[name]

        pv_dict = info['param_dict']
        parameters = info['parameters']
        ret = dict((param, pv_dict[param].value)
                   for param in parameters)

        ret.update(override)
        return ret

    def get_pv_instance(self, name, pv):
        '''Grab a parameter's PV instance from a specific function, by name'''
        if not self._server:
            raise RuntimeError('Server not yet configured (i.e., no prefix yet)')

        info = self._functions[name]
        param_pvs = info['param_dict']
        return param_pvs[pv]

    def get_pvnames(self, name):
        '''Get all PV names for a specific function in a dictionary:
            {param: pvname}
        '''
        if not self._server:
            raise RuntimeError('Server not yet configured (i.e., no prefix yet)')

        info = self._functions[name]
        ret = dict((param, pv.full_pvname)
                   for param, pv in info['param_dict'].items())

        return ret

    def __call__(self, fcn):
        '''Wraps the function'''
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
        if (args and len(args) != len(defaults)) or var_args:
            raise ValueError('All arguments must have defaults')

        name = fcn.__name__
        if name in self._functions:
            raise ValueError('Function already registered')

        info = self._functions[name] = {}

        if args:
            parameters = list(zip(args, defaults))
        else:
            parameters = []

        info['parameters'] = [param for param, default in parameters]
        info['defaults'] = [default for param, default in parameters]
        info['function'] = fcn
        info['wrapped'] = wrapped
        self._add_fcn(name)

        wrapped_sync.wrapper = self
        wrapped_async.wrapper = self

        def get_pvnames():
            return self.get_pvnames(name)

        def get_pv(pv):
            return self.get_pv_instance(name, pv)

        wrapped_sync.get_pvnames = get_pvnames
        wrapped_sync.get_pv = get_pv
        return wrapped_sync
