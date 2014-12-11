from __future__ import print_function
import signal
import atexit
import warnings

from ..controls.positioner import Positioner
from ..controls.signal import (OphydObject, Signal, SignalGroup)
from ..runengine import RunEngine

try:
    from ..utils.cas import caServer
except ImportError:
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


class SessionManager(object):
    _instance = None

    def __init__(self, logger, ipy=None):
        if SessionManager._instance is not None:
            raise RuntimeError('SessionManager already instantiated.')

        if ipy is None:
            ipy = _FakeIPython()

        SessionManager._instance = self
        self._ipy = ipy
        self._logger = logger
        self._run_engine = None
        self._registry = {'positioners': {}, 'signals': {},
                          'beamline_config': {}}

        session_mgr = self
        self._ipy.push('session_mgr')

        # Override the IPython exit request function
        self._ipy_exit = self._ipy.ask_exit
        self._ipy.ask_exit = self._ask_exit

        orig_hdlr = signal.getsignal(signal.SIGINT)

        def sigint_hdlr(sig, frame):
            self._logger.debug('Calling SessionManager SIGINT handler...')
            self.stop_all()
            orig_hdlr(sig, frame)

        signal.signal(signal.SIGINT, sigint_hdlr)
        self._ipy.push('sigint_hdlr')

        if caServer is not None:
            self._cas = caServer()
        else:
            self._logger.info('pcaspy is unavailable; channel access server disabled')
            self._cas = None

        atexit.register(self._cleanup)

        self.persist_var('_persisting', [], desc='persistence list')
        self.persist_var('_scan_id', 1, desc='Scan ID')

    @property
    def persisting(self):
        return self['_persisting']

    @property
    def ipy_config(self):
        '''
        The IPython configuration
        '''
        return self._ipy.config

    @property
    def in_ipython(self):
        return not isinstance(self._ipy, _FakeIPython)

    def persist_var(self, name, value=0, desc=None):
        if not self.in_ipython:
            return

        config = self.ipy_config
        if not config.StoreMagics.autorestore:
            warnings.warn('StoreMagics.autorestore not enabled; variable persistence disabled')

            if name not in self:
                self[name] = value
                self._logger.debug('Setting %s = %s' % (name, value))
            return self[name]

        if name not in self.persisting:
            self.persisting.append(name)

        if name not in self:
            if desc is not None:
                self._logger.debug('SessionManager could not find %s (%s).' % (name, desc))
                self._logger.debug('Resetting %s to %s' % (name, value))

            self[name] = value
        else:
            value = self[name]
            if desc is not None:
                self._logger.debug('Last %s = %s' % (desc, self[name]))

        self._ipy.run_line_magic('store', name)
        return value

    @property
    def cas(self):
        '''
        Channel Access Server instance
        '''
        return self._cas

    def _cleanup(self):
        '''
        Called when exiting IPython is confirmed
        '''
        if self._cas is not None:
            self._cas.stop()

        persisting = [name for name in self.persisting
                      if name in self]

        for name in persisting:
            self._ipy.run_line_magic('store', name)

    def _ask_exit(self):
        # TODO tweak this behavior as desired; one ctrl-D stops the scan,
        #      two confirms exit

        run = self._run_engine
        if run is not None:
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
        elif isinstance(obj, RunEngine):
            if self._run_engine is None:
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
            self._run_engine.stop()

        for pos in self._registry['positioners'].itervalues():
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
        return self['_scan_id']

    def set_scan_id(self, value):
        self['_scan_id'] = value

    # TODO: does this make sense for the session? up for suggestions
    def __getitem__(self, key):
        return self._ipy.user_ns[key]

    def __setitem__(self, key, value):
        self._ipy.user_ns[key] = value

    def __contains__(self, key):
        return key in self._ipy.user_ns
