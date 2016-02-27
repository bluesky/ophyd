import pytest
from ophyd import Device, Component as Cpt, RedundantStaging


class A(Device):
    pass


class B(Device):
    a = Cpt(A, '')


def test_whole_device_always_staged():
    b = B('')
    staged_by_b = b.stage()
    unstaged_by_b = b.unstage()
    staged_by_ba = b.a.stage()
    unstaged_by_ba = b.a.unstage()
    assert set(staged_by_b) == set(staged_by_ba) == set([b, b.a])
    assert set(unstaged_by_b) == set(unstaged_by_ba) == set([b, b.a])

    staged_by_b = b.stage()
    unstaged_by_ba = b.a.unstage()
    assert set(staged_by_b) == set(unstaged_by_ba) == set([b, b.a])


def test_illegal_operations():
    b = B('')
    b.stage()
    with pytest.raises(RedundantStaging):
        b.stage()
    b.unstage()
    b.a.stage()
    with pytest.raises(RedundantStaging):
        b.a.stage()
    with pytest.raises(RedundantStaging):
        b.stage()
    b.unstage()
    b.stage()
    b.unstage()
