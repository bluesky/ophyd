from __future__ import print_function

import os
import logging
import unittest

import epics

from ophyd.utils import epics_pvs as epics_utils
from ophyd.utils import errors

from . import config

logger = logging.getLogger(__name__)


def setUpModule():
    pass


def tearDownModule():
    pass


class EpicsUtilTest(unittest.TestCase):
    def test_split(self):
        utils = epics_utils

        self.assertEquals(utils.split_record_field('record.field'),
                          ('record', 'field'))
        self.assertEquals(utils.split_record_field('record.field.invalid'),
                          ('record.field', 'invalid'))
        self.assertEquals(utils.strip_field('record.field'), 'record')
        self.assertEquals(utils.strip_field('record.field.invalid'), 'record.field')

        self.assertEquals(utils.record_field('record', 'field'), 'record.FIELD')

    def test_alarm(self):
        utils = epics_utils

        rec = config.motor_recs[0]
        try:
            utils.check_alarm(rec)
        except Exception:
            pass

    def test_waveform_to_string(self):
        s = 'abcdefg'
        asc = [ord(c) for c in s]
        self.assertEquals(epics_utils.waveform_to_string(asc), s)

        asc = [ord(c) for c in s] + [0, 0, 0]
        self.assertEquals(epics_utils.waveform_to_string(asc), s)

    def test_pv_form(self):
        self.assertIn(epics_utils.get_pv_form(), ('native', 'time'))
        version = epics.__version__

        try:
            versions = ('3.2.3', '3.2.3rc1', '3.2.3-gABCD', 'unknown')
            for version in versions:
                epics.__version__ = version
                self.assertIn(epics_utils.get_pv_form(), ('native', 'time'))
        finally:
            epics.__version__ = version

    def test_records_from_db(self):
        # db_dir = os.path.join(config.epics_base, 'db')

        # if os.path.exists(db_dir):
        #     # fall back on the db file included with the tests
        db_dir = os.path.dirname(__file__)
        db_path = os.path.join(db_dir, 'scaler.db')
        records = epics_utils.records_from_db(db_path)
        self.assertIn(('bo', '$(P)$(S)_calcEnable'), records)


class ErrorsTest(unittest.TestCase):
    def test_alarm(self):
        self.assertIs(errors.get_alarm_class(errors.MinorAlarmError.severity),
                      errors.MinorAlarmError)
        self.assertIs(errors.get_alarm_class(errors.MajorAlarmError.severity),
                      errors.MajorAlarmError)

        errors.MajorAlarmError('', alarm='NO_ALARM')
        errors.MajorAlarmError('', alarm='TIMEOUT_ALARM')
        errors.MajorAlarmError('', alarm=0)


def assert_OD_equal_ignore_ts(a, b):
    for (k1, v1), (k2, v2) in zip(a.items(), b.items()):
        assert (k1 == k2) and (v1['value'] == v2['value'])


from . import main
is_main = (__name__ == '__main__')
main(is_main)
