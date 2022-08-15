import logging
import time
from copy import copy
from unittest import mock
from unittest.mock import Mock

import pytest

from ophyd.mixins import EpicsSignalPositioner
from ophyd.status import wait
from ophyd.utils import record_field

from .config import motor_recs

logger = logging.getLogger(__name__)


def setUpModule():
    logging.getLogger("ophyd.mixins").setLevel(logging.DEBUG)


def tearDownModule():
    logger.debug("Cleaning up")


@pytest.mark.motorsim
def test_epics_signal_positioner():
    readback = record_field(motor_recs[0], "RBV")
    setpoint = record_field(motor_recs[0], "VAL")
    p = EpicsSignalPositioner(
        readback, write_pv=setpoint, name="p", egu="egu", tolerance=0.005
    )
    p.wait_for_connection()
    assert p.connected

    position_callback = Mock()
    started_motion_callback = Mock()
    finished_motion_callback = Mock()
    moved_cb = Mock()
    assert p.egu == "egu"

    p.subscribe(position_callback, event_type=p.SUB_READBACK)
    p.subscribe(started_motion_callback, event_type=p.SUB_START)
    p.subscribe(finished_motion_callback, event_type=p.SUB_DONE)

    start_pos = p.position
    target_pos = start_pos - 1.5
    p.move(target_pos, wait=True, moved_cb=moved_cb)
    logger.debug(str(p))
    assert not p.moving
    assert abs(p.position - target_pos) <= p.tolerance
    time.sleep(0.5)
    moved_cb.assert_called_with(obj=p)
    position_callback.assert_called_with(
        obj=p, value=mock.ANY, sub_type=p.SUB_READBACK, timestamp=mock.ANY
    )
    started_motion_callback.assert_called_once_with(
        obj=p, sub_type=p.SUB_START, timestamp=mock.ANY
    )
    finished_motion_callback.assert_called_once_with(
        obj=p, sub_type=p.SUB_DONE, value=None, timestamp=mock.ANY
    )

    st = p.set(start_pos)

    wait(st)

    assert st.done
    assert st.error == 0
    assert st.elapsed > 0
    assert abs(p.position - start_pos) <= p.tolerance

    repr(p)
    str(p)

    p.stop()

    p.position

    pc = copy(p)
    assert pc.egu == p.egu
    assert pc.limits == p.limits
