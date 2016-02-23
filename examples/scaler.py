import time

import config
from ophyd import scaler
from ophyd.utils import enum

ScalerMode = enum(ONE_SHOT=0, AUTO_COUNT=1)

loggers = ('ophyd.signal',
           'ophyd.scaler',
           )

config.setup_loggers(loggers)
logger = config.logger


sca = scaler.EpicsScaler(config.scalers[0])

sca.preset_time.put(5.2, wait=True)

logger.info('Counting in One-Shot mode for %f s...', sca.preset_time.get())
sca.trigger()
logger.info('Sleeping...')
time.sleep(3)
logger.info('Done sleeping. Stopping counter...')
sca.count.put(0)

logger.info('Set mode to AutoCount')
sca.count_mode.put(ScalerMode.AUTO_COUNT, wait=True)
sca.trigger()
logger.info('Begin auto-counting (aka "background counting")...')
time.sleep(2)
logger.info('Set mode to OneShot')
sca.count_mode.put(ScalerMode.ONE_SHOT, wait=True)
time.sleep(1)
logger.info('Stopping (aborting) auto-counting.')
sca.count.put(0)

logger.info('read() all channels in one-shot mode...')
vals = sca.read()
logger.info(vals)

logger.info('sca.channels.get() shows: %s', sca.channels.get())
