import numpy as np

from ophyd.controls import EpicsMotor, EpicsScaler, PVPositioner, EpicsSignal
from ophyd.controls import SimDetector


# slt1_i = EpicsMotor('XF:23ID1-OP{Slt:1-Ax:I}Mtr', name='slt1_i')
# slt1_o = EpicsMotor('XF:23ID1-OP{Slt:1-Ax:O}Mtr', name='slt1_o')
m1 = EpicsMotor('XF:31IDA-OP{Tbl-Ax:X1}Mtr', name='m1')
m2 = EpicsMotor('XF:31IDA-OP{Tbl-Ax:X2}Mtr', name='m2')
m7 = PVPositioner('XF:31IDA-OP{Tbl-Ax:FakeMtr}-SP',
                  readback='XF:31IDA-OP{Tbl-Ax:FakeMtr}-I',
                  act='XF:31IDA-OP{Tbl-Ax:FakeMtr}Cmd:Go-Cmd', act_val=1,
                  stop='XF:31IDA-OP{Tbl-Ax:FakeMtr}Cmd:Stop-Cmd', stop_val=1,
                  done='XF:31IDA-OP{Tbl-Ax:FakeMtr}Sts:Moving-Sts', done_val=1,
                  put_complete=False,
                  name='m7'
                  )
sensor1 = EpicsSignal('XF:31IDA-BI{Dev:1}E-I', rw=False, name='sensor1')
sensor2 = EpicsSignal('XF:31IDA-BI{Dev:2}E-I', rw=False, name='sensor2')
sclr_trig = EpicsSignal('XF:23ID2-ES{Sclr:1}.CNT', rw=True, name='sclr_trig')
sclr_ch1 = EpicsSignal('XF:23ID2-ES{Sclr:1}.S1', rw=False, name='sclr_ch1')
sca = EpicsScaler('XF:23ID2-ES{Sclr:1}', name='sca')

# AreaDetector crud
simdet = SimDetector('XF:31IDA-BI{Cam:Tbl}', name='simdet')
# For now, access as simple 'signals'
simdet_acq = EpicsSignal('XF:31IDA-BI{Cam:Tbl}cam1:Acquire_RBV',
                         write_pv='XF:31IDA-BI{Cam:Tbl}cam1:Acquire',
                         rw=True, name='simdet_acq')
simdet_filename = EpicsSignal('XF:31IDA-BI{Cam:Tbl}TIFF1:FullFileName_RBV',
                              rw=False, string=True, name='simdet_filename')
simdet_intensity = EpicsSignal('XF:31IDA-BI{Cam:Tbl}Stats5:Total_RBV',
                               rw=False, name='simdet_intensity')
