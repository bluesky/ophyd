from __future__ import print_function
import signal


from ..controls.positioner import Positioner
from ..controls.signal import (OphydObject, Signal, SignalGroup)
from ..runengine import RunEngine


class SessionManager(object):
    _instance = None

    def __init__(self, logger, ipy):
        if SessionManager._instance is not None:
            raise RuntimeError('SessionManager already instantiated.')

        SessionManager._instance = self
        self._ipy = ipy
        self._logger = logger
        self._run_engine = None
        self._registry = {'positioners': {}, 'signals': {},
                        'beamline_config': {}}

        session_mgr = self
        self._ipy.push('session_mgr')

        orig_hdlr = signal.getsignal(signal.SIGINT)

        def sigint_hdlr(sig, frame):
            self._logger.debug('Calling SessionManager SIGINT handler...')
            self.stop_all()
            orig_hdlr(sig, frame)
        signal.signal(signal.SIGINT, sigint_hdlr)
        self._ipy.push('sigint_hdlr')

        #Restore _scan_id from IPy user_ns.
        #Relying on c.StoreMagics.autorestore = True in ophyd IPy profile.
        try:
            scanid = self._ipy.user_ns['_scan_id']
            self._logger.debug('Last scan id = %s' % scanid) 
        except KeyError:
            self._logger.debug('SessionManager could not find a scan_id.')
            self._logger.debug('Resetting scan_id to 1...')
            self._ipy.user_ns['_scan_id'] = 1
            self._ipy.run_line_magic('store', '_scan_id')


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
        return self._ipy.user_ns['_scan_id']

    def get_next_scan_id(self):
        '''Increments the current scan_id by one and returns the value.
           Then, persists the scan_id using IPython's "%store" magics.
        '''
        self._ipy.user_ns['_scan_id'] += 1
        self._ipy.run_line_magic('store', '_scan_id')
        return self._ipy.user_ns['_scan_id']

    def set_scan_id(self, value):
        self._ipy.user_ns['_scan_id'] = value
        self._ipy.run_line_magic('store', '_scan_id')
