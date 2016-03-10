Area Detectors
**************

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

Specific Hardware
-----------------

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


ADSC
^^^^

.. autoclass:: ophyd.areadetector.AdscDetector
.. autoclass:: ophyd.areadetector.AdscDetectorCam
    :members:

Andor3
^^^^^^

.. autoclass:: ophyd.areadetector.Andor3Detector
.. autoclass:: ophyd.areadetector.Andor3DetectorCam
    :members:

Andor
^^^^^

.. autoclass:: ophyd.areadetector.AndorDetector
.. autoclass:: ophyd.areadetector.AndorDetectorCam
    :members:


Bruker
^^^^^^

.. autoclass:: ophyd.areadetector.BrukerDetector
.. autoclass:: ophyd.areadetector.BrukerDetectorCam
    :members:

Firewire on Linux
^^^^^^^^^^^^^^^^^

.. autoclass:: ophyd.areadetector.FirewireLinDetector
.. autoclass:: ophyd.areadetector.FirewireLinDetectorCam
    :members:


Firewire on Windows
^^^^^^^^^^^^^^^^^^^

.. autoclass:: ophyd.areadetector.FirewireWinDetector
.. autoclass:: ophyd.areadetector.FirewireWinDetectorCam
    :members:

Lightfield
^^^^^^^^^^

.. autoclass:: ophyd.areadetector.LightFieldDetector
.. autoclass:: ophyd.areadetector.LightFieldDetectorCam
    :members:

Mar345
^^^^^^

.. autoclass:: ophyd.areadetector.Mar345Detector
.. autoclass:: ophyd.areadetector.Mar345DetectorCam
    :members:

Mar CCD
^^^^^^^

.. autoclass:: ophyd.areadetector.MarCCDDetector
.. autoclass:: ophyd.areadetector.MarCCDDetectorCam
    :members:

PSL
^^^

.. autoclass:: ophyd.areadetector.PSLDetector
.. autoclass:: ophyd.areadetector.PSLDetectorCam
    :members:

Perkin-Elmer
^^^^^^^^^^^^

.. autoclass:: ophyd.areadetector.PerkinElmerDetector
.. autoclass:: ophyd.areadetector.PerkinElmerDetectorCam
    :members:


Pilatus
^^^^^^^

.. autoclass:: ophyd.areadetector.PilatusDetector
.. autoclass:: ophyd.areadetector.PilatusDetectorCam
    :members:

Pixirad
^^^^^^^

.. autoclass:: ophyd.areadetector.PixiradDetector
.. autoclass:: ophyd.areadetector.PixiradDetectorCam
    :members:

Point Grey
^^^^^^^^^^

.. autoclass:: ophyd.areadetector.PointGreyDetector
.. autoclass:: ophyd.areadetector.PointGreyDetectorCam
    :members:

Prosilica
^^^^^^^^^

.. autoclass:: ophyd.areadetector.ProsilicaDetector
.. autoclass:: ophyd.areadetector.ProsilicaDetectorCam
    :members:

PV Cam
^^^^^^

.. autoclass:: ophyd.areadetector.PvcamDetector
.. autoclass:: ophyd.areadetector.PvcamDetectorCam
    :members:

Roper
^^^^^

.. autoclass:: ophyd.areadetector.RoperDetector
.. autoclass:: ophyd.areadetector.RoperDetectorCam
    :members:

Simulated
^^^^^^^^^

.. autoclass:: ophyd.areadetector.SimDetector
.. autoclass:: ophyd.areadetector.SimDetectorCam
    :members:


URL
^^^

.. autoclass:: ophyd.areadetector.URLDetector
.. autoclass:: ophyd.areadetector.URLDetectorCam
    :members:


Plugins
-------


.. autoclass:: ophyd.areadetector.plugins.PluginBase
    :members:

Color Converter Plugin
^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: ophyd.areadetector.plugins.ColorConvPlugin
    :members:

Image Plugin
^^^^^^^^^^^^

.. autoclass:: ophyd.areadetector.plugins.ImagePlugin
    :members:

Overlay Plugin
^^^^^^^^^^^^^^

.. autoclass:: ophyd.areadetector.plugins.OverlayPlugin
    :members:

Process Plugin
^^^^^^^^^^^^^^

.. autoclass:: ophyd.areadetector.plugins.ProcessPlugin
    :members:

ROI Plugin
^^^^^^^^^^

.. autoclass:: ophyd.areadetector.plugins.ROIPlugin
    :members:

Stats Plugin
^^^^^^^^^^^^

.. autoclass:: ophyd.areadetector.plugins.StatsPlugin
    :members:

Transform Plugin
^^^^^^^^^^^^^^^^

.. autoclass:: ophyd.areadetector.plugins.TransformPlugin
    :members:


File Plugins
------------

.. autoclass:: ophyd.areadetector.plugins.FilePlugin
    :members:


HDF5 Plugin
^^^^^^^^^^^
.. autoclass:: ophyd.areadetector.plugins.HDF5Plugin
    :members:

JPEG Plugin
^^^^^^^^^^^

.. autoclass:: ophyd.areadetector.plugins.JPEGPlugin
    :members:

ImageMagick Plugin
^^^^^^^^^^^^^^^^^^

.. autoclass:: ophyd.areadetector.plugins.MagickPlugin
    :members:

NetCDF Plugin
^^^^^^^^^^^^^

.. autoclass:: ophyd.areadetector.plugins.NetCDFPlugin
    :members:

Nexus Plugin
^^^^^^^^^^^^

.. autoclass:: ophyd.areadetector.plugins.NexusPlugin
    :members:

TIFF Plugin
^^^^^^^^^^^

.. autoclass:: ophyd.areadetector.plugins.TIFFPlugin
    :members:
