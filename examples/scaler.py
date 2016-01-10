import time

import config
from ophyd import scaler
from ophyd.utils import enum

ScalerMode = enum(ONE_SHOT=0, AUTO_COUNT=1)

def test():
    loggers = ('ophyd.signal',
               'ophyd.scaler',
               )

    config.setup_loggers(loggers)
    logger = config.logger


    sca = scaler.EpicsScaler(config.scalers[0])

    sca.preset_time = 5.2

    logger.info('Counting in One-Shot mode for %f s...' % sca.preset_time)
    sca.start()
    logger.info('Sleeping...')
    time.sleep(3)
    logger.info('Done sleeping. Stopping counter...')
    sca.stop()

    logger.info('Set mode to AutoCount')
    sca.count_mode = ScalerMode.AUTO_COUNT
    sca.start()
    logger.info('Begin auto-counting (aka "background counting")...')
    time.sleep(2)
    logger.info('Set mode to OneShot')
    sca.count_mode = ScalerMode.ONE_SHOT
    time.sleep(1)
    logger.info('Stopping (aborting) auto-counting.')
    sca.stop()

    logger.info('read() all channels in one-shot mode...')
    vals = sca.read()
    logger.info(vals)

    channels = (1,3,5,6)
    logger.info('read() selected channels %s in one-shot mode...' % list(channels))
    vals = sca.read(channels)
    logger.info(vals)

if __name__ == '__main__':
    test()
