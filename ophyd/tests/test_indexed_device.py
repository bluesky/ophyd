import logging
import pytest

from ophyd import (Device, IndexedComponent, Component, FormattedComponent)

from .test_device import FakeSignal

logger = logging.getLogger(__name__)


def test_single_range():
    class MyDev(Device):
        cpt1 = IndexedComponent(
            FakeSignal,
            attr='channel_{:02d}',
            suffix='{:02d}:Test',
            ranges=range(10),
            component_class=Component,
        )

    assert hasattr(MyDev.cpt1, 'channel_00')
    assert hasattr(MyDev.cpt1, 'channel_09')
    assert type(MyDev.cpt1.channel_00) is Component
    assert MyDev.cpt1.channel_00.cls is FakeSignal
    assert MyDev.cpt1.channel_00.suffix == '00:Test'
    dev = MyDev(prefix='PREFIX:', name='dev')

    assert dev.cpt1.channel_00.read_pv == 'PREFIX:00:Test'
    assert dev.cpt1[0] is dev.cpt1.channel_00
    assert len(dev.cpt1) == 10
    assert list(dev.cpt1) == list(range(10))
    assert dev.cpt1[:2] == [dev.cpt1.channel_00,
                            dev.cpt1.channel_01]


def test_formatted_component():
    class MyDev(Device):
        cpt1 = IndexedComponent(
            FakeSignal,
            attr='channel_{:02d}',
            suffix='{{prefix}}{:02d}:Test',
            ranges=range(10),
            component_class=FormattedComponent,
        )

    dev = MyDev(prefix='PREFIX:', name='dev')
    assert dev.cpt1.channel_00.read_pv == 'PREFIX:00:Test'


def test_double_range():
    class MyDev(Device):
        cpt1 = IndexedComponent(
            FakeSignal,
            attr='channel_{:02d}{}',
            suffix='{:02d}{}:Test',
            ranges=[range(10), 'ABCD'],
            component_class=Component,
        )

    assert hasattr(MyDev.cpt1, 'channel_00A')
    assert hasattr(MyDev.cpt1, 'channel_01A')
    assert hasattr(MyDev.cpt1, 'channel_09A')
    assert hasattr(MyDev.cpt1, 'channel_09B')
    assert type(MyDev.cpt1.channel_00A) is Component
    assert MyDev.cpt1.channel_00A.cls is FakeSignal
    assert MyDev.cpt1.channel_00B.suffix == '00B:Test'
    dev = MyDev(prefix='PREFIX:', name='dev')

    assert dev.cpt1.channel_00B.read_pv == 'PREFIX:00B:Test'
    assert dev.cpt1[0]['A'] is dev.cpt1.channel_00A
    assert len(dev.cpt1) == 10
    assert len(dev.cpt1[0]) == 4
    assert list(dev.cpt1) == list(range(10))
    assert list(dev.cpt1[0]) == list('ABCD')


def test_2d_slice():
    class MyDev(Device):
        cpt1 = IndexedComponent(
            FakeSignal,
            attr='channel_{:02d}{}',
            suffix='{:02d}{}:Test',
            ranges=[range(10), 'ABCD'],
            component_class=Component,
        )

    dev = MyDev(prefix='PREFIX:', name='dev')
    assert len(dev.cpt1[:]) == 10 * 4
    assert len(dev.cpt1[:, 'A']) == 10
    assert len(dev.cpt1[:, 'A':'C']) == 30
    assert len(dev.cpt1[:, 'A':]) == 40
    assert len(dev.cpt1[:, :'C']) == 30

    assert dev.cpt1[0, 'A'] is dev.cpt1.channel_00A
    assert dev.cpt1[(0, 'A')] is dev.cpt1.channel_00A

    with pytest.raises(ValueError):
        # slice step must be integer
        dev.cpt1[0:5:'A']

    with pytest.raises(ValueError):
        # too many slices
        dev.cpt1[:, :, :]


def test_3d_slice():
    class MyDev(Device):
        cpt1 = IndexedComponent(
            FakeSignal,
            attr='channel_{:02d}{}{}',
            suffix='{:02d}{}{}:Test',
            ranges=[range(10), 'ABCD', '0123'],
            component_class=Component,
        )

    dev = MyDev(prefix='PREFIX:', name='dev')
    assert len(dev.cpt1[:]) == 10 * 4 * 4
    assert len(dev.cpt1[:, 'A', '0']) == 10 * 1 * 1
    assert len(dev.cpt1[:, 'A':'C', '0']) == 10 * 3 * 1
    assert dev.cpt1[0, 'A', '0'] is dev.cpt1.channel_00A0


def test_string_range():
    class MyDev(Device):
        cpt1 = IndexedComponent(FakeSignal,
                                attr='channel{}',
                                suffix='{}:Test',
                                ranges='ABCD',
                                )

    assert hasattr(MyDev.cpt1, 'channelA')
    assert hasattr(MyDev.cpt1, 'channelB')
    assert hasattr(MyDev.cpt1, 'channelC')
    assert hasattr(MyDev.cpt1, 'channelD')
    assert type(MyDev.cpt1.channelA) is Component
    assert MyDev.cpt1.channelA.cls is FakeSignal
    assert MyDev.cpt1.channelB.suffix == 'B:Test'
    dev = MyDev(prefix='PREFIX:', name='dev')

    assert dev.cpt1.channelB.read_pv == 'PREFIX:B:Test'
    assert dev.cpt1['A'] is dev.cpt1.channelA
    assert len(dev.cpt1) == 4
    assert list(dev.cpt1) == list('ABCD')
