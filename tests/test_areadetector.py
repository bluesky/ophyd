from __future__ import print_function

import logging
import unittest

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

import epics

from ophyd.controls import (SimDetector, get_areadetector_plugin)
from ophyd.controls.areadetector.util import stub_templates

logger = logging.getLogger(__name__)


def setUpModule():
    pass


def tearDownModule():
    if __name__ == '__main__':
        epics.ca.destroy_context()


class ADTest(unittest.TestCase):
    prefix = 'XF:31IDA-BI{Cam:Tbl}'
    ad_path = '/epics/support/areaDetector/1-9-1/ADApp/Db/'

    def test_stubbing(self):
        try:
            for line in stub_templates(self.ad_path):
                logger.debug('Stub line: %s', line)
        except OSError:
            # self.fail('AreaDetector db path needed to run test')
            pass

    def test_detector(self):
        det = SimDetector(self.prefix)

        det.find_signal('a', f=StringIO())
        det.find_signal('a', use_re=True, f=StringIO())
        det.find_signal('a', case_sensitive=True, f=StringIO())
        det.find_signal('a', use_re=True, case_sensitive=True, f=StringIO())
        det.signal_names
        det.report

        det.image_mode.put('Single')
        # plugins don't live on detectors now:
        # det.image1.enable.put('Enable')
        det.array_callbacks.put('Enable')

        det.get()
        det.read()

        # values = tuple(det.gain_xy.get())
        det.gain_xy.put(det.gain_xy.get(), wait=True)

        # fail when only specifying x
        self.assertRaises(ValueError, det.gain_xy.put, (0.0, ), wait=True)

        det.describe()
        det.report

    def test_tiff_plugin(self):
        # det = AreaDetector(self.prefix)
        plugin = get_areadetector_plugin(self.prefix + 'TIFF1:')

        plugin.file_template.put('%s%s_%3.3d.tif')

        self.assertRaises(ValueError, get_areadetector_plugin,
                          self.prefix + 'foobar:')


from . import main
is_main = (__name__ == '__main__')
main(is_main)
