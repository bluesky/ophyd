.. include:: ../../README.rst

How the documentation is structured
-----------------------------------

.. rst-class:: columns

:ref:`tutorials`
~~~~~~~~~~~~~~~~

Tutorials for installation and usage. New users start here.

.. rst-class:: columns

:ref:`how-to`
~~~~~~~~~~~~~

Practical step-by-step guides for the more experienced user.

.. rst-class:: columns

:ref:`explanations`
~~~~~~~~~~~~~~~~~~~

Explanation of how the library works and why it works that way.

.. rst-class:: columns

:ref:`reference`
~~~~~~~~~~~~~~~~

Technically detailed API documentation.

.. rst-class:: endcolumns

About the documentation
~~~~~~~~~~~~~~~~~~~~~~~

`Why is the documentation structured this way? <https://documentation.divio.com>`_

.. toctree::
   :caption: Tutorials
   :name: tutorials
   :maxdepth: 1

   tutorials/install
   tutorials/single-PV
   tutorials/device

.. toctree::
   :caption: How-to Guides
   :name: how-to
   :maxdepth: 1

   how-to/pseudopositioner
   how-to/docker

.. toctree::
   :caption: Explanations
   :name: explanations
   :maxdepth: 1

   explanations/relationship-to-epics
   explanations/area-detector
   explanations/status
   explanations/staging

.. rst-class:: no-margin-after-ul

.. toctree::
   :caption: Reference
   :name: reference
   :maxdepth: 1

   reference/core
   reference/builtin-devices
   reference/signals
   reference/positioners
   reference/logging
   reference/release_notes

* :ref:`genindex`

.. toctree::
   :hidden:
   :caption: Bluesky Project

   Homepage <https://blueskyproject.io>
   GitHub <https://github.com/bluesky>

.. toctree::
   :hidden:
   :caption: Getting Help

   Gitter <https://gitter.im/NSLS-II/DAMA>
.. ophyd documentation master file, created by
   sphinx-quickstart on Fri Nov  7 11:18:58 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.
