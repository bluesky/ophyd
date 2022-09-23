# Relationship to EPICS

Ophyd is often used to integrate with hardware via EPICS, but it is
also used to integrate using other protocols. Ophyd's EPICS dependencies are
optional; Ophyd can be installed and used without any EPICS-related libraries.

The Ophyd codebase is older than Bluesky. The way its modules are organized
and named shows that it was *originally* conceived as an interface to EPICS
specifically. A 2015 rewrite re-conceived the library as a toolkit for
integrating *any* hardware with Bluesky, with a clear emphasis on EPICS but
also some generic components with no EPICS dependency.

Specifically, Ophyd contains three logically separate things:

* Generic classes and utilities for integrating potentially any control
  system with Bluesky. These include the Status API, the Device and Component
  classes, and various utility functions.
* An implementation of the Bluesky interface on an EPICS PV or read/write pair
  of PVs. This includes {class}`ophyd.signal.EpicsSignal` and related objects.
* An implementation of the Bluesky interface for common EPICS IOCs such as
  Epics Motor and Area Detector.

These aspects could be split into separate packages, but thus far the benefits
of making that separation have been judged not worth the cost of managing
separate CI harnesses and releases.

One of the problems that Ophyd solves is particular to Channel Access ("EPICS
V3"). On the server side, in an IOC, there are explicit groupings and
relationships among various parts of a device. The Channel Access protocol
has no way to express this grouping, so the information is not available
to the client. There is *implicit* grouping information in the nested structure
of PV names, but there are no technical guarantees, only soft conventions.
Ophyd addresses this but re-encoding this structure on the client side.
This is not a problem for protocols like PV Access ("Epics V4 / V7") or Tango,
and so this client-side grouping feature of Ophyd becomes less important. The
feature is still useful for creating *ad doc* client-side groupings that are not
a literal reflection of the arrangement of the hardware.