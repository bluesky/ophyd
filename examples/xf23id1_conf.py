import numpy as np

from ophyd import EpicsMotor, EpicsScaler, PVPositioner, EpicsSignal
from ophyd import SimDetector
from ophyd import ProsilicaDetector
from ophyd.userapi import *
import logging

from pyOlog.OlogHandler import OlogHandler

# Undulator

epu1_gap = PVPositioner('XF:23ID-ID{EPU:1-Ax:Gap}Pos-SP',
                        readback='XF:23ID-ID{EPU:1-Ax:Gap}Pos-I',
                        stop='SR:C23-ID:G1A{EPU:1-Ax:Gap}-Mtr.STOP',
                        stop_val=1,
                        done='XF:23ID-ID{EPU:1-Ax:Gap}Pos-Sts',
                        done_val=0,
                        name='epu2_gap')

epu2_gap = PVPositioner('XF:23ID-ID{EPU:2-Ax:Gap}Pos-SP',
                        readback='XF:23ID-ID{EPU:2-Ax:Gap}Pos-I',
                        stop='SR:C23-ID:G1A{EPU:2-Ax:Gap}-Mtr.STOP',
                        stop_val=1,
                        done='XF:23ID-ID{EPU:2-Ax:Gap}Pos-Sts',
                        done_val=0,
                        name='epu2_gap')

# Slits

slt1_xg   = EpicsMotor('XF:23ID1-OP{Slt:1-Ax:XGap}Mtr', name = 'slt1_xg')
slt1_xc   = EpicsMotor('XF:23ID1-OP{Slt:1-Ax:XCtr}Mtr', name = 'slt1_xc')
slt1_yg   = EpicsMotor('XF:23ID1-OP{Slt:1-Ax:YGap}Mtr', name = 'slt1_yg')
slt1_yc   = EpicsMotor('XF:23ID1-OP{Slt:1-Ax:YCtr}Mtr', name = 'slt1_yc')

slt2_xg   = EpicsMotor('XF:23ID1-OP{Slt:2-Ax:XGap}Mtr', name = 'slt2_xg')
slt2_xc   = EpicsMotor('XF:23ID1-OP{Slt:2-Ax:XCtr}Mtr', name = 'slt2_xc')
slt2_yg   = EpicsMotor('XF:23ID1-OP{Slt:2-Ax:YGap}Mtr', name = 'slt2_yg')
slt2_yc   = EpicsMotor('XF:23ID1-OP{Slt:2-Ax:YCtr}Mtr', name = 'slt2_yc')

slt3_x    = EpicsMotor('XF:23ID1-OP{Slt:3-Ax:X}Mtr', name    = 'slt3_x')
slt3_y    = EpicsMotor('XF:23ID1-OP{Slt:3-Ax:Y}Mtr', name    = 'slt3_y')

diag2_y   = EpicsMotor('XF:23ID1-BI{Diag:2-Ax:Y}Mtr', name   = 'diag2_y')
diag3_y   = EpicsMotor('XF:23ID1-BI{Diag:3-Ax:Y}Mtr', name   = 'diag3_y')
diag5_y   = EpicsMotor('XF:23ID1-BI{Diag:5-Ax:Y}Mtr', name   = 'diag5_y')
diag6_y   = EpicsMotor('XF:23ID1-BI{Diag:6-Ax:Y}Mtr', name   = 'diag6_y')

sclr_trig = EpicsSignal('XF:23ID1-ES{Sclr:1}.CNT', rw = True,
                        name  = 'sclr_trig')
sclr_ch1  = EpicsSignal('XF:23ID1-ES{Sclr:1}.S1', rw = False,
                        name = 'sclr_ch1')
sclr_ch2  = EpicsSignal('XF:23ID1-ES{Sclr:1}.S2', rw = False,
                        name = 'sclr_ch2')
sclr_ch3  = EpicsSignal('XF:23ID1-ES{Sclr:1}.S3', rw = False,
                        name = 'sclr_ch3')
sclr_ch4  = EpicsSignal('XF:23ID1-ES{Sclr:1}.S4', rw = False,
                        name = 'sclr_ch4')
sclr_ch5  = EpicsSignal('XF:23ID1-ES{Sclr:1}.S5', rw = False,
                        name = 'sclr_ch5')
sclr_ch6  = EpicsSignal('XF:23ID1-ES{Sclr:1}.S6', rw = False,
                        name = 'sclr_ch6')

# initialize Positioner for Mono Energy
args = ('XF:23ID1-OP{Mono}Enrgy-SP',
        {'readback': 'XF:23ID1-OP{Mono}Enrgy-I',
        'stop': 'XF:23ID1-OP{Mono}Cmd:Stop-Cmd',
        'stop_val': 1,
        'done': 'XF:23ID1-OP{Mono}Sts:Move-Sts',
        'done_val': 0,
        'name': 'energy'
        })
energy = PVPositioner(args[0], **args[1])

# Lakeshore 336 Temp Controller

temp_sp = PVPositioner('XF:23ID1-ES{TCtrl:1-Out:1}T-SP',
                       readback='XF:23ID1-ES{TCtrl:1-Out:1}T-RB',
                       done='XF:23ID1-ES{TCtrl:1-Out:1}Sts:Ramp-Sts',
                       done_val=0, name='temp_sp')

temp_a = EpicsSignal('XF:23ID1-ES{TCtrl:1-Chan:A}T-I', rw = False,
                     name = 'temp_a')
temp_b = EpicsSignal('XF:23ID1-ES{TCtrl:1-Chan:B}T-I', rw = False,
                     name = 'temp_b')
## initialize M1A virtual axes Positioner
#args = ('XF:23IDA-OP:1{Mir:1-Ax:Z}Mtr_POS_SP',
#        {'readback': 'XF:23IDA-OP:1{Mir:1-Ax:Z}Mtr_MON',
#         'act': 'XF:23IDA-OP:1{Mir:1}MOVE_CMD.PROC',
#         'act_val': 1,
#         'stop': 'XF:23IDA-OP:1{Mir:1}STOP_CMD.PROC',
#         'stop_val': 1,
#         'done': 'XF:23IDA-OP:1{Mir:1}BUSY_STS',
#         'done_val': 0,
#         'name': 'm1a_z',
#        })
#m1a_z = PVPositioner(args[0], **args[1])

# AreaDetector Beam Instrumentation
# diag3_cam = ProsilicaDetector('XF:23ID1-BI{Diag:3-Cam:1}')
# For now, access as simple 'signals'
diag3_cam = EpicsSignal('XF:23ID1-BI{Diag:3-Cam:1}cam1:Acquire_RBV',
                        write_pv='XF:23ID1-BI{Diag:3-Cam:1}cam1:Acquire',
                        rw=True, name='diag3_cam_trigger')

diag5_cam = EpicsSignal('XF:23ID1-BI{Diag:5-Cam:1}cam1:Acquire_RBV',
                        write_pv='XF:23ID1-BI{Diag:5-Cam:1}cam1:Acquire',
                        rw=True, name='diag5_cam_trigger')

#
#simdet_filename = EpicsSignal('XF:31IDA-BI{Cam:Tbl}TIFF1:FullFileName_RBV',
#                                rw=False, string=True, name='simdet_filename')

diag3_tot1 = EpicsSignal('XF:23ID1-BI{Diag:3-Cam:1}Stats1:Total_RBV',
                         rw=False, name='diag3_tot1')
diag3_tot5 = EpicsSignal('XF:23ID1-BI{Diag:3-Cam:1}Stats5:Total_RBV',
                         rw=False, name='diag3_tot5')

diag5_tot1 = EpicsSignal('XF:23ID1-BI{Diag:5-Cam:1}Stats1:Total_RBV',
                         rw=False, name='diag5_tot1')
diag5_tot5 = EpicsSignal('XF:23ID1-BI{Diag:5-Cam:1}Stats5:Total_RBV',
                         rw=False, name='diag5_tot5')

pimte_cam = EpicsSignal('XF:23ID1-ES{Dif-Cam:PIMTE}cam1:Acquire_RBV',
                        write_pv='XF:23ID1-ES{Dif-Cam:PIMTE}cam1:Acquire',
                        rw=True, name='pimte_cam_trigger')
pimte_tot1 = EpicsSignal('XF:23ID1-ES{Dif-Cam:PIMTE}Stats1:Total_RBV',
                         rw=False, name='pimte_tot1')
pimte_tot2 = EpicsSignal('XF:23ID1-ES{Dif-Cam:PIMTE}Stats2:Total_RBV',
                         rw=False, name='pimte_tot2')
pimte_tot3 = EpicsSignal('XF:23ID1-ES{Dif-Cam:PIMTE}Stats3:Total_RBV',
                         rw=False, name='pimte_tot3')
pimte_tot4 = EpicsSignal('XF:23ID1-ES{Dif-Cam:PIMTE}Stats4:Total_RBV',
                         rw=False, name='pimte_tot4')
pimte_tot5 = EpicsSignal('XF:23ID1-ES{Dif-Cam:PIMTE}Stats5:Total_RBV',
                         rw=False, name='pimte_tot5')

#
# Endstation motors
#


delta   = EpicsMotor('XF:23ID1-ES{Dif-Ax:Del}Mtr', name = 'delta')
gamma   = EpicsMotor('XF:23ID1-ES{Dif-Ax:Gam}Mtr', name = 'gamma')
theta   = EpicsMotor('XF:23ID1-ES{Dif-Ax:Th}Mtr', name = 'theta')

sx   = EpicsMotor('XF:23ID1-ES{Dif-Ax:X}Mtr', name = 'sx')
sy   = EpicsMotor('XF:23ID1-ES{Dif-Ax:Y}Mtr', name = 'sy')
sz   = EpicsMotor('XF:23ID1-ES{Dif-Ax:Z}Mtr', name = 'sz')

nptx = EpicsMotor('XF:23ID1-ES{Dif:Lens-Ax:TopX}Mtr', name = 'nptx')
npty = EpicsMotor('XF:23ID1-ES{Dif:Lens-Ax:TopY}Mtr', name = 'npty')
nptz = EpicsMotor('XF:23ID1-ES{Dif:Lens-Ax:TopZ}Mtr', name = 'nptz')
npbx = EpicsMotor('XF:23ID1-ES{Dif:Lens-Ax:BtmX}Mtr', name = 'npbx')
npby = EpicsMotor('XF:23ID1-ES{Dif:Lens-Ax:BtmY}Mtr', name = 'npby')
npbz = EpicsMotor('XF:23ID1-ES{Dif:Lens-Ax:BtmZ}Mtr', name = 'npbz')


# Setup auto logging

olog_handler = OlogHandler(logbooks='Data Acquisition')
olog_handler.setLevel(logging.INFO)
