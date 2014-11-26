import config

import numpy as np

from ophyd.controls import EpicsMotor, EpicsScaler, PVPositioner, EpicsSignal
from scan1d import scan1d
#from examples.dumb_scan import simple_scan


#slt1_i = EpicsMotor('XF:23ID1-OP{Slt:1-Ax:I}Mtr', name='slt1_i')
#slt1_o = EpicsMotor('XF:23ID1-OP{Slt:1-Ax:O}Mtr', name='slt1_o')
m1 = EpicsMotor(config.motor_recs[0], name='m1')
m2 = EpicsMotor(config.motor_recs[1], name='m2')
fm = config.fake_motors[0]
m7 = PVPositioner(fm['setpoint'],
                       readback=fm['readback'],
                       act=fm['actuate'], act_val=1,
                       stop=fm['stop'], stop_val=1,
                       done=fm['moving'], done_val=1,
                       put_complete=False,
                       name='m7'
                       )
sensor1 = EpicsSignal(config.fake_sensors[0], rw=False, name='sensor1')
sensor2 = EpicsSignal(config.fake_sensors[1], rw=False, name='sensor2')
sclr_trig = EpicsSignal('XF:23ID2-ES{Sclr:1}.CNT', rw=True, name='sclr_trig')
sclr_ch1 = EpicsSignal('XF:23ID2-ES{Sclr:1}.S1', rw=False, name='sclr_ch1')
sca = EpicsScaler('XF:23ID2-ES{Sclr:1}', name='sca')

m1.set_trajectory(np.linspace(-1,2,10))
m2.set_trajectory(np.linspace(-1,2,10))

