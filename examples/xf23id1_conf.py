import numpy as np

from ophyd.controls import EpicsMotor, EpicsScaler, PVPositioner, EpicsSignal
from ophyd.controls import SimDetector
from ophyd.controls import ProsilicaDetector
from ophyd.userapi import *
from scan1d import scan1d

# Slits 

slt1_xg = EpicsMotor('XF:23ID1-OP{Slt:1-Ax:XGap}Mtr', name='slt1_xg')
slt1_xc = EpicsMotor('XF:23ID1-OP{Slt:1-Ax:XCtr}Mtr', name='slt1_xc')
slt1_yg = EpicsMotor('XF:23ID1-OP{Slt:1-Ax:YGap}Mtr', name='slt1_yg')
slt1_yc = EpicsMotor('XF:23ID1-OP{Slt:1-Ax:YCtr}Mtr', name='slt1_yc')

slt2_xg = EpicsMotor('XF:23ID1-OP{Slt:2-Ax:XGap}Mtr', name='slt2_xg')
slt2_xc = EpicsMotor('XF:23ID1-OP{Slt:2-Ax:XCtr}Mtr', name='slt2_xc')
slt2_yg = EpicsMotor('XF:23ID1-OP{Slt:2-Ax:YGap}Mtr', name='slt2_yg')
slt2_yc = EpicsMotor('XF:23ID1-OP{Slt:2-Ax:YCtr}Mtr', name='slt2_yc')

slt3_x = EpicsMotor('XF:23ID1-OP{Slt:3-Ax:X}Mtr', name='slt3_x')
slt3_y = EpicsMotor('XF:23ID1-OP{Slt:3-Ax:Y}Mtr', name='slt3_y')

diag5_y = EpicsMotor('XF:23ID1-BI{Diag:5-Ax:Y}Mtr', name='diag5_y')

#m1 = EpicsMotor(config.motor_recs[0], name='m1')
#m2 = EpicsMotor(config.motor_recs[1], name='m2')
#fm = config.fake_motors[0]
#m7 = PVPositioner(fm['setpoint'],
#                       readback=fm['readback'],
#                       act=fm['actuate'], act_val=1,
#                       stop=fm['stop'], stop_val=1,
#                       done=fm['moving'], done_val=1,
#                       put_complete=False,
#                       name='m7'
#                       )

sclr_trig = EpicsSignal('XF:23ID1-ES{Sclr:1}.CNT', rw=True, name='sclr_trig')
sclr_ch1 = EpicsSignal('XF:23ID1-ES{Sclr:1}.S6', rw=False, name='sclr_ch6')
#sca = EpicsScaler('XF:23ID2-ES{Sclr:1}', name='sca')
#
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

# AreaDetector Beam Instrumentation
# diag3_cam = ProsilicaDetector('XF:23ID1-BI{Diag:3-Cam:1}')
# For now, access as simple 'signals'
diag3_cam = EpicsSignal('XF:23ID1-BI{Diag:3-Cam:1}cam1:Acquire_RBV',
                         write_pv='XF:23ID1-BI{Diag:3-Cam:1}cam1:Acquire',
                         rw=True, name='diag3_cam_trigger')
#simdet_filename = EpicsSignal('XF:31IDA-BI{Cam:Tbl}TIFF1:FullFileName_RBV',
#                                rw=False, string=True, name='simdet_filename')
diag3_tot1 = EpicsSignal('XF:23ID1-BI{Diag:3-Cam:1}Stats1:Total_RBV',
                                rw=False, name='diag3_tot1')
diag3_tot5 = EpicsSignal('XF:23ID1-BI{Diag:3-Cam:1}Stats5:Total_RBV',
                                rw=False, name='diag3_tot5')
pimte_cam = EpicsSignal('XF:23ID1-ES{Dif-Cam:PIMTE}cam1:Acquire_RBV',
                         write_pv='XF:23ID1-ES{Dif-Cam:PIMTE}cam1:Acquire',
                         rw=True, name='pimte_cam_trigger')
#simdet_filename = EpicsSignal('XF:31IDA-ES{Cam:Tbl}TIFF1:FullFileName_RBV',
#                                rw=False, string=True, name='simdet_filename')
pimte_tot1 = EpicsSignal('XF:23ID1-ES{Dif-Cam:PIMTE}Stats1:Total_RBV',
                                rw=False, name='pimte_tot1')
pimte_tot4 = EpicsSignal('XF:23ID1-ES{Dif-Cam:PIMTE}Stats4:Total_RBV',
                                rw=False, name='pimte_tot4')
pimte_tot5 = EpicsSignal('XF:23ID1-ES{Dif-Cam:PIMTE}Stats5:Total_RBV',
                                rw=False, name='pimte_tot5')
