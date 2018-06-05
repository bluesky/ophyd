.. currentmodule:: ophyd.areadetector

================
 Area Detectors
================

Area Detector devices require some customization to use. Here is the simplest
possible configuration.

.. code-block:: python

    from ophyd import AreaDetector, SingleTrigger

    class MyDetector(SingleTrigger, AreaDetector):
        pass

    prefix = 'XF:23ID1-ES{Tst-Cam:1}'
    det = MyDetector(prefix)

The above should work correctly with any EPICS `Area Detector <http://cars.uchicago.edu/software/epics/areaDetector.html>`_. We test on
versions 1.9.1 and 2.2.

.. warning

   When making new detector classes the ``Trigger`` class must come first in the inheretance
   or the default ``Device`` trigger method will be used instead of the trigger method from
   the trigger mix in.

Ports
=====

.. autosummary::
   :toctree: generated

   ~base.ADBase
   ~base.ADBase.get_plugin_by_asyn_port
   ~base.ADBase.get_asyn_port_dictionary
   ~base.ADBase.get_asyn_digraph
   ~base.ADBase.validate_asyn_ports
   ~base.ADBase.missing_plugins


Filestore Plugins
=================

.. note::

   The mixins in this section are to be mixed with the file plugin classes
   and used as components on a larger device.  The siblings of the resulting classes
   are components representing the various plugins that make up an Area Detector.

Integration of the file writing with filestore is done by mixing
sub-classes of :class:`FileStorePluginBase` into one of the file
plugin classes and using the resulting class as a component in your
detector.


The base classes (which may be merged in the future)

.. autosummary::
   :toctree: generated

   ~filestore_mixins.FileStoreBase
   ~filestore_mixins.FileStorePluginBase


provide the basic methods required for integrating AreaDetector file plugins with
:mod:`filestore`

.. autosummary::
   :toctree: generated

   ~filestore_mixins.FileStoreBase.generate_datum

   ~filestore_mixins.FileStoreBase.write_path_template
   ~filestore_mixins.FileStoreBase.reg_root
   ~filestore_mixins.FileStoreBase.fs_root
   ~filestore_mixins.FileStoreBase.read_path_template

   ~filestore_mixins.FileStorePluginBase.make_filename

`~filestore_mixins.FileStorePluginBase` must be sub-classed to match
each file plugin and take care of inserting the correct meta-data into
`FileStore` and configuring the file plugin.

.. autosummary::
   :toctree: generated

   ~filestore_mixins.FileStoreTIFF
   ~filestore_mixins.FileStoreHDF5
   ~filestore_mixins.FileStoreTIFFSquashing


The :class:`~filestore_mixins.FileStoreTIFFSquashing` also makes use of the
processing plugin to 'squash' multiple frames together into a single
saved image.

To create a functioning class you must also mixin

.. autosummary::
   :toctree: generated

   ~filestore_mixins.FileStoreIterativeWrite

which extends :meth:`~filestore_mixins.FileStoreBase.generate_datum` to
insert into the ``FileStore`` instance as data is taken.

For convenience we provide


.. autosummary::
   :toctree: generated

   ~filestore_mixins.FileStoreHDF5IterativeWrite
   ~filestore_mixins.FileStoreTIFFIterativeWrite


.. inheritance-diagram:: ophyd.areadetector.filestore_mixins.FileStoreBase ophyd.areadetector.filestore_mixins.FileStoreHDF5 ophyd.areadetector.filestore_mixins.FileStoreHDF5IterativeWrite ophyd.areadetector.filestore_mixins.FileStoreIterativeWrite ophyd.areadetector.filestore_mixins.FileStorePluginBase ophyd.areadetector.filestore_mixins.FileStoreTIFF ophyd.areadetector.filestore_mixins.FileStoreTIFFIterativeWrite ophyd.areadetector.filestore_mixins.FileStoreTIFFSquashing ophyd.device.GenerateDatumInterface ophyd.device.BlueskyInterface
    :parts: 1


Area Detector Trigger dispatching
=================================
.. note::

   The mixins in this section are to be mixed with :class:`~ophyd.device.Device` to
   represent the 'top level' area detector.  The components of the resulting class are
   the various plugins that make up a full Area Detector.


.. autosummary::
   :toctree: generated

   ~detectors.DetectorBase
   ~detectors.DetectorBase.dispatch
   ~detectors.DetectorBase.make_data_key

The translation between the :meth:`~ophyd.device.BlueskyInterface.trigger` and triggering
the underlying camera is mediated by the trigger mix-ins.

.. autosummary::
   :toctree: generated

   ~trigger_mixins.TriggerBase
   ~trigger_mixins.SingleTrigger
   ~trigger_mixins.MultiTrigger

.. inheritance-diagram:: ophyd.areadetector.trigger_mixins.TriggerBase ophyd.areadetector.trigger_mixins.SingleTrigger ophyd.areadetector.trigger_mixins.MultiTrigger
    :parts: 1

Plugins
=======


.. autosummary::
   :toctree: generated

   ~plugins.PluginBase
   ~plugins.ColorConvPlugin
   ~plugins.ImagePlugin
   ~plugins.OverlayPlugin
   ~plugins.ProcessPlugin
   ~plugins.ROIPlugin
   ~plugins.StatsPlugin
   ~plugins.TransformPlugin

.. inheritance-diagram:: ophyd.areadetector.plugins.PluginBase ophyd.areadetector.plugins.ColorConvPlugin ophyd.areadetector.plugins.ImagePlugin ophyd.areadetector.plugins.OverlayPlugin ophyd.areadetector.plugins.ProcessPlugin ophyd.areadetector.plugins.ROIPlugin ophyd.areadetector.plugins.StatsPlugin ophyd.areadetector.plugins.TransformPlugin
   :parts: 1

File Plugins
============
.. autosummary::
   :toctree: generated

   ~plugins.FilePlugin
   ~plugins.HDF5Plugin
   ~plugins.JPEGPlugin
   ~plugins.MagickPlugin
   ~plugins.NetCDFPlugin
   ~plugins.NexusPlugin
   ~plugins.TIFFPlugin


.. inheritance-diagram:: ophyd.areadetector.plugins.FilePlugin ophyd.areadetector.plugins.HDF5Plugin ophyd.areadetector.plugins.JPEGPlugin ophyd.areadetector.plugins.MagickPlugin ophyd.areadetector.plugins.NetCDFPlugin ophyd.areadetector.plugins.NexusPlugin ophyd.areadetector.plugins.TIFFPlugin
   :parts: 1


Specific Hardware
=================

While the above example should work with any Area Detector, ophyd provides
specialized classes for specific detectors supported by EPICS Area Detector.
These specialized classes generally add components representing fields
particular to a given detector, along with device-specific documentation
for components.

To use these model-specific classes, swap out ``AreaDetector`` like so:

.. code-block:: python

    # before
    class MyDetector(SingleTrigger, AreaDetector):
        pass

    # after
    class MyDetector(SingleTrigger, AndorDetector):
        pass

.. autosummary::
   :toctree: generated

   ~detectors.AreaDetector
   ~detectors.AdscDetector
   ~detectors.Andor3Detector
   ~detectors.AndorDetector
   ~detectors.BrukerDetector
   ~detectors.FirewireLinDetector
   ~detectors.FirewireWinDetector
   ~detectors.LightFieldDetector
   ~detectors.Mar345Detector
   ~detectors.MarCCDDetector
   ~detectors.PSLDetector
   ~detectors.PerkinElmerDetector
   ~detectors.PilatusDetector
   ~detectors.PixiradDetector
   ~detectors.PointGreyDetector
   ~detectors.ProsilicaDetector
   ~detectors.PvcamDetector
   ~detectors.RoperDetector
   ~detectors.SimDetector
   ~detectors.URLDetector

.. inheritance-diagram:: ophyd.areadetector.detectors.AreaDetector ophyd.areadetector.detectors.AdscDetector ophyd.areadetector.detectors.Andor3Detector ophyd.areadetector.detectors.AndorDetector ophyd.areadetector.detectors.BrukerDetector ophyd.areadetector.detectors.FirewireLinDetector ophyd.areadetector.detectors.FirewireWinDetector ophyd.areadetector.detectors.LightFieldDetector ophyd.areadetector.detectors.Mar345Detector ophyd.areadetector.detectors.MarCCDDetector ophyd.areadetector.detectors.PSLDetector ophyd.areadetector.detectors.PerkinElmerDetector ophyd.areadetector.detectors.PilatusDetector ophyd.areadetector.detectors.PixiradDetector ophyd.areadetector.detectors.PointGreyDetector ophyd.areadetector.detectors.ProsilicaDetector ophyd.areadetector.detectors.PvcamDetector ophyd.areadetector.detectors.RoperDetector ophyd.areadetector.detectors.SimDetector ophyd.areadetector.detectors.URLDetector
   :parts: 1


Cams
----

The vendor specific details are embedded in the cams

.. autosummary::
   :toctree: generated

   ~cam.CamBase
   ~cam.AdscDetectorCam
   ~cam.Andor3DetectorCam
   ~cam.AndorDetectorCam
   ~cam.BrukerDetectorCam
   ~cam.FirewireLinDetectorCam
   ~cam.FirewireWinDetectorCam
   ~cam.LightFieldDetectorCam
   ~cam.Mar345DetectorCam
   ~cam.MarCCDDetectorCam
   ~cam.PSLDetectorCam
   ~cam.PcoDetectorCam
   ~cam.PcoDetectorIO
   ~cam.PcoDetectorSimIO
   ~cam.PerkinElmerDetectorCam
   ~cam.PilatusDetectorCam
   ~cam.PixiradDetectorCam
   ~cam.PointGreyDetectorCam
   ~cam.ProsilicaDetectorCam
   ~cam.PvcamDetectorCam
   ~cam.RoperDetectorCam
   ~cam.SimDetectorCam
   ~cam.URLDetectorCam

.. inheritance-diagram:: ophyd.areadetector.cam.CamBase ophyd.areadetector.cam.AdscDetectorCam ophyd.areadetector.cam.Andor3DetectorCam ophyd.areadetector.cam.AndorDetectorCam ophyd.areadetector.cam.BrukerDetectorCam ophyd.areadetector.cam.FirewireLinDetectorCam ophyd.areadetector.cam.FirewireWinDetectorCam ophyd.areadetector.cam.LightFieldDetectorCam ophyd.areadetector.cam.Mar345DetectorCam ophyd.areadetector.cam.MarCCDDetectorCam ophyd.areadetector.cam.PSLDetectorCam ophyd.areadetector.cam.PcoDetectorCam ophyd.areadetector.cam.PcoDetectorIO ophyd.areadetector.cam.PcoDetectorSimIO ophyd.areadetector.cam.PerkinElmerDetectorCam ophyd.areadetector.cam.PilatusDetectorCam ophyd.areadetector.cam.PixiradDetectorCam ophyd.areadetector.cam.PointGreyDetectorCam ophyd.areadetector.cam.ProsilicaDetectorCam ophyd.areadetector.cam.PvcamDetectorCam ophyd.areadetector.cam.RoperDetectorCam ophyd.areadetector.cam.SimDetectorCam ophyd.areadetector.cam.URLDetectorCam
   :parts: 1

Helpers
=======

.. autosummary::
   :toctree: generated

   ~base.EpicsSignalWithRBV
   ~base.ADComponent
   ~base.ad_group


Full Inheritance
================

.. inheritance-diagram:: ophyd.areadetector.plugins.FilePlugin ophyd.areadetector.plugins.HDF5Plugin ophyd.areadetector.plugins.JPEGPlugin ophyd.areadetector.plugins.MagickPlugin ophyd.areadetector.plugins.NetCDFPlugin ophyd.areadetector.plugins.NexusPlugin ophyd.areadetector.plugins.TIFFPlugin ophyd.areadetector.plugins.PluginBase ophyd.areadetector.plugins.ColorConvPlugin ophyd.areadetector.plugins.ImagePlugin ophyd.areadetector.plugins.OverlayPlugin ophyd.areadetector.plugins.ProcessPlugin ophyd.areadetector.plugins.ROIPlugin ophyd.areadetector.plugins.StatsPlugin ophyd.areadetector.plugins.TransformPlugin ophyd.areadetector.filestore_mixins.FileStoreBase ophyd.areadetector.filestore_mixins.FileStoreHDF5 ophyd.areadetector.filestore_mixins.FileStoreHDF5IterativeWrite ophyd.areadetector.filestore_mixins.FileStoreIterativeWrite ophyd.areadetector.filestore_mixins.FileStorePluginBase ophyd.areadetector.filestore_mixins.FileStoreTIFF ophyd.areadetector.filestore_mixins.FileStoreTIFFIterativeWrite ophyd.areadetector.filestore_mixins.FileStoreTIFFSquashing ophyd.device.GenerateDatumInterface ophyd.device.BlueskyInterface ophyd.areadetector.trigger_mixins.TriggerBase ophyd.areadetector.trigger_mixins.SingleTrigger ophyd.areadetector.trigger_mixins.MultiTrigger ophyd.areadetector.cam.CamBase ophyd.areadetector.cam.AdscDetectorCam ophyd.areadetector.cam.Andor3DetectorCam ophyd.areadetector.cam.AndorDetectorCam ophyd.areadetector.cam.BrukerDetectorCam ophyd.areadetector.cam.FirewireLinDetectorCam ophyd.areadetector.cam.FirewireWinDetectorCam ophyd.areadetector.cam.LightFieldDetectorCam ophyd.areadetector.cam.Mar345DetectorCam ophyd.areadetector.cam.MarCCDDetectorCam ophyd.areadetector.cam.PSLDetectorCam ophyd.areadetector.cam.PcoDetectorCam ophyd.areadetector.cam.PcoDetectorIO ophyd.areadetector.cam.PcoDetectorSimIO ophyd.areadetector.cam.PerkinElmerDetectorCam ophyd.areadetector.cam.PilatusDetectorCam ophyd.areadetector.cam.PixiradDetectorCam ophyd.areadetector.cam.PointGreyDetectorCam ophyd.areadetector.cam.ProsilicaDetectorCam ophyd.areadetector.cam.PvcamDetectorCam ophyd.areadetector.cam.RoperDetectorCam ophyd.areadetector.cam.SimDetectorCam ophyd.areadetector.cam.URLDetectorCam ophyd.areadetector.detectors.AreaDetector ophyd.areadetector.detectors.AdscDetector ophyd.areadetector.detectors.Andor3Detector ophyd.areadetector.detectors.AndorDetector ophyd.areadetector.detectors.BrukerDetector ophyd.areadetector.detectors.FirewireLinDetector ophyd.areadetector.detectors.FirewireWinDetector ophyd.areadetector.detectors.LightFieldDetector ophyd.areadetector.detectors.Mar345Detector ophyd.areadetector.detectors.MarCCDDetector ophyd.areadetector.detectors.PSLDetector ophyd.areadetector.detectors.PerkinElmerDetector ophyd.areadetector.detectors.PilatusDetector ophyd.areadetector.detectors.PixiradDetector ophyd.areadetector.detectors.PointGreyDetector ophyd.areadetector.detectors.ProsilicaDetector ophyd.areadetector.detectors.PvcamDetector ophyd.areadetector.detectors.RoperDetector ophyd.areadetector.detectors.SimDetector ophyd.areadetector.detectors.URLDetector ophyd.areadetector.base.ADComponent ophyd.areadetector.base.EpicsSignalWithRBV
   :parts: 1
