import pytest
from ophyd import Device, Component as Cpt, RedundantStaging
from ophyd.device import Staged


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


class SpecialException(Exception):
    pass


class BrokenStage1(Device):
    def stage(self):
        super().stage()
        raise SpecialException


class BrokenStage2(Device):

    def stage(self):
        raise SpecialException


class BrokenUnstage1(Device):
    def __init__(self, *args, **kwargs):
        self.broken = True
        super().__init__(*args, **kwargs)

    def unstage(self):
        super().unstage()
        if self.broken:
            raise SpecialException


class BrokenUnstage2(Device):
    def __init__(self, *args, **kwargs):
        self.broken = True
        super().__init__(*args, **kwargs)

    def unstage(self):
        if self.broken:
            raise SpecialException
        super().unstage()


class ParentOfBrokenStage1(Device):
    b = Cpt(BrokenStage1, '')


class ParentOfBrokenStage2(Device):
    b = Cpt(BrokenStage2, '')


class ParentOfBrokenUnstage1(Device):
    b = Cpt(BrokenUnstage1, '')


class ParentOfBrokenUnstage2(Device):
    b = Cpt(BrokenUnstage2, '')


class ParentOfBrokenStage1DoubleBroken(ParentOfBrokenStage1):
    def stage(self):
        raise SpecialException


class ParentOfBrokenStage2DoubleBroken(ParentOfBrokenStage2):
    def stage(self):
        raise SpecialException


class ParentOfBrokenUnstage1DoubleBroken(ParentOfBrokenUnstage1):
    def stage(self):
        raise SpecialException


class ParentOfBrokenUnstage2DoubleBroken(ParentOfBrokenUnstage2):
    def stage(self):
        raise SpecialException



def test_interrupted_stage():
    d1 = ParentOfBrokenStage1('')
    d2 = ParentOfBrokenStage2('')
    d1db = ParentOfBrokenStage1DoubleBroken('')
    d2db = ParentOfBrokenStage2DoubleBroken('')
    try:
        d1.stage()
    except SpecialException:
        pass
    assert d1._staged == Staged.no
    assert d1.b._staged == Staged.no
    try:
        d2.stage()
    except SpecialException:
        pass
    assert d2._staged == Staged.no
    assert d1.b._staged == Staged.no
    try:
        d1db.stage()
    except SpecialException:
        pass
    assert d1db._staged == Staged.no
    assert d1db.b._staged == Staged.no
    try:
        d2db.stage()
    except SpecialException:
        pass
    assert d2db._staged == Staged.no
    assert d2db.b._staged == Staged.no


def test_interrupted_unstage():
    d1 = ParentOfBrokenUnstage1('')
    d2 = ParentOfBrokenUnstage2('')
    d3 = ParentOfBrokenUnstage1DoubleBroken('')
    d4 = ParentOfBrokenUnstage2DoubleBroken('')
    d1.stage()
    try:
        d1.unstage()
    except SpecialException:
        pass
    d1.b.broken = False
    d1.unstage()
    assert d1._staged == Staged.no
    assert d1.b._staged == Staged.no
    d2.stage()
    try:
        d2.unstage()
    except SpecialException:
        pass
    d2.b.broken = False
    d2.unstage()
    assert d2._staged == Staged.no
    assert d2.b._staged == Staged.no
    try:
        d3.unstage()
    except SpecialException:
        pass
    d3.b.broken = False
    d3.unstage()
    assert d3._staged == Staged.no
    assert d3.b._staged == Staged.no
    try:
        d4.unstage()
    except SpecialException:
        pass
    d4.b.broken = False
    d4.unstage()
    assert d4._staged == Staged.no
    assert d4.b._staged == Staged.no
