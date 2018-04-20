import pytest
import os
import logging
import numpy as np
import tempfile

from ophyd.utils import epics_pvs as epics_utils
from ophyd.utils import (make_dir_tree, makedirs)
from .conftest import AssertTools


logger = logging.getLogger(__name__)


class TestEpicsUtil(AssertTools):
    def test_split(self):
        utils = epics_utils

        assert utils.split_record_field('record.field') == ('record', 'field')
        self.assertEquals(utils.split_record_field('record.field.invalid'),
                          ('record.field', 'invalid'))
        self.assertEquals(utils.strip_field('record.field'), 'record')
        self.assertEquals(utils.strip_field('record.field.invalid'), 'record.field')

        self.assertEquals(utils.record_field('record', 'field'), 'record.FIELD')

    def test_waveform_to_string(self):
        s = 'abcdefg'
        asc = [ord(c) for c in s]
        self.assertEquals(epics_utils.waveform_to_string(asc), s)

        asc = [ord(c) for c in s] + [0, 0, 0]
        self.assertEquals(epics_utils.waveform_to_string(asc), s)

    def test_pv_form(self):
        from ophyd import get_cl
        o_ps = pytest.importorskip('ophyd._pyepics_shim')
        cl = get_cl()
        self.assertIn(cl.pv_form, ('native', 'time'))
        versions = ('3.2.3', '3.2.3rc1', '3.2.3-gABCD', 'unknown')
        for version in versions:
            self.assertIn(o_ps.get_pv_form(version), ('native', 'time'))

    def test_records_from_db(self):
        # db_dir = os.path.join(config.epics_base, 'db')

        # if os.path.exists(db_dir):
        #     # fall back on the db file included with the tests
        db_dir = os.path.dirname(__file__)
        db_path = os.path.join(db_dir, 'scaler.db')
        records = epics_utils.records_from_db(db_path)
        self.assertIn(('bo', '$(P)$(S)_calcEnable'), records)

    def test_data_type(self):
        utils = epics_utils

        self.assertEquals(utils.data_type(1), 'integer')
        self.assertNotEqual(utils.data_type(2), 'number')
        self.assertEquals(utils.data_type(1e-3), 'number')
        self.assertEquals(utils.data_type(2.718), 'number')
        self.assertEquals(utils.data_type('foo'), 'string')
        self.assertEquals(utils.data_type(np.array([1,2,3])), 'array')

        self.assertRaises(ValueError, utils.data_type, [1,2,3])
        self.assertRaises(ValueError, utils.data_type, dict())

    def test_data_shape(self):
        utils = epics_utils

        self.assertEquals(utils.data_shape(1), list())
        self.assertEquals(utils.data_shape('foo'), list())
        self.assertEquals(utils.data_shape(np.array([1,2,3])), [3, ])
        self.assertEquals(utils.data_shape(np.array([[1, 2], [3, 4]])), [2, 2])

        self.assertRaises(ValueError, utils.data_shape, list())


def assert_OD_equal_ignore_ts(a, b):
    for (k1, v1), (k2, v2) in zip(a.items(), b.items()):
        assert (k1 == k2) and (v1['value'] == v2['value'])


def assert_file_mode(path, expected):
    assert (os.stat(path).st_mode & 0o777) == expected


def test_makedirs():
    with tempfile.TemporaryDirectory() as tempdir:
        create_dir = os.path.join(tempdir, 'a')
        makedirs(create_dir, mode=0o767, mode_base=tempdir)
        assert_file_mode(create_dir, 0o767)


def test_make_dir_tree():
    with tempfile.TemporaryDirectory() as tempdir:
        paths = make_dir_tree(2016, base_path=tempdir, mode=0o777)
        assert len(paths) == 366

        for path in paths:
            assert_file_mode(path, 0o777)

        assert os.path.join(tempdir, '2016', '03', '04') in paths
        assert os.path.join(tempdir, '2016', '02', '29') in paths


def test_valid_pvname():
    with pytest.raises(epics_utils.BadPVName):
        epics_utils.validate_pv_name('this.will.fail')
