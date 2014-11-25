# vi: ts=4 sw=4
'''
:mod:`ophyd.control.areadetector` - areaDetector
================================================

.. module:: ophyd.control.areadetector
 :synopsis:  `areaDetector`_ camera and plugin abstractions

.. _areaDetector: http://cars.uchicago.edu/software/epics/areaDetector.html

'''

from __future__ import print_function
import logging
import inspect
import time
import copy

from .signal import (Signal, EpicsSignal, SignalGroup)
from ..utils import ad_docs

logger = logging.getLogger(__name__)


__all__ = ['AreaDetector',
           'SimDetector',
           'AndorDetector',
           'Andor3Detector',
           'BrukerDetector',
           'FirewireLinDetector',
           'FirewireWinDetector',
           'LightFieldDetector',
           'Mar345Detector',
           'MarCCDDetector',
           'PerkinElmerDetector',
           'PSLDetector',
           'PilatusDetector',
           'PixiradDetector',
           'PointGreyDetector',
           'ProsilicaDetector',
           'PvcamDetector',
           'RoperDetector',
           'URLDetector',
           ]


def ADSignalGroup(*props, **kwargs):
    def check_exists(self):
        signals = tuple(prop.__get__(self) for prop in props)
        key = tuple(signal.read_pvname for signal in signals)
        try:
            return self._ad_signals[key]
        except KeyError:
            sg = SignalGroup(**kwargs)
            for signal in signals:
                sg.add_signal(signal)

            self._ad_signals[key] = sg
            return self._ad_signals[key]

    def fget(self):
        return check_exists(self)

    def fset(self, value):
        sg = check_exists(self)
        sg.value = value

    doc = kwargs.pop('doc', '')
    return property(fget, fset, doc=doc)


def lookup_doc(cls_, pv):
    '''
    Go from top-level to base-level class, looking up html documentation
    until we get a hit.

    .. note:: This is only executed once, per class, per property (see
    ADSignal for more information)
    '''
    classes = inspect.getmro(cls_)
    docs = ad_docs.docs

    for class_ in classes:
        try:
            html_file = class_._html_docs
        except AttributeError:
            continue

        for fn in html_file:
            try:
                doc = docs[fn]
            except KeyError:
                continue

            try:
                return doc[pv]
            except KeyError:
                pass

            if pv.endswith('_RBV'):
                try:
                    return doc[pv[:-4]]
                except KeyError:
                    pass

    return 'No documentation found [PV suffix=%s]' % pv


class ADSignal(object):
    '''
    A property-like descriptor

    Don't create an EpicsSignal instance until it's
    accessed (i.e., lazy evaluation)
    '''

    def __init__(self, pv, has_rbv=False, doc=None, **kwargs):
        self.pv = pv
        self.has_rbv = has_rbv
        self.doc = doc
        self.kwargs = kwargs

        self.__doc__ = '[Lazy property for %s]' % pv

    def update_docstring(self, cls_):
        if self.doc is None:
            self.__doc__ = lookup_doc(cls_, self.pv)

    def check_exists(self, obj):
        if obj is None:
            # Happens when working on the class and not the object
            return self

        pv = self.pv
        try:
            return obj._ad_signals[pv]
        except KeyError:
            read_ = write = ''.join([obj._prefix, pv])
            if self.has_rbv:
                read_ += '_RBV'
            else:
                write = None

            signal = EpicsSignal(read_, write_pv=write,
                                 **self.kwargs)

            obj._ad_signals[pv] = signal
            if self.doc is not None:
                signal.__doc__ = self.doc
            else:
                signal.__doc__ = self.__doc__

            return obj._ad_signals[pv]

    def __get__(self, obj, objtype=None):
        return self.check_exists(obj)

    def __set__(self, obj, value):
        signal = self.check_exists(obj)
        signal.value = value


class ADBase(SignalGroup):
    _html_docs = ['areaDetectorDoc.html']

    @classmethod
    def _update_docstrings(cls_):
        '''
        ..note:: Updates docstrings
        '''

        attrs = [(attr, getattr(cls_, attr))
                 for attr in sorted(dir(cls_))]

        signals = [obj for attr, obj in attrs
                   if isinstance(obj, ADSignal)]

        for signal in signals:
            signal.update_docstring(cls_)

    @property
    def signals(self):
        '''
        A dictionary of all signals (or groups) in the object.

        .. note:: Instantiates all lazy signals
        '''
        if self.__sig_dict is None:
            attrs = [(attr, getattr(self, attr))
                     for attr in sorted(dir(self))
                     if not attr.startswith('_') and attr != 'signals']

            self.__sig_dict = dict((name, value) for name, value in attrs
                                   if isinstance(value, (Signal, SignalGroup)))

        return self.__sig_dict

    def __init__(self, prefix, **kwargs):
        SignalGroup.__init__(self, **kwargs)

        self._prefix = prefix
        self._ad_signals = {}
        self.__sig_dict = None

    def read(self):
        return self.report()

    def report(self):
        return copy.deepcopy(self.__sig_dict)


class NDArrayDriver(ADBase):
    _html_docs = ['areaDetectorDoc.html']

    array_counter = ADSignal('ArrayCounter', has_rbv=True)
    array_rate = ADSignal('ArrayRate_RBV', rw=False)
    asyn_io = ADSignal('AsynIO')

    nd_attributes_file = ADSignal('NDAttributesFile', string=True)
    pool_alloc_buffers = ADSignal('PoolAllocBuffers')
    pool_free_buffers = ADSignal('PoolFreeBuffers')
    pool_max_buffers = ADSignal('PoolMaxBuffers')
    pool_max_mem = ADSignal('PoolMaxMem')
    pool_used_buffers = ADSignal('PoolUsedBuffers')
    pool_used_mem = ADSignal('PoolUsedMem')
    port_name = ADSignal('PortName_RBV', rw=False, string=True)


class AreaDetector(NDArrayDriver):
    _html_docs = ['areaDetectorDoc.html']

    acquire = ADSignal('Acquire', has_rbv=True)
    acquire_period = ADSignal('AcquirePeriod', has_rbv=True)
    acquire_time = ADSignal('AcquireTime', has_rbv=True)

    array_callbacks = ADSignal('ArrayCallbacks', has_rbv=True)

    _array_size_x = ADSignal('ArraySizeX_RBV', rw=False)
    _array_size_y = ADSignal('ArraySizeY_RBV', rw=False)
    _array_size_z = ADSignal('ArraySizeZ_RBV', rw=False)
    array_size = ADSignalGroup(_array_size_x, _array_size_y, _array_size_z,
                               doc='Size of the array in the XYZ dimensions')

    array_size_bytes = ADSignal('ArraySize_RBV', rw=False)
    bin_x = ADSignal('BinX', has_rbv=True)
    bin_y = ADSignal('BinY', has_rbv=True)
    color_mode = ADSignal('ColorMode', has_rbv=True)
    data_type = ADSignal('DataType', has_rbv=True)
    detector_state = ADSignal('DetectorState_RBV', rw=False)
    frame_type = ADSignal('FrameType', has_rbv=True)
    gain = ADSignal('Gain', has_rbv=True)

    image_mode = ADSignal('ImageMode', has_rbv=True)
    manufacturer = ADSignal('Manufacturer_RBV', rw=False)

    _max_size_x = ADSignal('MaxSizeX_RBV', rw=False)
    _max_size_y = ADSignal('MaxSizeY_RBV', rw=False)
    max_size = ADSignalGroup(_max_size_x, _max_size_y,
                             doc='Maximum sensor size in the XY directions')

    min_x = ADSignal('MinX', has_rbv=True)
    min_y = ADSignal('MinY', has_rbv=True)
    model = ADSignal('Model_RBV', rw=False)

    num_exposures = ADSignal('NumExposures', has_rbv=True)
    num_exposures_counter = ADSignal('NumExposuresCounter_RBV', rw=False)
    num_images = ADSignal('NumImages', has_rbv=True)
    num_images_counter = ADSignal('NumImagesCounter_RBV', rw=False)

    read_status = ADSignal('ReadStatus')

    _reverse_x = ADSignal('ReverseX', has_rbv=True)
    _reverse_y = ADSignal('ReverseY', has_rbv=True)
    reverse = ADSignalGroup(_reverse_x, _reverse_y)

    shutter_close_delay = ADSignal('ShutterCloseDelay', has_rbv=True)
    shutter_close_epics = ADSignal('ShutterCloseEPICS')
    shutter_control = ADSignal('ShutterControl', has_rbv=True)
    shutter_control_epics = ADSignal('ShutterControlEPICS')
    shutter_fanout = ADSignal('ShutterFanout')
    shutter_mode = ADSignal('ShutterMode', has_rbv=True)
    shutter_open_delay = ADSignal('ShutterOpenDelay', has_rbv=True)
    shutter_open_epics = ADSignal('ShutterOpenEPICS')
    shutter_status_epics = ADSignal('ShutterStatusEPICS_RBV', rw=False)
    shutter_status = ADSignal('ShutterStatus_RBV', rw=False)

    _size_x = ADSignal('SizeX', has_rbv=True)
    _size_y = ADSignal('SizeY', has_rbv=True)
    size = ADSignalGroup(_size_x, _size_y)

    status_message = ADSignal('StatusMessage_RBV', rw=False, string=True)
    string_from_server = ADSignal('StringFromServer_RBV', rw=False, string=True)
    string_to_server = ADSignal('StringToServer_RBV', rw=False, string=True)
    temperature = ADSignal('Temperature', has_rbv=True)
    temperature_actual = ADSignal('TemperatureActual')
    time_remaining = ADSignal('TimeRemaining_RBV', rw=False)
    trigger_mode = ADSignal('TriggerMode', has_rbv=True)

    def __init__(self, prefix, cam='cam1:',
                 images=['image1:', ],
                 rois=['ROI1:', 'ROI2:', 'ROI3:', 'ROI4:'],
                 files=['TIFF1:', ],
                 procs=['Proc1:', ],
                 stats=['Stats1:', 'Stats2:', 'Stats3:', 'Stats4:', 'Stats5:', ],
                 ccs=['CC1:', 'CC2:', ],
                 trans=['Trans1:', ],
                 over=[['Over1:', 1, 8], ],
                 **kwargs):

        self._base_prefix = prefix

        if cam and not prefix.endswith(cam):
            prefix = ''.join([prefix, cam])

        ADBase.__init__(self, prefix=prefix, **kwargs)

        self.images = [plugins.ImagePlugin(self._base_prefix, suffix=im)
                       for im in images]
        self.files = [plugins.get_areadetector_plugin(self._base_prefix, suffix=fn)
                      for fn in files]
        self.procs = [plugins.ProcessPlugin(self._base_prefix, suffix=proc)
                      for proc in procs]
        self.stats = [plugins.StatsPlugin(self._base_prefix, suffix=stat)
                      for stat in stats]
        self.ccs = [plugins.ColorConvPlugin(self._base_prefix, suffix=cc)
                    for cc in ccs]
        self.trans = [plugins.TransformPlugin(self._base_prefix, suffix=tran)
                      for tran in trans]
        self.overlays = [plugins.OverlayPlugin(self._base_prefix, suffix=o[0],
                                               first_overlay=o[1], count=o[2])
                         for o in over]

    # TODO all reads should allow a timeout kw?
    # TODO handling multiple images even possible, or just assume single shot
    #      always?
    def read(self, timeout=None):
        start_mode = self.image_mode.value
        start_acquire = self.acquire.value

        self.acquire = 0

        time.sleep(0.01)

        if self.image_mode.value == 2:
            self.image_mode = 0  # single mode
            logger.debug('%s: Setting to single image mode' % self)

        time.sleep(0.01)

        try:
            self.acquire = 1
            time.sleep(0.01)
            logger.debug('%s: Waiting for completion' % self)
            while self.detector_state.value != 0 and self.acquire.value:
                time.sleep(0.01)

            images = [im.image for im in self.images]

            logger.debug('%s: Acquired %d image(s)' % (self, len(images)))
            if len(images) == 1:
                return images[0]
            else:
                return images
        finally:
            logger.debug('%s: Putting detector back into original state' % self)
            self.image_mode = start_mode
            self.acquire._set_request(start_acquire, wait=False)


class SimDetector(AreaDetector):
    _html_docs = ['simDetectorDoc.html']

    sim_mode = ADSignal('SimMode', has_rbv=True)

    gain_blue = ADSignal('GainBlue', has_rbv=True)
    gain_green = ADSignal('GainGreen', has_rbv=True)
    gain_red = ADSignal('GainRed', has_rbv=True)
    gain_rgb = ADSignalGroup(gain_red, gain_green, gain_blue)

    _gain_x = ADSignal('GainX', has_rbv=True)
    _gain_y = ADSignal('GainY', has_rbv=True)
    gain_xy = ADSignalGroup(_gain_x, _gain_y)

    noise = ADSignal('Noise', has_rbv=True)

    _peak_num_x = ADSignal('PeakNumX', has_rbv=True)
    _peak_num_y = ADSignal('PeakNumY', has_rbv=True)
    peak_num = ADSignalGroup(_peak_num_x, _peak_num_y,
                             doc='')

    _peak_start_x = ADSignal('PeakStartX', has_rbv=True)
    _peak_start_y = ADSignal('PeakStartY', has_rbv=True)
    peak_start = ADSignalGroup(_peak_start_x, _peak_start_y)

    _peak_step_x = ADSignal('PeakStepX', has_rbv=True)
    _peak_step_y = ADSignal('PeakStepY', has_rbv=True)
    peak_step = ADSignalGroup(_peak_step_x, _peak_step_y)

    peak_variation = ADSignal('PeakVariation', has_rbv=True)

    _peak_width_x = ADSignal('PeakWidthX', has_rbv=True)
    _peak_width_y = ADSignal('PeakWidthY', has_rbv=True)
    peak_width = ADSignalGroup(_peak_width_x, _peak_width_y)

    reset = ADSignal('Reset', has_rbv=True)


class AndorDetector(AreaDetector):
    _html_docs = ['andorDoc.html']


class Andor3Detector(AreaDetector):
    _html_docs = ['andor3Doc.html']


class BrukerDetector(AreaDetector):
    _html_docs = ['BrukerDoc.html']


class FirewireLinDetector(AreaDetector):
    _html_docs = ['FirewireWinDoc.html']


class FirewireWinDetector(AreaDetector):
    _html_docs = ['FirewireWinDoc.html']


class LightFieldDetector(AreaDetector):
    _html_docs = ['LightFieldDoc.html']


class Mar345Detector(AreaDetector):
    _html_docs = ['Mar345Doc.html']


class MarCCDDetector(AreaDetector):
    _html_docs = ['MarCCDDoc.html']


class PerkinElmerDetector(AreaDetector):
    _html_docs = ['PerkinElmerDoc.html']


class PSLDetector(AreaDetector):
    _html_docs = ['PSLDoc.html']


class PilatusDetector(AreaDetector):
    _html_docs = ['pilatusDoc.html']


class PixiradDetector(AreaDetector):
    _html_docs = ['PixiradDoc.html']


class PointGreyDetector(AreaDetector):
    _html_docs = ['PointGreyDoc.html']


class ProsilicaDetector(AreaDetector):
    _html_docs = ['prosilicaDoc.html']


class PvcamDetector(AreaDetector):
    _html_docs = ['pvcamDoc.html']


class RoperDetector(AreaDetector):
    _html_docs = ['RoperDoc.html']


class URLDetector(AreaDetector):
    _html_docs = ['URLDoc.html']

from . import ad_plugins as plugins

def update_docstrings():
    '''
    Dynamically set docstrings for all ADSignals, based on
    parsed areadetector documentation

    .. note:: called automatically when the module is loaded
    '''
    def all_items():
        for item in globals().items():
            yield item

        for item in plugins.__dict__.items():
            yield item

    for var, cls_ in all_items():
        if inspect.isclass(cls_):
            if hasattr(cls_, '_update_docstrings'):
                cls_._update_docstrings()


update_docstrings()
