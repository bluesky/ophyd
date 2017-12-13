# vi: ts=4 sw=4
'''AreaDetector Devices

`areaDetector`_ detector abstractions

.. _areaDetector: http://cars.uchicago.edu/software/epics/areaDetector.html
'''
import networkx as nx
from collections import OrderedDict

from .base import (ADBase, ADComponent as C, EnableRule)
from ..utils import set_and_wait
from . import cam


__all__ = ['DetectorBase',
           'AreaDetector',
           'AdscDetector',
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
    """
    The base class for the hardware-specific classes that follow.

    Note that Plugin also inherits from ADBase.
    This adds some AD-specific methods that are not shared by the plugins.
    """
    _default_configuration_attrs = (ADBase._default_configuration_attrs +
                                    ('cam', ))

    def dispatch(self, key, timestamp):
        """Notify plugins of acquisition being complete.

        When a new acquisition is finished, this method is called with a
        key which is a label like 'light', 'dark', or 'gain8'.

        It in turn calls all of the file plugins and makes them insert a
        datum into FileStore.

        File plugins are identified by searching for a
        :meth:`~ophyd.areadetector.filestore_mixins.FileStoreBase.generate_datum`
        method that must have the siganture ::

           def generate_datum(key: str, timestamp: float):
              ...

        """
        file_plugins = [s for s in self._signals.values() if
                        hasattr(s, 'generate_datum')]
        for p in file_plugins:
            if p.enable.get():
                p.generate_datum(key, timestamp, {})

    def make_data_key(self):
        source = 'PV:{}'.format(self.prefix)
        shape = tuple(self.cam.array_size.get())
        return dict(shape=shape, source=source, dtype='array',
                    external='FILESTORE:')

    def stage(self, *args, **kwargs):
        from threading import Event
        # get ready to drain the queues
        g, port_map = self.get_asyn_digraph(enable_rule=EnableRule.ENABLE)

        # walk the tree from top to bottom
        plugins = OrderedDict()
        for name in nx.topological_sort(g):
            plugins[name] = port_map[name]

        # disable all of the and cache current enable state
        previous_enable_values = {}
        for cpt in plugins.values():
            if hasattr(cpt, 'enable'):
                previous_enable_values[cpt.enable] = cpt.enable.get()
                set_and_wait(cpt.enable, 0)

        # find anything that is not at 0 queue usage and install callbacks
        need_draining = {cpt
                         for cpt in plugins.values()
                         if (hasattr(cpt, 'queue_use') and
                             cpt.queue_use.get() > 0)}
        drain_events = {}

        for cpt in need_draining:
            ev = Event()
            drain_events
            cid = cpt.queue_use.subscribe(
                lambda value, _evt=ev, **kwargs:
                ev.set()
                if value == 0 else None)

            drain_events[ev] = (cid, cpt)

        # wait for all queues to drain to 0
        for ev, (cid, cpt) in drain_events.items():
            ev.wait()
            cpt.unsubscribe(cid)

        # check that all quesue really are at 0
        for cpt in plugins.values():
            if hasattr(cpt, 'queue_use') and cpt.queue_use.get() > 0:
                raise RuntimeError("Queue still draining, should be empty")

        # do the base stage which may re-wire the plugins and will recurse
        # down through any children
        ret = super().stage(*args, **kwargs)
        # due to the above code, the base stage thinks everything is disabled,
        # update with the values we grabbed above.
        self._original_vals.update(previous_enable_values)
        # grab the port map again
        g, port_map = self.get_asyn_digraph(enable_rule=EnableRule.ENABLE)
        try:
            # TODO check that everything in self.read is enabled
            pass
        except RuntimeError:
            self.unstage()
            raise

        try:
            self._validate_asyn_ports(g, port_map)
        except RuntimeError as err:
            self.unstage()
            raise err

        # re-enable the enabled callbacks starting from bottom

        return ret


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
