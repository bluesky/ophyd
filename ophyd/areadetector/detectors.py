# vi: ts=4 sw=4
"""AreaDetector Devices

`areaDetector`_ detector abstractions

.. _areaDetector: https://areadetector.github.io/master/index.html
"""
import warnings

from . import cam
from .base import ADBase
from .base import ADComponent as C

__all__ = [
    "DetectorBase",
    "AreaDetector",
    "AdscDetector",
    "Andor3Detector",
    "AndorDetector",
    "BrukerDetector",
    "DexelaDetector",
    "EmergentVisionDetector",
    "EigerDetector",
    "FirewireLinDetector",
    "FirewireWinDetector",
    "GreatEyesDetector",
    "LightFieldDetector",
    "Mar345Detector",
    "MarCCDDetector",
    "PSLDetector",
    "PerkinElmerDetector",
    "PICamDetector",
    "PilatusDetector",
    "PixiradDetector",
    "PointGreyDetector",
    "ProsilicaDetector",
    "PvaDetector",
    "PvcamDetector",
    "RoperDetector",
    "SimDetector",
    "URLDetector",
    "UVCDetector",
    "Xspress3Detector",
]


class DetectorBase(ADBase):
    """
    The base class for the hardware-specific classes that follow.

    Note that Plugin also inherits from ADBase.
    This adds some AD-specific methods that are not shared by the plugins.
    """

    _default_configuration_attrs = ADBase._default_configuration_attrs + ("cam",)

    def generate_datum(self, key, timestamp, datum_kwargs=None):
        """
        Notify plugins of acquisition being complete.

        When a new acquisition is started, this method is called with a
        key which is a label like 'light', 'dark', or 'gain8'.

        It in turn calls ``generate_datum`` on all of the plugins that have
        that method.

        File plugins are identified by searching for a
        :meth:`~ophyd.areadetector.filestore_mixins.FileStoreBase.generate_datum`
        method that must have the signature ::

           def generate_datum(key: str, timestamp: float, datum_kwargs: dict):
              ...

        Parameters
        ----------
        key : str
            The label for the datum that should be generated

        timestamp : float
            The time of the trigger

        datum_kwargs : Dict[str, Any], optional
            Any datum kwargs that should go to all children.
        """
        if datum_kwargs is None:
            datum_kwargs = {}
        file_plugins = [
            s for s in self._signals.values() if hasattr(s, "generate_datum")
        ]
        for p in file_plugins:
            if p.enable.get():
                p.generate_datum(key, timestamp, datum_kwargs)

    def dispatch(self, key, timestamp):
        warnings.warn(
            ".dispatch is deprecated, use .generate_datum instead", stacklevel=2
        )

        return self.generate_datum(key, timestamp, {})

    dispatch.__doc__ = generate_datum.__doc__

    def make_data_key(self):
        source = "PV:{}".format(self.prefix)
        # This shape is expected to match arr.shape for the array.
        shape = (
            self.cam.num_images.get(),
            self.cam.array_size.array_size_y.get(),
            self.cam.array_size.array_size_x.get(),
        )
        return dict(shape=shape, source=source, dtype="array", external="FILESTORE:")

    def collect_asset_docs(self):
        file_plugins = [
            s for s in self._signals.values() if hasattr(s, "collect_asset_docs")
        ]
        for p in file_plugins:
            yield from p.collect_asset_docs()


class AreaDetector(DetectorBase):
    cam = C(cam.AreaDetectorCam, "cam1:")


class SimDetector(DetectorBase):
    _html_docs = ["simDetectorDoc.html"]
    cam = C(cam.SimDetectorCam, "cam1:")


class AdscDetector(DetectorBase):
    _html_docs = ["adscDoc.html"]
    cam = C(cam.AdscDetectorCam, "cam1:")


class AndorDetector(DetectorBase):
    _html_docs = ["andorDoc.html"]
    cam = C(cam.AndorDetectorCam, "cam1:")


class Andor3Detector(DetectorBase):
    _html_docs = ["andor3Doc.html"]
    cam = C(cam.Andor3DetectorCam, "cam1:")


class BrukerDetector(DetectorBase):
    _html_docs = ["BrukerDoc.html"]
    cam = C(cam.BrukerDetectorCam, "cam1:")


class DexelaDetector(DetectorBase):
    _html_docs = ["DexelaDoc.html"]
    cam = C(cam.DexelaDetectorCam, "cam1:")


class EmergentVisionDetector(DetectorBase):
    _html_docs = ["EVTDoc.html"]
    cam = C(cam.EmergentVisionDetectorCam, "cam1:")


class EigerDetector(DetectorBase):
    _html_docs = ["EigerDoc.html"]
    cam = C(cam.EigerDetectorCam, "cam1:")


class FirewireLinDetector(DetectorBase):
    _html_docs = ["FirewireWinDoc.html"]
    cam = C(cam.FirewireLinDetectorCam, "cam1:")


class FirewireWinDetector(DetectorBase):
    _html_docs = ["FirewireWinDoc.html"]
    cam = C(cam.FirewireWinDetectorCam, "cam1:")


class GreatEyesDetector(DetectorBase):
    _html_docs = []  # the documentation is not public
    cam = C(cam.GreatEyesDetectorCam, "cam1:")


class LightFieldDetector(DetectorBase):
    _html_docs = ["LightFieldDoc.html"]
    cam = C(cam.LightFieldDetectorCam, "cam1:")


class Mar345Detector(DetectorBase):
    _html_docs = ["Mar345Doc.html"]
    cam = C(cam.Mar345DetectorCam, "cam1:")


class MarCCDDetector(DetectorBase):
    _html_docs = ["MarCCDDoc.html"]
    cam = C(cam.MarCCDDetectorCam, "cam1:")


class PerkinElmerDetector(DetectorBase):
    _html_docs = ["PerkinElmerDoc.html"]
    cam = C(cam.PerkinElmerDetectorCam, "cam1:")


class PSLDetector(DetectorBase):
    _html_docs = ["PSLDoc.html"]
    cam = C(cam.PSLDetectorCam, "cam1:")


class PICamDetector(DetectorBase):
    _html_docs = ["PICamDoc.html"]
    cam = C(cam.PICamDetectorCam, "cam1:")


class PilatusDetector(DetectorBase):
    _html_docs = ["pilatusDoc.html"]
    cam = C(cam.PilatusDetectorCam, "cam1:")


class PixiradDetector(DetectorBase):
    _html_docs = ["PixiradDoc.html"]
    cam = C(cam.PixiradDetectorCam, "cam1:")


class PointGreyDetector(DetectorBase):
    _html_docs = ["PointGreyDoc.html"]
    cam = C(cam.PointGreyDetectorCam, "cam1:")


class ProsilicaDetector(DetectorBase):
    _html_docs = ["prosilicaDoc.html"]
    cam = C(cam.ProsilicaDetectorCam, "cam1:")


class PvaDetector(DetectorBase):
    _html_docs = ["pvaDoc.html"]
    cam = C(cam.PvaDetectorCam, "cam1:")


class PvcamDetector(DetectorBase):
    _html_docs = ["pvcamDoc.html"]
    cam = C(cam.PvcamDetectorCam, "cam1:")


class RoperDetector(DetectorBase):
    _html_docs = ["RoperDoc.html"]
    cam = C(cam.RoperDetectorCam, "cam1:")


class URLDetector(DetectorBase):
    _html_docs = ["URLDoc.html"]
    cam = C(cam.URLDetectorCam, "cam1:")


class UVCDetector(DetectorBase):
    _html_docs = ["UVCDoc.html"]
    cam = C(cam.UVCDetectorCam, "cam1:")


class Xspress3Detector(DetectorBase):
    _html_docs = ["Xspress3Doc.html"]
    cam = C(cam.Xspress3DetectorCam, "det1:")
