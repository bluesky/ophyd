Signals
*******

A ``Signal`` is much like a ``Device`` -- they share almost the same
interface -- but a ``Signal`` has no sub-components. In ophyd's hierarchical,
tree-like representation of a complex piece of hardware, the signals are
the leaves. Each one represents a single PV or a read--write pair of PVs.

.. automodule:: ophyd.signal
   :members:
