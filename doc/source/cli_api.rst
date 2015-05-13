.. currentmodule:: ophyd.userapi.cli_api

Basic Commands
==============

Summary
-------

.. autosummary::
   :toctree: generated/

   wh_pos
   set_pos
   mov
   movr
   set_lm
   log_pos
   log_pos_diff

For basic scanning commands, see the next page.

Positioners and Detectors in Ophyd
----------------------------------

Ophyd represents beamline intruments,
including motors, detectors, and any other hardware, as a Python objects.
Any device that can be written to (in EPICS jargon, "put" to) is considered
a positioner. Thus, positioners include things like temperature controllers
that might not intuitively seems like they fit that title.

*Any* device can be used as a detector. Even devices that are being used as
positioners can be read from (in EPICS jargon, they respond to "get").

The next page covers how to choose detectors and positioners for a scan.

Where are my positioners?
^^^^^^^^^^^^^^^^^^^^^^^^^

Use ``wh_pos()`` to get the current position of all "positioners" and print
them to the screen.


