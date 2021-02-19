Installation Tutorial
=====================

This tutorial covers

* Installation using conda
* Installation using pip
* Installation from source

Conda
-----

We strongly recommend creating a fresh environment.

.. code:: bash

   conda create -n try-ophyd
   conda activate try-ophyd

Install Ophyd from the ``nsls2forge`` conda channel maintained by NSLS-II.
(The conda package will also install ``pyepics``. It's not needed for *all*
use cases, but it is commonly used to enable Ophyd to work with EPICS.)

.. code:: bash

   conda install -c nsls2forge ophyd

Finally, to follow along with the EPICS tutorials, you should also install
``caproto`` to run EPICS servers with simulated hardware and ``bluesky`` to
orchestrate scans with the RunEngine.

.. code:: bash

   conda install -c nsls2forge bluesky caproto

Pip
---

We strongly recommend creating a fresh environment.

.. code:: bash

   python3 -m venv try-ophyd
   source try-ophyd/bin/activate

Install Ophyd from PyPI.

.. code:: bash

   python3 -m pip install ophyd

If you intend to use ophyd with EPICS, you should also install an EPICS client
library for ophyd to use---either pyepics (recommended) or caproto (experimental).

.. code:: bash

   python3 -m pip install pyepics  # or caproto if you are feeling adventurous

Finally, to follow along with the EPICS tutorials, you should also install
``caproto`` to run EPICS servers with simulated hardware and ``bluesky`` to
orchestrate scans with the RunEngine.

.. code:: bash

   python3 -m pip install bluesky caproto[standard]

Source
------

To install an editable installation for local development:

.. code:: bash

   git clone https://github.com/bluesky/ophyd
   cd ophyd
   pip install -e .
