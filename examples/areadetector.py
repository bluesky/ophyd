#!/usr/bin/env python2.7
'''
An example of using :class:`AreaDetector`
'''
from __future__ import print_function

import sys
import time

import config

from ophyd.controls import (areadetector, AreaDetector, EpicsSignal)


def test():
    def dump_pvnames(obj, f=sys.stderr):
        for attr, signal in sorted(obj.signals.items()):
            if not isinstance(signal, EpicsSignal):
                continue

            if signal.read_pvname:
                print(signal.read_pvname, file=f)

            if signal.write_pvname != signal.read_pvname and signal.write_pvname:
                print(signal.write_pvname, file=f)

    def log_values(obj):
        port_name = obj.port_name.value

        for attr, signal in sorted(obj.signals.items()):
            name = "%s.%s" % (port_name, attr)
            logger.debug('(epics) %s %s=%s' % (name, signal.read_pvname, signal.value))

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
                log_values(plugin)

            if 0:
                dump_pvnames(plugin)


            if type_ != 'file':
                break

    det = AreaDetector(det1_prefix, cam=det1_cam)
    log_values(det)
    # det.acquire = 1
    logger.debug('acquire = %d' % det.acquire.value)

    img1 = areadetector.ImagePlugin(det1_prefix, suffix='image1:')
    # log_all(img1)

    logger.debug('nd_array_port = %s' % img1.nd_array_port.value)

    # ensure EPICS_CA_MAX_ARRAY_BYTES set properly...
    if 1:
        img1.array_data.value

    proc1 = areadetector.ProcessPlugin(det1_prefix, suffix='Proc1:')

    # Signal group allows setting value as a list:
    logger.debug('fc=%s' % proc1.fc.value)
    proc1.fc = [1, 2, 3, 4]
    time.sleep(0.1)

    logger.debug('fc=%s from %s' % (proc1.fc.value, proc1.fc.read_pvname))

    # But they can be accessed individually as well
    logger.debug('(fc1=%s, fc2=%s, fc3=%s, fc4=%s)' % (proc1._fc1.value,
                                                       proc1._fc2.value,
                                                       proc1._fc3.value,
                                                       proc1._fc4.value))

    # Reset them to the default values
    proc1.fc = [1, -1, 0, 1]
    logger.debug('fc=%s' % proc1.fc.value)


if __name__ == '__main__':
    test()
