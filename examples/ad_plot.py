'''An example of using :class:`AreaDetector`'''

import config
from ophyd import (AreaDetector, ImagePlugin,
                   Component as Cpt)
import matplotlib.pyplot as plt

logger = config.logger

det1 = config.sim_areadetector[0]
det1_prefix = det1['prefix']
det1_cam = det1['cam']

# Instantiate a plugin directly
img1 = ImagePlugin(det1_prefix + 'image1:')
img = img1.image

plt.figure()
plt.imshow(img, cmap=plt.cm.gray)
plt.title('Plugin instantiated directly - img1.image')

logger.debug('Image shape=%s dtype=%s', img.shape, img.dtype)
logger.debug('Image pixels=%s dtype=%s', img1.array_pixels, img1.data_type.value)

# Or reference that plugin from the detector instance
class MyDetector(AreaDetector):
    image1 = Cpt(ImagePlugin, 'image1:')


ad = MyDetector(det1_prefix)

img = ad.image1.image
plt.figure()
plt.title('Plugin from AreaDetector - ad.image1.image')
plt.imshow(img, cmap=plt.cm.gray)
plt.show()
