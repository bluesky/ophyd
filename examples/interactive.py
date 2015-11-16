# run this with: ipython -i interactive.py

import config
import time

from ophyd.controls.positioner import EpicsMotor
import ophyd.commands
from ophyd.commands import (mov, movr, set_pos, wh_pos, set_lm, log_pos,
                            log_pos_diff)

import IPython
ip = IPython.get_ipython()


rec1, rec2, rec3 = config.motor_recs[:3]
m1 = EpicsMotor(rec1)
m2 = EpicsMotor(rec2)
m3 = EpicsMotor(rec3)


# wait for positioners to connect...
time.sleep(1.0)

print('Moving m1 to 0.3:')
mov(m1, 0.3)

print('Moving m1 to 0.0:')
mov(m1, 0.0)

print('Moving m1 to 0.3 (relative):')
movr(m1, 0.3)

print('wh_pos getting all positioners available, if running in IPython:')
wh_pos()

print('wh_pos of a single motor:')
wh_pos([m1])
