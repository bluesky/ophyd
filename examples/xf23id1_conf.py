import config

import numpy as np

from ophyd.controls import EpicsMotor, EpicsScaler, PVPositioner, EpicsSignal
from ophyd.controls import SimDetector

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

# initialize Positioner for Mono Energy
args = ('XF:23ID1-OP{Mono}Enrgy-SP',
        {'readback': 'XF:23ID1-OP{Mono}Enrgy-I',
        'stop': 'XF:23ID1-OP{Mono}Cmd:Stop-Cmd',
        'stop_val': 1,
        'done': 'XF:23ID1-OP{Mono}Sts:Move-Sts',
        'done_val': 0,
        'name': 'pgm_energy'
        })
pgm_energy = PVPositioner(args[0], **args[1])

# initialize M1A virtual axes Positioner
args = ('XF:23IDA-OP:1{Mir:1-Ax:Z}Mtr_POS_SP',
        {'readback': 'XF:23IDA-OP:1{Mir:1-Ax:Z}Mtr_MON',
         'act': 'XF:23IDA-OP:1{Mir:1}MOVE_CMD.PROC',
         'act_val': 1,
         'stop': 'XF:23IDA-OP:1{Mir:1}STOP_CMD.PROC',
         'stop_val': 1,
         'done': 'XF:23IDA-OP:1{Mir:1}BUSY_STS',
         'done_val': 0,
         'name': 'm1a_z',
        })
m1a_z = PVPositioner(args[0], **args[1])

# AreaDetector crud
simdet = SimDetector(config.sim_areadetector[0]['prefix'])
# For now, access as simple 'signals'
simdet_acq = EpicsSignal('XF:31IDA-BI{Cam:Tbl}cam1:Acquire_RBV',
                         write_pv='XF:31IDA-BI{Cam:Tbl}cam1:Acquire',
                         rw=True, name='simdet_acq')
simdet_filename = EpicsSignal('XF:31IDA-BI{Cam:Tbl}TIFF1:FullFileName_RBV',
                                rw=False, string=True, name='simdet_filename')
simdet_intensity = EpicsSignal('XF:31IDA-BI{Cam:Tbl}Stats5:Total_RBV',
                                rw=False, name='simdet_intensity')
