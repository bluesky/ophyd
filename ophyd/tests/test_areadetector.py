from __future__ import print_function

import logging
import unittest

from StringIO import StringIO

import epics

from ophyd.controls.areadetector.detectors import (AreaDetector, stub_templates)
from ophyd.controls.areadetector.plugins import get_areadetector_plugin
from ophyd.session import get_session_manager

server = None
logger = logging.getLogger(__name__)
session = get_session_manager()


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
            stub_templates(self.ad_path, f=StringIO())
        except OSError:
            self.fail('AreaDetector db path needed to run test')

    def test_detector(self):
        det = AreaDetector(self.prefix)

        det.find_signal('a', f=StringIO())
        det.find_signal('a', use_re=True, f=StringIO())
        det.find_signal('a', case_sensitive=True, f=StringIO())
        det.find_signal('a', use_re=True, case_sensitive=True, f=StringIO())
        det.signals
        det.report

        det.image_mode = 'Single'
        det.image1.enable = 'Enable'
        det.array_callbacks = 'Enable'

        try:
            det.read()
        except Exception as ex:
            self.fail('AreaDetector not setup for acquiring: %s' % ex)

        AreaDetector._update_docstrings()
        AreaDetector._all_adsignals()

    def test_plugin(self):
        det = AreaDetector(self.prefix)
        plugin = get_areadetector_plugin(self.prefix, suffix='TIFF1:',
                                         detector=det)

        plugin.file_template = '%s%s_%3.3d.tif'
        try:
            plugin.get_filenames(check=True)
        except (RuntimeError, ValueError):
            pass

        try:
            get_areadetector_plugin(self.prefix, suffix='foobar:')
        except ValueError:
            pass
        else:
            self.fail('Should have failed on invalid pv')


from . import main
is_main = (__name__ == '__main__')
main(is_main)
