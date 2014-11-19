import time

import config
from ophyd.controls import scaler


def enum(**enums):
    return type('Enum', (object,), enums)

ScalerMode = enum(ONE_SHOT=0, AUTO_COUNT=1)


sca = scaler.Scaler('XF:23ID2-ES{Sclr:1}')
sca.start()
print 'Sleeping...'
time.sleep(2)
print 'Done sleeping.'
sca.stop()
#print 'Set mode to AutoCount'
#sca.set_mode(ScalerMode.AUTO_COUNT)
#time.sleep(0.5)
#print 'Set mode to OneShot'
#sca.set_mode(ScalerMode.ONE_SHOT)
print 'Trigger read() method...'
vals = sca.read()
print vals
