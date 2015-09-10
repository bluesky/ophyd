
from __future__ import print_function
import signal
import atexit
import warnings

import epics

from ..controls.positioner import Positioner
from ..controls.signal import (OphydObject, Signal, SignalGroup)
from ..utils.epics_pvs import MonitorDispatcher
from ..runengine.run import Run

try:
    from ..controls.cas import caServer
except ImportError as ex:
    print(ex)
    caServer = None

__all__ = ['SessionManager']


class _FakeIPython(object):
    user_ns = {}

    def _no_op(self, *args, **kwargs):
        pass

    config = None
    ask_exit = _no_op
    push = _no_op
    run_line_magic = _no_op
    __getattr__ = _no_op
    __setattr__ = _no_op


class SessionManager(object):
    '''The singleton session manager

    Parameters
    ----------
    logger : logging.Logger
    ipy : IPython session, optional
    '''
    _instance = None

    def __init__(self, logger, ipy=None):
        if SessionManager._instance is not None:
            raise RuntimeError('SessionManager already instantiated.')

        if ipy is None:
            ipy = _FakeIPython()

        SessionManager._instance = self
        self._ipy = ipy
        self._ipy.push(dict(session_mgr=self))

        self._logger = logger
        self._run_engine = None
        self._registry = {'positioners': {}, 'signals': {},
                          'beamline_config': {}}

        self._dispatcher = None
        self._setup_epics()

        # Override the IPython exit request function
        self._ipy_exit = self._ipy.ask_exit
        self._ipy.ask_exit = self._ask_exit

        self._setup_sigint()

        if caServer is not None:
            self._cas = caServer('OPHYD_SESSION:')
            # TODO config should override this?
        else:
            self._logger.info('pcaspy is unavailable; channel access server disabled')
            self._cas = None

        atexit.register(self._cleanup)

        self.persist_var('_persisting', [], desc='persistence list')
        self.persist_var('_scan_id', 1, desc='Scan ID')

    def _setup_sigint(self):
        '''Setup the signal interrupt handler'''
        self._orig_sigint_hdlr = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self.sigint_hdlr)

        # Expose it to IPython as well
        self._ipy.push(dict(sigint_hdlr=self.sigint_hdlr))

    def sigint_hdlr(self, sig, frame):
        '''Default ophyd signal interrupt (ctrl-c) handler'''
        self._logger.debug('Calling SessionManager SIGINT handler...')
        self.stop_all()
        self._orig_sigint_hdlr(sig, frame)
        raise KeyboardInterrupt

    @property
    def persisting(self):
        return self['_persisting']

    @property
    def ipy_config(self):
        '''The IPython configuration'''
        return self._ipy.config

    @property
    def in_ipython(self):
        return not isinstance(self._ipy, _FakeIPython)

    @property
    def autorestore(self):
        '''Check for Magics autorestore and return it.'''
        config = self.ipy_config

        try:
            return config.StoreMagics.autorestore
        except AttributeError:
            try:
                return config.StoreMagic.autorestore
            except AttributeError:
                pass

    def persist_var(self, name, value=0, desc=None):
        if not self.in_ipython:
            return value

        config = self.ipy_config
        if not self.autorestore:
            warnings.warn('StoreMagic.autorestore not enabled; variable persistence disabled')

            if name not in self:
                self[name] = value
                self._logger.debug('Setting %s = %s' % (name, value))
            return self[name]

        if name not in self:
            if desc is not None:
                self._logger.debug('SessionManager could not find %s (%s).' % (name, desc))
                self._logger.debug('Resetting %s to %s' % (name, value))

            self[name] = value
        else:
            value = self[name]
            if desc is not None:
                self._logger.debug('Last %s = %s' % (desc, self[name]))

        if name not in self.persisting:
            self.persisting.append(name)

        self._ipy.run_line_magic('store', name)
        return value

    def _cleanup(self):
        '''Called when exiting IPython is confirmed'''
        if self._dispatcher.is_alive():
            self._dispatcher.stop()
            self._dispatcher.join()

        epics.ca.finalize_libca()

        if self._cas is not None:
            # Stopping the channel access server causes disconnections right as
            # the program is quitting. To stop it from being noisy and
            # polluting stdout with needless tracebacks, set the pyepics
            # events callback filters to not do anything.
            epics.ca._onGetEvent = lambda *args, **kwargs: 0
            epics.ca._onMonitorEvent = lambda *args, **kwargs: 0
            epics.ca.get_cache = lambda *args, **kwargs: {}

            self._cas.stop()

        if self.in_ipython:
            persisting = [name for name in self.persisting
                          if name in self]

            for name in persisting:
                self._ipy.run_line_magic('store', name)

    def _ask_exit(self):
        '''Called when the user tries to quit the IPython session

        One ctrl-D stops the scan, two confirms exit
        '''


        run = self._run_engine
        if run is not None and run.state in ('acquiring', 'suspended'):
            self.stop_all()
            run.stop()
        else:
            self._ipy_exit()

    def _update_registry(self, obj, category):
        if obj not in self._registry[category] and obj.name is not None:
            self._registry[category][obj.name] = obj

    # TODO: figure out what the policy needs to be here...
    def register(self, obj):
        '''Maintain a dict of positioners and detectors.

           If these objects are loaded via "ipython -i conf_script.py",
           then they're available in the ipy namespace too.
        '''
        if isinstance(obj, Positioner):
            self._update_registry(obj, 'positioners')
        elif isinstance(obj, (Signal, SignalGroup)):
            self._update_registry(obj, 'signals')
        elif isinstance(obj, Run):
            self._logger.debug('Registering RunEngine.')
            self._run_engine = obj
        elif isinstance(obj, OphydObject):
            # TODO
            pass
        else:
            raise TypeError('%s cannot be registered with the session.' % obj)
        return self._logger

    #TODO: should swallow and gracefully notify the user of changes
    def notify_connection(self, msg):
        self._logger.debug('connection notification: %s' % msg)

    def stop_all(self):
        #TODO: fixme - add RunEngines to registry
        if self._run_engine is not None:
            if self._run_engine.state == 'acquiring':
                self._run_engine.pause()
            elif self._run_engine.state == 'suspended':
                self._run_engine.stop(status='abort')

        for pos in self._registry['positioners'].values():
            if pos.moving is True:
                pos.stop()
                self._logger.debug('Stopped %s' % pos)

    def get_positioners(self):
        return self._registry['positioners']

    #TODO: should we let this raise a KeyError exception? Probably...
    def get_positioner(self, pos):
        return self._registry['positioners'][pos]

    def get_current_scan_id(self):
        return self['_scan_id']

    def get_next_scan_id(self):
        '''Increments the current scan_id by one and returns the value.
           Then, persists the scan_id using IPython's "%store" magics.
        '''
        self['_scan_id'] += 1
        return self.persist_var('_scan_id', value=self['_scan_id'])

    def set_scan_id(self, value):
        '''Set scan_id to value, then persist via IPython "%store" magic.'''
        self['_scan_id'] = value
        self.persist_var('_scan_id', value=value)

    def __getitem__(self, key):
        '''Grab variables from the IPython namespace'''
        return self._ipy.user_ns[key]

    def __setitem__(self, key, value):
        '''Set variables in the IPython namespace'''
        self._ipy.user_ns[key] = value

    def __contains__(self, key):
        return key in self._ipy.user_ns

    @property
    def cas(self):
        '''Channel Access Server instance'''
        return self._cas

    @property
    def dispatcher(self):
        '''The monitor dispatcher'''
        return self._dispatcher

    def _setup_epics(self):
        # It's important to use the same context in the callback dispatcher
        # as the main thread, otherwise not-so-savvy users will be very
        # confused
        epics.ca.use_initial_context()

        self._dispatcher = MonitorDispatcher()

        self._ipy.push(dict(caget=epics.caget,
                            caput=epics.caput,
                            camonitor=epics.camonitor,
                            cainfo=epics.cainfo))
