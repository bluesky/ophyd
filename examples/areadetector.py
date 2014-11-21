#!/usr/bin/env python2.7
'''
An example of using :class:`AreaDetector`
'''
from __future__ import print_function
import config
from ophyd.controls import (areadetector, AreaDetector, EpicsSignal)


def test():
    def log_all(obj):
        port_name = obj.port_name.value

        for attr in dir(obj):
            if attr.startswith('__'):
                continue

            val = getattr(obj, attr)
            name = "%s.%s" % (port_name, attr)
            if isinstance(val, EpicsSignal):
                logger.debug('(epics) %s %s=%s' % (name, val.read_pvname, val.value))

    loggers = ('ophyd.controls.areadetector',
               'ophyd.session',
               )

    config.setup_loggers(loggers)
    logger = config.logger

    det1 = config.sim_areadetector[0]
    det1_prefix = det1['prefix']
    det1_cam = det1['cam']
    for type_, suffix_list in config.ad_plugins.items():
        if type_ == 'overlay':
            continue

        for suffix in suffix_list:
            plugin = areadetector.get_areadetector_plugin(det1_prefix, suffix)
            # Note: the below will print out every EpicsSignal attribute for
            # every plugin, image, etc. and will take a while:
            if 0:
                log_all(plugin)

    det = AreaDetector(det1_prefix, cam=det1_cam)
    # det.acquire = 1
    logger.debug('acquire = %d' % det.acquire.value)

    img1 = areadetector.ImagePlugin(det1_prefix, suffix='image1:')
    log_all(img1)

    logger.debug('nd_array_port = %s' % img1.nd_array_port.value)

    # ensure EPICS_CA_MAX_ARRAY_BYTES set properly...
    if 1:
        img1.array_data.value

    proc1 = areadetector.ProcessPlugin(det1_prefix, suffix='Proc1:')

    logger.debug('fc=%s' % proc1.fc)
    proc1.fc = [1, 2, 3, 4]
    logger.debug('fc=%s' % proc1.fc)
    proc1.fc = [1, -1, 0, 1]
    logger.debug('fc=%s' % proc1.fc)


if __name__ == '__main__':
    test()
