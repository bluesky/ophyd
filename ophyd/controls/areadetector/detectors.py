# vi: ts=4 sw=4
'''
:mod:`ophyd.control.areadetector` - areaDetector
================================================

.. module:: ophyd.controls.areadetector.detectors
 :synopsis:  `areaDetector`_ detector abstractions

.. _areaDetector: http://cars.uchicago.edu/software/epics/areaDetector.html
'''

from __future__ import print_function
import logging

from .base import (ADBase, ADComponent as C)
from . import cam

logger = logging.getLogger(__name__)


__all__ = ['AreaDetector',
           'Andor3Detector',
           'AndorDetector',
           'BrukerDetector',
           'FirewireLinDetector',
           'FirewireWinDetector',
           'LightFieldDetector',
           'Mar345Detector',
           'MarCCDDetector',
           'PerkinElmerDetector',
           'PilatusDetector',
           'PixiradDetector',
           'PointGreyDetector',
           'ProsilicaDetector',
           'PSLDetector',
           'PvcamDetector',
           'RoperDetector',
           'SimDetector',
           'URLDetector',
           ]


class DetectorBase(ADBase):
    pass


class AreaDetector(DetectorBase):
    cam = C(cam.AreaDetectorCam, 'cam1:')


class SimDetector(DetectorBase):
    _html_docs = ['simDetectorDoc.html']
    cam = C(cam.SimDetectorCam, 'cam1:')


class AdscDetector(DetectorBase):
    _html_docs = ['adscDoc.html']
    cam = C(cam.AdscDetectorCam, 'cam1:')


class AndorDetector(DetectorBase):
    _html_docs = ['andorDoc.html']
    cam = C(cam.AndorDetectorCam, 'cam1:')


class Andor3Detector(DetectorBase):
    _html_docs = ['andor3Doc.html']
    cam = C(cam.Andor3DetectorCam, 'cam1:')


class BrukerDetector(DetectorBase):
    _html_docs = ['BrukerDoc.html']
    cam = C(cam.Andor3DetectorCam, 'cam1:')


class FirewireLinDetector(DetectorBase):
    _html_docs = ['FirewireWinDoc.html']
    cam = C(cam.FirewireLinDetectorCam, 'cam1:')


class FirewireWinDetector(DetectorBase):
    _html_docs = ['FirewireWinDoc.html']
    cam = C(cam.FirewireWinDetectorCam, 'cam1:')


class LightFieldDetector(DetectorBase):
    _html_docs = ['LightFieldDoc.html']
    cam = C(cam.LightFieldDetectorCam, 'cam1:')


class Mar345Detector(DetectorBase):
    _html_docs = ['Mar345Doc.html']
    cam = C(cam.Mar345DetectorCam, 'cam1:')


class MarCCDDetector(DetectorBase):
    _html_docs = ['MarCCDDoc.html']
    cam = C(cam.MarCCDDetectorCam, 'cam1:')


class PerkinElmerDetector(DetectorBase):
    _html_docs = ['PerkinElmerDoc.html']
    cam = C(cam.LightFieldDetectorCam, 'cam1:')


class PSLDetector(DetectorBase):
    _html_docs = ['PSLDoc.html']
    cam = C(cam.PSLDetectorCam, 'cam1:')


class PilatusDetector(DetectorBase):
    _html_docs = ['pilatusDoc.html']
    cam = C(cam.PilatusDetectorCam, 'cam1:')


class PixiradDetector(DetectorBase):
    _html_docs = ['PixiradDoc.html']
    cam = C(cam.PixiradDetectorCam, 'cam1:')


class PointGreyDetector(DetectorBase):
    _html_docs = ['PointGreyDoc.html']
    cam = C(cam.PointGreyDetectorCam, 'cam1:')


class ProsilicaDetector(DetectorBase):
    _html_docs = ['prosilicaDoc.html']
    cam = C(cam.ProsilicaDetectorCam, 'cam1:')


class PvcamDetector(DetectorBase):
    _html_docs = ['pvcamDoc.html']
    cam = C(cam.PvcamDetectorCam, 'cam1:')


class RoperDetector(DetectorBase):
    _html_docs = ['RoperDoc.html']
    cam = C(cam.RoperDetectorCam, 'cam1:')


class URLDetector(DetectorBase):
    _html_docs = ['URLDoc.html']
    cam = C(cam.URLDetectorCam, 'cam1:')
