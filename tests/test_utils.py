from __future__ import print_function

import os
import logging
import unittest

from ophyd.session import get_session_manager
from ophyd.utils import epics_pvs as epics_utils
from ophyd.utils import errors
from ophyd.utils import decorators

from . import config

server = None
logger = logging.getLogger(__name__)
session = get_session_manager()


def setUpModule():
    pass


def tearDownModule():
    pass


class EpicsUtilTest(unittest.TestCase):
    def test_split(self):
        utils = epics_utils

        self.assertEquals(utils.split_record_field('record.field'), ('record', 'field'))
        self.assertEquals(utils.split_record_field('record.field.invalid'), ('record.field', 'invalid'))
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

    def test_records_from_db(self):
        db_path = os.path.join(config.epics_base, 'db', 'scaler.db')
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


class DecoratorsTest(unittest.TestCase):
    def test_cached(self):
        self.call_count = 0

        @decorators.cached_retval
        def fcn():
            self.call_count += 1
            return 1

        for i in range(10):
            self.assertEquals(fcn(), 1)

        self.assertEquals(self.call_count, 1)


from . import main
is_main = (__name__ == '__main__')
main(is_main)
