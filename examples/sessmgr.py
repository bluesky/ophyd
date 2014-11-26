import config

from ophyd.controls import EpicsMotor, EpicsScaler, PVPositioner
from dumb_scan import simple_scan


m1 = EpicsMotor(config.motor_recs[0], name='m1')
m2 = EpicsMotor(config.motor_recs[1], name='m2')
#m7 = PVPositioner(config.fake_motors[0], name='m7')
sca = EpicsScaler(config.scalers[0], name='sca')
