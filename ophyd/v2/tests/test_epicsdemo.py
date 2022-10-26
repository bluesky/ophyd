import asyncio
from typing import Dict, cast
from unittest.mock import Mock, call, patch

import pytest
from bluesky.protocols import Reading

from ophyd.v2 import epicsdemo
from ophyd.v2.core import DeviceCollector
from ophyd.v2.epics import ChannelSim

# Long enough for multiple asyncio event loop cycles to run so
# all the tasks have a chance to run
A_BIT = 0.001


@pytest.fixture
async def sim_mover():
    async with DeviceCollector(sim=True):
        sim_mover = epicsdemo.Mover("BLxxI-MO-TABLE-01:X")
        # Signals connected here

    assert sim_mover.name == "sim_mover"
    units = cast(ChannelSim, sim_mover.units.read_channel)
    units.set_value("mm")
    precision = cast(ChannelSim, sim_mover.precision.read_channel)
    precision.set_value(3)
    velocity = cast(ChannelSim, sim_mover.velocity.read_channel)
    velocity.set_value(1)
    yield sim_mover


async def test_mover_moving_well(sim_mover: epicsdemo.Mover) -> None:
    setpoint = cast(ChannelSim, sim_mover.setpoint.write_channel)
    readback = cast(ChannelSim, sim_mover.readback.read_channel)
    s = sim_mover.set(0.55)
    watcher = Mock()
    s.watch(watcher)
    done = Mock()
    s.add_callback(done)
    await asyncio.sleep(A_BIT)
    assert watcher.call_count == 1
    assert watcher.call_args == call(
        name="sim_mover",
        current=0.0,
        initial=0.0,
        target=0.55,
        unit="mm",
        precision=3,
        time_elapsed=pytest.approx(0.0, abs=0.05),
    )
    watcher.reset_mock()
    assert setpoint._value == 0.55
    assert not s.done
    done.assert_not_called()
    await asyncio.sleep(0.1)
    readback.set_value(0.1)
    await asyncio.sleep(A_BIT)
    assert watcher.call_count == 1
    assert watcher.call_args == call(
        name="sim_mover",
        current=0.1,
        initial=0.0,
        target=0.55,
        unit="mm",
        precision=3,
        time_elapsed=pytest.approx(0.1, abs=0.05),
    )
    readback.set_value(0.5499999)
    await asyncio.sleep(A_BIT)
    assert s.done
    assert s.success
    done.assert_called_once_with(s)
    done2 = Mock()
    s.add_callback(done2)
    done2.assert_called_once_with(s)


async def test_mover_stopped(sim_mover: epicsdemo.Mover):
    stop = cast(ChannelSim, sim_mover.stop_.write_channel)
    await sim_mover.stop()
    assert stop._value == 1


async def test_read_mover(sim_mover: epicsdemo.Mover):
    sim_mover.stage()
    assert (await sim_mover.read())["sim_mover"]["value"] == 0.0
    assert (await sim_mover.describe())["sim_mover"][
        "source"
    ] == "sim://BLxxI-MO-TABLE-01:XReadback"
    assert (await sim_mover.read_configuration())["sim_mover-velocity"]["value"] == 1
    assert (await sim_mover.describe_configuration())["sim_mover-units"]["shape"] == []
    readback = cast(ChannelSim, sim_mover.readback.read_channel)
    readback.set_value(0.5)
    assert (await sim_mover.read())["sim_mover"]["value"] == 0.5
    sim_mover.unstage()
    # Check we can still read and describe when not staged
    readback.set_value(0.1)
    assert (await sim_mover.read())["sim_mover"]["value"] == 0.1
    assert await sim_mover.describe()


async def test_set_velocity(sim_mover: epicsdemo.Mover) -> None:
    v = sim_mover.velocity
    assert (await v.describe())["sim_mover-velocity"][
        "source"
    ] == "sim://BLxxI-MO-TABLE-01:XVelocity"
    q: asyncio.Queue[Dict[str, Reading]] = asyncio.Queue()
    v.subscribe(q.put_nowait)
    assert (await q.get())["sim_mover-velocity"]["value"] == 1.0
    await v.set(2.0)
    assert (await q.get())["sim_mover-velocity"]["value"] == 2.0
    v.clear_sub(q.put_nowait)
    await v.set(3.0)
    assert (await v.read())["sim_mover-velocity"]["value"] == 3.0
    assert q.empty()


async def test_sensor_disconncted():
    with patch("ophyd.v2.core.logging") as mock_logging:
        async with DeviceCollector(timeout=0.1):
            s = epicsdemo.Sensor("ca://PRE:", name="sensor")
        mock_logging.error.assert_called_once_with(
            """\
1 Devices did not connect:
  s: NotConnected
    value: ca://PRE:Value
    mode: ca://PRE:Mode"""
        )
    assert s.name == "sensor"


async def test_assembly_renaming() -> None:
    thing = epicsdemo.SampleStage("PRE")
    await thing.connect(sim=True)
    assert thing.x.name == ""
    assert thing.x.velocity.name == ""
    assert thing.x.stop_.name == ""
    await thing.x.velocity.set(456)
    assert await (thing.x.velocity.get_value()) == 456
    thing.set_name("foo")
    assert thing.x.name == "foo-x"
    assert thing.x.velocity.name == "foo-x-velocity"
    assert thing.x.stop_.name == "foo-x-stop"
