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
particular to a given detector.

To use these model-specific classes, swap out ``AreaDetector`` like so:

.. code-block:: python

    # before
    class MyDetector(SingleTrigger, AreaDetector):
        pass

    # after
    class MyDetector(SingleTrigger, AndorDetector):
        pass

Below is a list of all model-specific classes supported by ophyd.


* AdscDetector
* Andor3Detector
* AndorDetector
* BrukerDetector
* FirewireLinDetector
* FirewireWinDetector
* LightFieldDetector
* Mar345Detector
* MarCCDDetector
* PSLDetector
* PerkinElmerDetector
* PilatusDetector
* PixiradDetector
* PointGreyDetector
* ProsilicaDetector
* PvcamDetector
* RoperDetector
* SimDetector
* URLDetector
