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

In Python, everything is an "object." Ophyd represents beamline intruments,
including motors, detectors, and any other hardware, as a Python objects.



Where are my positioners?
^^^^^^^^^^^^^^^^^^^^^^^^^

Use ``wh_pos()`` to get the current position of all "positioners" and print
them to the screen.


