import pytest

from ..areadetector.paths import EpicsPathSignal


def test_path_semantics_exception():
    with pytest.raises(ValueError):
        EpicsPathSignal('TEST', path_semantics='not_a_thing')
