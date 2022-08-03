import logging
import os
import tempfile

import numpy as np
import pytest

from ophyd import Signal
from ophyd.utils import epics_pvs as epics_utils
from ophyd.utils import make_dir_tree, makedirs

logger = logging.getLogger(__name__)


def test_split():
    utils = epics_utils

    assert utils.split_record_field("record.field") == ("record", "field")
    assert utils.split_record_field("record.field.invalid") == (
        "record.field",
        "invalid",
    )
    assert utils.strip_field("record.field") == "record"
    assert utils.strip_field("record.field.invalid") == "record.field"
    assert utils.record_field("record", "field") == "record.FIELD"


def test_waveform_to_string():
    s = "abcdefg"
    asc = [ord(c) for c in s]
    assert epics_utils.waveform_to_string(asc) == s

    asc = [ord(c) for c in s] + [0, 0, 0]
    assert epics_utils.waveform_to_string(asc) == s


def test_records_from_db():
    # db_dir = os.path.join(config.epics_base, 'db')

    # if os.path.exists(db_dir):
    #     # fall back on the db file included with the tests
    db_dir = os.path.dirname(__file__)
    db_path = os.path.join(db_dir, "scaler.db")
    records = epics_utils.records_from_db(db_path)
    assert ("bo", "$(P)$(S)_calcEnable") in records


@pytest.mark.parametrize(
    "value, dtype, shape",
    [
        [1, "integer", []],
        [1.0, "number", []],
        [1e-3, "number", []],
        ["foo", "string", []],
        [np.array([1, 2, 3]), "array", [3]],
        [np.array([[1, 2], [3, 4]]), "array", [2, 2]],
        [(1, 2, 3), "array", [3]],
        [[1, 2, 3], "array", [3]],
        [[], "array", [0]],
    ],
)
def test_data_type_and_shape(value, dtype, shape):
    utils = epics_utils
    assert utils.data_type(value) == dtype
    assert utils.data_shape(value) == shape


@pytest.mark.parametrize("value", [dict()])
def test_invalid_data_type(value):
    utils = epics_utils
    with pytest.raises(ValueError):
        utils.data_type(value)


def assert_OD_equal_ignore_ts(a, b):
    for (k1, v1), (k2, v2) in zip(a.items(), b.items()):
        assert (k1 == k2) and (v1["value"] == v2["value"])


def assert_file_mode(path, expected):
    assert (os.stat(path).st_mode & 0o777) == expected


def test_makedirs():
    with tempfile.TemporaryDirectory() as tempdir:
        create_dir = os.path.join(tempdir, "a")
        makedirs(create_dir, mode=0o767, mode_base=tempdir)
        assert_file_mode(create_dir, 0o767)


def test_make_dir_tree():
    with tempfile.TemporaryDirectory() as tempdir:
        paths = make_dir_tree(2016, base_path=tempdir, mode=0o777)
        assert len(paths) == 366

        for path in paths:
            assert_file_mode(path, 0o777)

        assert os.path.join(tempdir, "2016", "03", "04") in paths
        assert os.path.join(tempdir, "2016", "02", "29") in paths


def test_valid_pvname():
    with pytest.raises(epics_utils.BadPVName):
        epics_utils.validate_pv_name("this.will.fail")


def test_array_into_softsignal():
    data = np.array([1, 2, 3])
    s = Signal(name="np.array")
    s.set(data).wait()
    assert np.all(s.get() == data)


def test_none_signal():
    import itertools

    class CycleSignal(Signal):
        def __init__(self, *args, value_cycle, **kwargs):
            super().__init__(*args, **kwargs)
            self._value_cycle = itertools.cycle(value_cycle)

        def get(self):
            return next(self._value_cycle)

    cs = CycleSignal(
        name="cycle", value_cycle=[0, 1, 2, None, 4], tolerance=0.01, rtolerance=0.1
    )

    cs.set(4).wait()


def test_set_signal_to_None():
    s = Signal(value="0", name="bob")
    s.set(None).wait(timeout=1)
