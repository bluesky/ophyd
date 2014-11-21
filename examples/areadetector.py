#!/usr/bin/env python2.7
'''
An example of using :class:`AreaDetector`
'''

import config
from ophyd.controls import areadetector
from ophyd.controls import AreaDetector


def test():
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
            areadetector.get_areadetector_plugin(det1_prefix, suffix)

    det = AreaDetector(det1_prefix)
    # det.acquire = 1
    logger.debug('acquire = %d' % det.acquire.value)

    img1 = areadetector.ImagePlugin(det1_prefix, suffix='image1:')
    logger.debug('nd_array_port = %s' % img1.nd_array_port.value)

    # ensure EPICS_CA_MAX_ARRAY_BYTES set properly...
    if 1:
        img1.array_data.value

if __name__ == '__main__':
    test()
