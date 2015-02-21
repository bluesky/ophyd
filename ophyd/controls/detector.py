# vi: ts=4 sw=4
'''
:mod:`ophyd.control.detector` - Ophyd Detectors Class
=====================================================

.. module:: ophyd.control.detector
   :synopsis:
'''

from __future__ import print_function
from ophyd.controls import SignalGroup


class Detector(SignalGroup):

    def __init__(self, sig1=None, sig2=None, **kwargs):
        '''Initialization logic here.'''

    def configure(self, *args, **kwargs):
        '''Called at the beginning of RunEngine.start_run() prior to collection starting.'''
        pass

    def deconfigure(self):
        '''Called at the exit of RunEngine.start_run() after collection concludes.'''
        pass

    def acquire(self, **kwargs):
        '''Configure and/or actuate the detector to affect acquisition.
           May be regarded as a "trigger"

           Called by the RunEngine.
           Returns None.
        '''
        raise NotImplementedError('Detector.acquire must be implemented in sub-classes.')

    def read(self, **kwargs):
        '''Retrieve data from instrumentation, format it, and return it.

           Returns (for example) dict: {data_key: value} or {data_key: [val0, val1,...]}
        '''
        raise NotImplementedError('Detector.read must be implemented in sub-classes.')
