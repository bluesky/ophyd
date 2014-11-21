#!/usr/bin/env python2.7
'''
An example of using :class:`AreaDetector`
'''
from __future__ import print_function
import config
from ophyd.controls.areadetector import (AreaDetector, ImagePlugin)

import matplotlib.pyplot as plt


def test():
    loggers = ('ophyd.controls.areadetector',
               'ophyd.session',
               )

    config.setup_loggers(loggers)
    logger = config.logger

    det1 = config.sim_areadetector[0]
    det1_prefix = det1['prefix']
    det1_cam = det1['cam']

    # Instantiate a plugin directly
    img1 = ImagePlugin(det1_prefix, suffix='image1:')
    img = img1.image
    plt.imshow(img, cmap=plt.cm.gray)

    logger.debug('Image shape=%s dtype=%s' % (img.shape, img.dtype))
    logger.debug('Image pixels=%s dtype=%s' % (img1.array_pixels, img1.data_type.value))
    plt.show()

    # Or reference that plugin from the detector instance
    ad = AreaDetector(det1_prefix, cam=det1_cam,
                      images=['image1:', ])
    img = ad.images[0].image
    plt.imshow(img, cmap=plt.cm.gray)
    plt.show()


if __name__ == '__main__':
    test()
