'''An example of using :class:`AreaDetector`'''

import time

import config

from ophyd import SimDetector
from ophyd import (ImagePlugin, TIFFPlugin, ProcessPlugin, OverlayPlugin,
                   Component as Cpt)


logger = config.logger


class MyDetector(SimDetector):
    image1 = Cpt(ImagePlugin, 'image1:')
    tiff1 = Cpt(TIFFPlugin, 'TIFF1:')
    proc1 = Cpt(ProcessPlugin, 'Proc1:')
    over1 = Cpt(OverlayPlugin, 'Over1:')


det1_prefix = 'XF:31IDA-BI{Cam:Tbl}'
det = MyDetector(det1_prefix)
det.cam.image_mode.put('Single', wait=True)
det.image1.enable.put('Enable', wait=True)
det.cam.array_callbacks.put('Enable', wait=True)

# ensure EPICS_CA_MAX_ARRAY_BYTES set properly...
img = det.image1.image
print('Image: {}'.format(img))

det.tiff1.file_template.put('%s%s_%3.3d.tif', wait=True)
logger.debug('template value=%s', det.tiff1.file_template.get())
logger.debug('full filename=%s', det.tiff1.full_file_name.get())
logger.debug('acquire = %d', det.cam.acquire.get())

img1 = det.image1
logger.debug('nd_array_port = %s', img1.nd_array_port.get())

# Signal group allows setting value as a list:
proc1 = det.proc1
logger.debug('fc=%s', proc1.fc.get())
FcTuple = proc1.fc.get_device_tuple()
proc1.fc.put(FcTuple(fc1=1, fc2=2, fc3=3, fc4=4),
             wait=True)
time.sleep(0.1)

logger.debug('fc=%s', proc1.fc.get())

# But they can be accessed individually as well
logger.debug('(fc1=%s, fc2=%s, fc3=%s, fc4=%s)', proc1.fc.fc1.get(),
             proc1.fc.fc2.get(), proc1.fc.fc3.get(), proc1.fc.fc4.get())

# Reset them to the default values
proc1.fc.put(FcTuple(1, -1, 0, 1), wait=True)
time.sleep(0.1)
logger.debug('reset to fc=%s', proc1.fc.get())

# if using IPython, try the following:
# In [0]: run areadetector.py
#
# In [1]: help(proc1)

logger.debug('Overlay1:1 blue=%s', det.over1.overlay_1.blue.get())
