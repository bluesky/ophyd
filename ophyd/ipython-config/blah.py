import logging
session_mgr._logger.setLevel(logging.CRITICAL)
from ophyd.userapi import *

###  endstation setup, configuring PVs

from ophyd.controls import PVPositioner, EpicsMotor

# Diffo angles

delta = EpicsMotor('XF:23ID1-ES{Dif-Ax:Del}Mtr', name='delta')
gamma = EpicsMotor('XF:23ID1-ES{Dif-Ax:Gam}Mtr', name='gamma')
theta = EpicsMotor('XF:23ID1-ES{Dif-Ax:Th}Mtr', name='theta')

# Sample positions

sx = EpicsMotor('XF:23ID1-ES{Dif-Ax:X}Mtr', name='sx')
sy = PVPositioner('XF:23ID1-ES{Dif-Ax:SY}Pos-SP',
                  readback='XF:23ID1-ES{Dif-Ax:SY}Pos-RB',
                  stop='XF:23ID1-ES{Dif-Cryo}Cmd:Stop-Cmd',
                  stop_val=1, put_complete=True,
                  name='sy')

sz = PVPositioner('XF:23ID1-ES{Dif-Ax:SZ}Pos-SP',
                  readback='XF:23ID1-ES{Dif-Ax:SZ}Pos-SP',
                  stop='XF:23ID1-ES{Dif-Cryo}Cmd:Stop-Cmd',
                  stop_val=1, put_complete=True,
                  name='sz')

cryoangle = PVPositioner('XF:23ID1-ES{Dif-Cryo}Pos:Angle-SP',
                         readback='XF:23ID1-ES{Dif-Cryo}Pos:Angle-RB',
                         name='cryoangle')

# Nano-positioners

nptx = EpicsMotor('XF:23ID1-ES{Dif:Lens-Ax:TopX}Mtr', name='nptx')
npty = EpicsMotor('XF:23ID1-ES{Dif:Lens-Ax:TopY}Mtr', name='npty')
nptz = EpicsMotor('XF:23ID1-ES{Dif:Lens-Ax:TopZ}Mtr', name='nptz')
npbx = EpicsMotor('XF:23ID1-ES{Dif:Lens-Ax:BtmX}Mtr', name='npbx')
npby = EpicsMotor('XF:23ID1-ES{Dif:Lens-Ax:BtmY}Mtr', name='npby')
npbz = EpicsMotor('XF:23ID1-ES{Dif:Lens-Ax:BtmZ}Mtr', name='npbz')

# Diagnostic Axis

es_diag1_y = EpicsMotor('XF:23ID1-ES{Diag:1-Ax:Y}Mtr', name='es_diag1_y')

# Lakeshore 336 Temp Controller

temp_sp = PVPositioner('XF:23ID1-ES{TCtrl:1-Out:1}T-SP',
                       readback='XF:23ID1-ES{TCtrl:1-Out:1}T-RB',
                       done='XF:23ID1-ES{TCtrl:1-Out:1}Sts:Ramp-Sts',
                       done_val=0, name='temp_sp')


from ophyd.controls import PVPositioner

# Undulator

epu1_gap = PVPositioner('XF:23ID-ID{EPU:1-Ax:Gap}Pos-SP',
                        readback='XF:23ID-ID{EPU:1-Ax:Gap}Pos-I',
                        stop='SR:C23-ID:G1A{EPU:1-Ax:Gap}-Mtr.STOP',
                        stop_val=1,
                        put_complete=True,
                        name='epu1_gap')

epu2_gap = PVPositioner('XF:23ID-ID{EPU:2-Ax:Gap}Pos-SP',
                        readback='XF:23ID-ID{EPU:2-Ax:Gap}Pos-I',
                        stop='SR:C23-ID:G1A{EPU:2-Ax:Gap}-Mtr.STOP',
                        stop_val=1,
                        put_complete=True,
                        name='epu2_gap')

epu1_phase = PVPositioner('XF:23ID-ID{EPU:1-Ax:Phase}Pos-SP',
                          readback='XF:23ID-ID{EPU:1-Ax:Phase}Pos-I',
                          stop='SR:C23-ID:G1A{EPU:1-Ax:Phase}-Mtr.STOP',
                          stop_val=1,
                          put_complete=True,
                          name='epu1_phase')

epu2_phase = PVPositioner('XF:23ID-ID{EPU:2-Ax:Phase}Pos-SP',
                          readback='XF:23ID-ID{EPU:2-Ax:Phase}Pos-I',
                          stop='SR:C23-ID:G1A{EPU:2-Ax:Phase}-Mtr.STOP',
                          stop_val=1,
                          put_complete=True,
                          name='epu2_phase')

# Front End Slits (Primary Slits)

fe_xc = PVPositioner('FE:C23A-OP{Slt:12-Ax:X}center',
                     readback='FE:C23A-OP{Slt:12-Ax:X}t2.D',
                     stop='FE:C23A-CT{MC:1}allstop',
                     stop_val=1, put_complete=True,
                     name='fe_xc')

fe_yc = PVPositioner('FE:C23A-OP{Slt:12-Ax:Y}center',
                     readback='FE:C23A-OP{Slt:12-Ax:Y}t2.D',
                     stop='FE:C23A-CT{MC:1}allstop',
                     stop_val=1,
                     put_complete=True,
                     name='fe_yc')

fe_xg = PVPositioner('FE:C23A-OP{Slt:12-Ax:X}size',
                     readback='FE:C23A-OP{Slt:12-Ax:X}t2.C',
                     stop='FE:C23A-CT{MC:1}allstop',
                     stop_val=1, put_complete=True,
                     name='fe_xg')

fe_yg = PVPositioner('FE:C23A-OP{Slt:12-Ax:Y}size',
                     readback='FE:C23A-OP{Slt:12-Ax:Y}t2.C',
                     stop='FE:C23A-CT{MC:1}allstop',
                     stop_val=1,
                     put_complete=True,
                     name='fe_yg')
from ophyd.controls import EpicsMotor, PVPositioner

# M1A

kwargs = {'act': 'XF:23IDA-OP:1{Mir:1}MOVE_CMD.PROC',
          'act_val': 1,
          'stop': 'XF:23IDA-OP:1{Mir:1}STOP_CMD.PROC',
          'stop_val': 1,
          'done': 'XF:23IDA-OP:1{Mir:1}BUSY_STS',
          'done_val': 0}

m1a_z = PVPositioner('XF:23IDA-OP:1{Mir:1-Ax:Z}Mtr_POS_SP',
                     readback='XF:23IDA-OP:1{Mir:1-Ax:Z}Mtr_MON',
                     name='m1a_z', **kwargs)
m1a_y = PVPositioner('XF:23IDA-OP:1{Mir:1-Ax:Y}Mtr_POS_SP',
                     readback='XF:23IDA-OP:1{Mir:1-Ax:Y}Mtr_MON',
                     name='m1a_y', **kwargs)
m1a_x = PVPositioner('XF:23IDA-OP:1{Mir:1-Ax:X}Mtr_POS_SP',
                     readback='XF:23IDA-OP:1{Mir:1-Ax:X}Mtr_MON',
                     name='m1a_x', **kwargs)
m1a_pit = PVPositioner('XF:23IDA-OP:1{Mir:1-Ax:Pit}Mtr_POS_SP',
                       readback='XF:23IDA-OP:1{Mir:1-Ax:Pit}Mtr_MON',
                       name='m1a_pit', **kwargs)
m1a_yaw = PVPositioner('XF:23IDA-OP:1{Mir:1-Ax:Yaw}Mtr_POS_SP',
                       readback='XF:23IDA-OP:1{Mir:1-Ax:Yaw}Mtr_MON',
                       name='m1a_yaw', **kwargs)
m1a_rol = PVPositioner('XF:23IDA-OP:1{Mir:1-Ax:Rol}Mtr_POS_SP',
                       readback='XF:23IDA-OP:1{Mir:1-Ax:Rol}Mtr_MON',
                       name='m1a_rol', **kwargs)

m1a = [m1a_z, m1a_y, m1a_x, m1a_pit, m1a_yaw, m1a_rol]

# M1B1

kwargs = {'act': 'XF:23IDA-OP:2{Mir:1A}MOVE_CMD.PROC',
          'act_val': 1,
          'stop': 'XF:23IDA-OP:2{Mir:1A}STOP_CMD.PROC',
          'stop_val': 1,
          'done': 'XF:23IDA-OP:2{Mir:1A}BUSY_STS',
          'done_val': 0}

m1b1_z = PVPositioner('XF:23IDA-OP:2{Mir:1A-Ax:Z}Mtr_POS_SP',
                      readback='XF:23IDA-OP:2{Mir:1A-Ax:Z}Mtr_MON',
                      name='m1b1_z', **kwargs)
m1b1_y = PVPositioner('XF:23IDA-OP:2{Mir:1A-Ax:Y}Mtr_POS_SP',
                      readback='XF:23IDA-OP:2{Mir:1A-Ax:Y}Mtr_MON',
                      name='m1b1_y', **kwargs)
m1b1_x = PVPositioner('XF:23IDA-OP:2{Mir:1A-Ax:X}Mtr_POS_SP',
                      readback='XF:23IDA-OP:2{Mir:1A-Ax:X}Mtr_MON',
                      name='m1b1_x', **kwargs)
m1b1_pit = PVPositioner('XF:23IDA-OP:2{Mir:1A-Ax:Pit}Mtr_POS_SP',
                        readback='XF:23IDA-OP:2{Mir:1A-Ax:Pit}Mtr_MON',
                        name='m1b1_pit', **kwargs)
m1b1_yaw = PVPositioner('XF:23IDA-OP:2{Mir:1A-Ax:Yaw}Mtr_POS_SP',
                        readback='XF:23IDA-OP:2{Mir:1A-Ax:Yaw}Mtr_MON',
                        name='m1b1_yaw', **kwargs)
m1b1_rol = PVPositioner('XF:23IDA-OP:2{Mir:1A-Ax:Rol}Mtr_POS_SP',
                        readback='XF:23IDA-OP:2{Mir:1A-Ax:Rol}Mtr_MON',
                        name='m1b1_rol', **kwargs)

m1b1 = [m1b1_z, m1b1_y, m1b1_x, m1b1_pit, m1b1_yaw, m1b1_rol]

# M1B2

kwargs = {'act': 'XF:23IDA-OP:2{Mir:1B}MOVE_CMD.PROC',
          'act_val': 1,
          'stop': 'XF:23IDA-OP:2{Mir:1B}STOP_CMD.PROC',
          'stop_val': 1,
          'done': 'XF:23IDA-OP:2{Mir:1B}BUSY_STS',
          'done_val': 0}

m1b2_z = PVPositioner('XF:23IDA-OP:2{Mir:1B-Ax:Z}Mtr_POS_SP',
                      readback='XF:23IDA-OP:2{Mir:1B-Ax:Z}Mtr_MON',
                      name='m1b2_z', **kwargs)
m1b2_y = PVPositioner('XF:23IDA-OP:2{Mir:1B-Ax:Y}Mtr_POS_SP',
                      readback='XF:23IDA-OP:2{Mir:1B-Ax:Y}Mtr_MON',
                      name='m1b2_y', **kwargs)
m1b2_x = PVPositioner('XF:23IDA-OP:2{Mir:1B-Ax:X}Mtr_POS_SP',
                      readback='XF:23IDA-OP:2{Mir:1B-Ax:X}Mtr_MON',
                      name='m1b2_x', **kwargs)
m1b2_pit = PVPositioner('XF:23IDA-OP:2{Mir:1B-Ax:Pit}Mtr_POS_SP',
                        readback='XF:23IDA-OP:2{Mir:1B-Ax:Pit}Mtr_MON',
                        name='m1b2_pit', **kwargs)
m1b2_yaw = PVPositioner('XF:23IDA-OP:2{Mir:1B-Ax:Yaw}Mtr_POS_SP',
                        readback='XF:23IDA-OP:2{Mir:1B-Ax:Yaw}Mtr_MON',
                        name='m1b2_yaw', **kwargs)
m1b2_rol = PVPositioner('XF:23IDA-OP:2{Mir:1B-Ax:Rol}Mtr_POS_SP',
                        readback='XF:23IDA-OP:2{Mir:1B-Ax:Rol}Mtr_MON',
                        name='m1b2_rol', **kwargs)

m1b2 = [m1b2_z, m1b2_y, m1b2_x, m1b2_pit, m1b2_yaw, m1b2_rol]

# VLS-PGM

pgm_energy = PVPositioner('XF:23ID1-OP{Mono}Enrgy-SP',
                          readback='XF:23ID1-OP{Mono}Enrgy-I',
                          stop='XF:23ID1-OP{Mono}Cmd:Stop-Cmd',
                          stop_val=1, put_complete=True,
                          name='pgm_energy')

pgm_mir_pit = EpicsMotor('XF:23ID1-OP{Mono-Ax:MirP}Mtr', name='pgm_mir_pit')
pgm_grt_pit = EpicsMotor('XF:23ID1-OP{Mono-Ax:GrtP}Mtr', name='pgm_grt_pit')
pgm_mir_x = EpicsMotor('XF:23ID1-OP{Mono-Ax:MirX}Mtr', name='pgm_mir_x')
pgm_grt_x = EpicsMotor('XF:23ID1-OP{Mono-Ax:GrtX}Mtr', name='pgm_grt_x')

# M3A Mirror

m3a_x = EpicsMotor('XF:23ID1-OP{Mir:3-Ax:XAvg}Mtr', name='m3a_x')
m3a_pit = EpicsMotor('XF:23ID1-OP{Mir:3-Ax:P}Mtr',   name='m3a_pit')
m3a_bdr = EpicsMotor('XF:23ID1-OP{Mir:3-Ax:Bdr}Mtr',  name='m3a_bdr')

# Fast CCD Shutter

sh_y = EpicsMotor('XF:23ID1-OP{Sh:Fast-Ax:Y}Mtr', name='sh_y')
sh_x = EpicsMotor('XF:23ID1-OP{Sh:Fast-Ax:X}Mtr', name='sh_x')

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

# Diagnostic Manipulators

diag2_y = EpicsMotor('XF:23ID1-BI{Diag:2-Ax:Y}Mtr', name='diag2_y')
diag3_y = EpicsMotor('XF:23ID1-BI{Diag:3-Ax:Y}Mtr', name='diag3_y')
diag5_y = EpicsMotor('XF:23ID1-BI{Diag:5-Ax:Y}Mtr', name='diag5_y')
diag6_y = EpicsMotor('XF:23ID1-BI{Diag:6-Ax:Y}Mtr', name='diag6_y')


## DETECTORS

from ophyd.controls import ProsilicaDetector, EpicsSignal, EpicsScaler

# CSX-1 Scalar

sclr = EpicsScaler('XF:23ID1-ES{Sclr:1}', name='sclr', numchan=32)
sclr_trig = EpicsSignal('XF:23ID1-ES{Sclr:1}.CNT', rw=True,
                        name='sclr_trig')
sclr_ch1 = EpicsSignal('XF:23ID1-ES{Sclr:1}.S1', rw=False,
                       name='sclr_ch1')
sclr_ch2 = EpicsSignal('XF:23ID1-ES{Sclr:1}.S2', rw=False,
                       name='sclr_ch2')
sclr_ch3 = EpicsSignal('XF:23ID1-ES{Sclr:1}.S3', rw=False,
                       name='sclr_ch3')
sclr_ch4 = EpicsSignal('XF:23ID1-ES{Sclr:1}.S4', rw=False,
                       name='sclr_ch4')
sclr_ch5 = EpicsSignal('XF:23ID1-ES{Sclr:1}.S5', rw=False,
                       name='sclr_ch5')
sclr_ch6 = EpicsSignal('XF:23ID1-ES{Sclr:1}.S6', rw=False,
                       name='sclr_ch6')
temp_a = EpicsSignal('XF:23ID1-ES{TCtrl:1-Chan:A}T-I', rw=False,
                     name='temp_a')
temp_b = EpicsSignal('XF:23ID1-ES{TCtrl:1-Chan:B}T-I', rw=False,
                     name='temp_b')

# AreaDetector Beam Instrumentation
fs1_cam = ProsilicaDetector('XF:23IDA-BI:1{FS:1-Cam:1}')
diag3_cam = ProsilicaDetector('XF:23ID1-BI{Diag:3-Cam:1}')
diag5_cam = ProsilicaDetector('XF:23ID1-BI{Diag:5-Cam:1}')
diag6_cam = ProsilicaDetector('XF:23ID1-BI{Diag:6-Cam:1}')
diag6_cam = ProsilicaDetector('XF:23ID1-BI{Diag:6-Cam:1}')
dif_beam_cam = ProsilicaDetector('XF:23ID1-ES{Dif-Cam:Beam}')

# Princeton CCD camera

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

# SCANS

from ophyd.userapi.scan_api import Scan, AScan, DScan, Count

scan = Scan()
ascan = AScan()
ascan.default_triggers = [sclr_trig]
ascan.default_detectors = [sclr_ch1, sclr_ch2, sclr_ch3, sclr_ch4, sclr_ch5,
                           sclr_ch6]
dscan = DScan()

# Use ct as a count which is a single scan.

ct = Count()
