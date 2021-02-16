A single EPICS PV
=================

In this tutorial we will read, write, and monitor an EPICS PV in ophyd.

Set up for tutorial
-------------------

For this tutorial you will need an EPICS IOC serving a PV that you can connect
to.  We suggest starting a simple test IOC using `caproto`_, as follows. If
you already have another IOC handy, you may use that instead.

Install caproto.

.. code:: bash

   pip install caproto[standard]

   # If you the above gives you trouble, you can try a lighter-weight
   # installation that omits some optional dependencies.
   pip install caproto

Stand caproto's random walk IOC.

.. code:: bash

   python -m caproto.ioc_examples_random_walk --list-pvs

Start your favorite interactive Python environment, such as ``ipython`` or
``jupyter lab``.

Create an ophyd ``EpicsSignal``
-------------------------------

TODO

* EpicsSignal
* EpicsSignalRO
* Emphasize that if you want to use it with the RunEngine, you should stop here
  and let the RunEngine worry about read/write/subscribe.
* read
* write
* subscribe
