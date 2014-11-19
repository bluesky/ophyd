# vi: ts=4 sw=4
'''
:mod:`ophyd.control.areadetector` - areaDetector
================================================

.. module:: ophyd.control.areadetector
 :synopsis:  `areaDetector`_ camera and plugin abstractions

.. _areaDetector: http://cars.uchicago.edu/software/epics/areaDetector.html

'''

from __future__ import print_function

from .signal import SignalGroup

import logging

logger = logging.getLogger(__name__)

class AreaDetector(SignalGroup):
    pass
