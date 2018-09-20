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

The above should work correctly with any EPICS `Area Detector
<http://cars.uchicago.edu/software/epics/areaDetector.html#Overview>`_. We test
on versions 1.9.1 and 2.2.  For preliminary support for AD33 see the
``nslsii`` package.

.. warning

   When making new detector classes the ``Trigger`` class must come first in the inheretance
   or the default ``Device`` trigger method will be used instead of the trigger method from
   the trigger mix in.


Callbacks
=========

Internally, Area Detector provides a `flexible array processing
pipeline <http://cars9.uchicago.edu/software/epics/pluginDoc.html>`_.
The pipeline is a chain of 'plugins' which can be re-configured at
runtime by setting the ``.nd_array_port`` on a downstream plugin to
the ``.port_name`` of the upstream plugin.  Internally the plugins
pass data between each other by passing a pointer to an ``NDArray`` C++
object (which is an array plus some meta-data).  The arrays are
allocated out of a shared pool when they are created (typically by the
'cam' plugin which wraps the detector driver) and freed when the last
plugin is done with them.  Each plugin can trigger its children in
two ways:

- *blocking* : The next plugin is called syncronously, blocking the
  parent plugin until all of the (blocking) children are finished.
  This is single-threaded.
- *non-blocking* : The pointer is put on a queue that the child
  consumes from.  This allows multi-threaded processing with each
  plugin running on its own thread.

This behavior is controlled by the ``.blocking_callbacks`` signal on
the plugin.

The :obj:`~ophyd.areadetector.trigger_mixins.SingleTrigger` sets the
acquire bit 'high' and then watches for it to go low (indicating that
acquisition is complete).  If any of the down-stream plugins are in
non-blocking mode are likely to have the following sequence of events
when using, for example, the ``Stats`` plugin and taking one frame

1. detector produces the frame
2. puts the frame on the queue for the stats plugin to consume
3. flips the acquire bit to 'low'
4. ophyd sees the acquire bit go low and marks the status object as done
5. bluesky continues with the plan and reads the Stats plugin (which still contains old data)
6. the Stats plugin processes the frame (updating the values for the just-collected frame)

Because (6) happens after (5) bluesky reads 'stale' data from the
stats plugin and produces an event which associates other measurements
with the incorrect reading from the camera.  This issue has resulted
in alignment scans systematically returning the values from the
previous point.  To avoid this, we ensure in ``stage()`` that all
plugins are in 'blocking' mode.  This has the downside of slowing the
detector down as we are only using a single thread but has the
advantage of giving correct measurements.

Prior to AD3-3, AD did not track if a given frame had fully propagated
through the pipeline.  We looked into tracking this from the outside
and using this to determine when the data acquisition was done.  In
principle this could be done by watching a combination of queue size
and the ``.uniqueID`` signal, however this work was abandoned due to
the complexity of supporting this for all of the version of AD on the
floor.

In `AD3-3
<https://github.com/areaDetector/ADCore/blob/master/RELEASE.md#queued-array-counting-and-waiting-for-plugins-to-complete>`_,
the camera now tracks if all of the frames it produces have been
processed (added to support ophyd [#]_ ).  There is now a
``.wait_for_plugins`` signal that controls the behavior of
put-complete on the ``.acquire`` signal.  If ``.wait_for_plugins`` is
``True``, then the put-complete callback on the ``.acquire`` signal
will not process until all of the frames have been processed by all of
the plugins.

This allows us to run with all of the plugins in non-blocking mode and
to simplify the trigger logic.  Instead of waiting for the acquire bit to
change value, we use the a put-completion callback.

To convert an existing area detector sub-class to support the new scheme you
must:

1. Change the type of the came to sub-class :obj:`nslsii.ad33.CamV33Mixin`
2. Change the trigger mixin to be :obj:`nslsii.ad33.SingleTriggerV33`
3. Arrange for ``det.cam.ensure_nonblocking`` to be called after
   initializing the ophyd object.



Ports
=====

Each plugin has a read-only out-put port name (``.port_name``) and a
settable in-put port name (``.nd_array_port``).  To connect plugin
``downstream`` to plugin ``upstream`` set ``downstream.nd_array_port``
to ``upstream.port_name``.

The top-level `~base.ADBase` class has several helper methods for
walking and validating the plugin network.

.. autosummary::
   :toctree: generated

   ~base.ADBase
   ~base.ADBase.visualize_asyn_digraph
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

Custom Devices
==============
For custom hardware based on area-detector it may be necesary to add a custom
device class (for custom plugins see section below). The new class should
inherit from :class:`ophyd.areadetector.base.ADbase` and should have the following
PV structure:

.. code-block:: python

    PV = 'Areadetector_device_PV_prefix:(Plugin_suffix or attribute_suffix)'

As an example, for the builtin areadetector 'stats' class this looks like:

.. code-block:: python

    PV = 'Areadetector_device_PV_prefix:Stats'

And for the builtin areadetector 'color mode' attribute it looks like:

.. code-block:: python

    PV = 'Areadetector_device_PV_prefix:cam1:ColorMode_RBV'

where ``'Areadetector_device_PV_prefix'`` is the base PV name for the
Area detector device, ``plugin_suffix = 'Stats'`` is the 'stats' Plugin
suffix and ``attribute_suffix = 'ColorMode_RBV'`` is the 'color mode'
attribute suffix of the ``'cam1'`` plugin.

In order to create the class then the following code is required
(where ``XXX`` is the name of the device):

.. code-block:: python

    from ophyd.areadetector.base import ad_group, EpicsSignalWithRBV
    from ophyd.signal import EpicsSignal, EpicsSignalRO
    from ophyd.device import DynamicDeviceComponent as DDCpt, Component as Cpt
    from ophyd.detectors import DetectorBase
    from ophyd.areadetector.trigger_mixins import SingleTrigger

    class XXX(SingleTrigger, DetectorBase):
        '''An areadetector device class for ...'''

        # ADD ATTRIBUTES AS COMPONENTS HERE USING THE SYNTAX
        # where 'Type' is EpicsSignal, EpicsSignalRO, EpicsSignalWithRBV,..
        attribute_name = Cpt(Type, attribute_suffix)

        # ADD ATTRIBUTE GROUPS AS COMPONENTS USING THE SYNTAX
        group_name = DDCpt(ad_group(Type,
                                    (attribute_1_name, attribute_1_suffix),
                                    (attribute_2_name, attribute_2_suffix),
                                    ...,
                                    (attribute_n_name, attribute_n_suffix))

        # ADD ATTRIBUTE PLUGINS AS COMPONENTS USING THE SYNTAX
        plugin_name = Cpt(PluginClass, suffix=Plugin_suffix+':')


.. note::

    1. :class:`ophyd.areadetector.detectors.DetectorBase` can be
       swapped out for any other Areadetector Device class that inherits
       from :class:`ophyd.areadetector.detectors.DetectorBase`.

    2. :class:`ophyd.areadetector.triggermixins.SingleTrigger` is an
       optional trigger_mixin class and can be swapped out for any other
       class that inherits from
       :class:`ophyd.areadetector.trigger_mixins.TriggerBase`.  These
       classes provide the logic to 'trigger' the detector and actually
       acquire the images.

    3. PluginClass can be
       :class:`ophyd.areadetector.plugins.PluginBase`,
       :class:`ophyd.areadetector.cam.CamBase` or any plugin/cam class
       that inherits from either of these.

    4. In the ophyd source code, you may see
       :class:`.ophyd.areadetector.base.ADComponent`
       used. Functionally, this is interchangeable with an ordinary
       :class:`.ophyd.device.Component` (imported as ``Cpt`` above); it
       just adds extra machinery for generating a docstring based on a
       scrape of the HTML of the official AreaDetector documentation. For
       custom extensions such as we are addressing here, it is not
       generally applicable.


The Areadetector device should then be instantiated using:

.. code-block:: python

    ADdevice_name = Some_Areadetector_Device_Class(Areadetector_device_PV_suffix,
                                                   name = 'ADdevice_name')


Custom Plugins or Cameras
=========================

For custom hardware based on area-detector it may be necesary to add a
custom plugin or camera class, this section will cover what is
required. Both 'plugins' and 'cameras' act in the same way, but have
slightly different 'base' attributes, hence they have different 'base
classes'.  New Plugin classes should inherit from
:class:`ophyd.areadetector.base.PluginBase` while new Camera classes
should inherit from :class:`ophyd.areadetector.cam.CamBase`.  Both
should have the following PV structure (replace 'plugin' with 'cam'
for cameras):

.. code-block:: python

    PV = 'Areadetector_device_PV_prefix:Plugin_suffix:attribute_suffix'

As an example, for the 'max value' component of the built-in areadetector
'stats' class this looks like:

.. code-block:: python

    PV = 'Areadetector_device_PV_prefix:Stats:max_value'

where ``Areadetector_device_PV_prefix`` is the PV name for the Area
detector device, ``plugin_suffix = Stats`` is the 'stats' Plugin
suffix and ``attribute_suffix = max_value`` is the 'max value'
attribute suffix.


In order to create the class then the following code is required
(where ``XXX`` is the name of the plugin):

.. code-block:: python

    from ophyd.areadetector.base import ad_group, EpicsSignalWithRBV
    from ophyd.signal import EpicsSignal, EpicsSignalRO
    from ophyd.device import DynamicDeviceComponent as DDCpt, Component as Cpt
    from ophyd.areadetector.plugins import PluginBase, register_plugin
    from ophyd.areadetector.filestore_mixins import FileStoreHDF5


    class XXXplugin(PluginBase, FileStoreHDF5):
        '''An areadetector plugin class that does ......'''
        _suffix_re = 'Plugin_suffix\d:'

        # ADD ATTRIBUTES AS COMPONENTS HERE USING THE SYNTAX
        attribute_name = Cpt(Type, attribute_suffix)
            # where 'Type' is EpicsSignal, EpicsSignalRO, EpicsSignalWithRBV,..

        # ADD ATTRIBUTE GROUPS AS COMPONENTS USING THE SYNTAX
        group_name = DDCpt(ad_group(Type,
                                    (attribute_1_name, attribute_1_suffix),
                                    (attribute_2_name, attribute_2_suffix),
                                    ...,
                                    (attribute_n_name, attribute_n_suffix))

    # this allows searching for a plugin class via matching _suffix_re for
    # classes in the registry against the a PV name and is optional.
    register_plugin(XXXplugin)


.. note::

    1. :class:`ophyd.areadetector.plugins.PluginBase` can be swapped
       out for :class:`ophyd.areadetector.cam.CamBase`,
       :class:`ophyd.areadetector.plugins.FilePlugin` or any other
       Areadetector Plugin, cam or FilePlugin class that inherits from
       these.

    2. For FilePlugin plugins the optional filestore_mixin
       :class:`ophyd.areadetector.filestore_mixins.FileStoreHDF5` should
       also be defined. This can be replaced with any class that inherits
       from
       :class:`ophyd.areadetector.filestore_mixins.FileStorePluginBase`.
       These mix-in classes provide the logic for generating Asset
       Registry documents.


Once the class is defined above then it should be added to the Area
detector device class as a component using the code:

.. code-block:: python

    class Some_Areadetector_Device_Class(Some_Area_Detector_Base_Class):
        'The ophyd class for the device that has the custom plugin'

        ...

        xxx = Cpt(XXXplugin, suffix=Plugin_suffix+':')

        ...

The Areadetector device should then be instantiated using:

.. code-block:: python

    ADdevice_name = Some_Areadetector_Device_Class(Areadetector_device_PV_suffix,
                                                  name = 'ADdevice_name')


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

.. [#] This came out of a conversation with Mark Rivers, Thomas Caswell, Stuart Campbell, and Stuart Wilkins and implemented by `Mark <https://github.com/areaDetector/ADCore/pull/323>`_
