import logging
import unittest
from copy import copy
from unittest import mock
from unittest.mock import Mock

from ophyd import (SoftPositioner, )

logger = logging.getLogger(__name__)


def test_positioner_settle():
    p = SoftPositioner(name='test', egu='egu', limits=(-10, 10),
                       settle_time=0.1, timeout=10.0)
    assert p.settle_time == 0.1
    st = p.move(0.0, wait=False)
    assert st.settle_time == 0.1
    assert st.timeout == 10.0

    assert p.timeout == 10.0
    p.timeout = 20.0
    assert p.timeout == 20.0


def test_positioner():
    p = SoftPositioner(name='test', egu='egu', limits=(-10, 10))

    assert p.connected == True

    position_callback = Mock()
    started_motion_callback = Mock()
    finished_motion_callback = Mock()

    assert p.egu == 'egu'
    assert p.limits == (-10, 10)

    p.subscribe(position_callback, event_type=p.SUB_READBACK)
    p.subscribe(started_motion_callback, event_type=p.SUB_START)
    p.subscribe(finished_motion_callback, event_type=p.SUB_DONE)

    target_pos = 0
    p.move(target_pos, timeout=2, wait=True)
    assert not p.moving
    assert p.position == target_pos

    position_callback.assert_called_once_with(obj=p, value=target_pos,
                                              sub_type=p.SUB_READBACK,
                                              timestamp=mock.ANY)
    started_motion_callback.assert_called_once_with(obj=p,
                                                    sub_type=p.SUB_START,
                                                    timestamp=mock.ANY)
    finished_motion_callback.assert_called_once_with(obj=p,
                                                     sub_type=p.SUB_DONE,
                                                     value=None,
                                                     timestamp=mock.ANY)
    position_callback.reset_mock()
    started_motion_callback.reset_mock()
    finished_motion_callback.reset_mock()

    target_pos = 1
    res = p.move(target_pos, wait=False)

    assert res.done
    assert res.error == 0
    assert res.elapsed > 0
    assert p.position == target_pos
    position_callback.assert_called_once_with(obj=p, value=target_pos,
                                              sub_type=p.SUB_READBACK,
                                              timestamp=unittest.mock.ANY)
    started_motion_callback.assert_called_once_with(obj=p,
                                                    sub_type=p.SUB_START,
                                                    timestamp=unittest.mock.ANY)
    finished_motion_callback.assert_called_once_with(obj=p,
                                                     sub_type=p.SUB_DONE,
                                                     value=None,
                                                     timestamp=unittest.mock.ANY)

    repr(res)
    str(res)
    repr(p)
    str(p)

    p.stop()

    p.position

    pc = copy(p)
    assert pc.egu == p.egu
    assert pc.limits == p.limits
