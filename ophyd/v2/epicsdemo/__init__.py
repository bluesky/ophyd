"""Demo EPICS Devices for the tutorial"""

import asyncio
import time
from enum import Enum
from typing import Callable, List

import numpy as np
from bluesky.protocols import Movable, Stoppable

from ophyd.v2.core import (
    AsyncStatus,
    Device,
    HasReadableSignals,
    connect_children,
    observe_value,
)
from ophyd.v2.epics import EpicsSignalR, EpicsSignalRW, EpicsSignalX


class Energy(Enum):
    """Energy mode for `Sensor`"""

    #: Low energy mode
    low = "Low"
    #: High energy mode
    high = "High"


class Sensor(HasReadableSignals, Device):
    """A demo sensor that produces a scalar value based on X and Y Movers"""

    def __init__(self, prefix: str, name=None) -> None:
        self.prefix = prefix
        # Define some signals
        self.value = EpicsSignalR(float, "Value")
        self.energy = EpicsSignalRW(Energy, "Energy")
        # Set the signals that read() etc. will read from
        self.set_readable_signals(
            read=[self.value],
            config=[self.energy],
        )
        # Goes at the end so signals are named
        self.set_name(name)

    async def connect(self, prefix: str = "", sim=False):
        # Add pv prefix to child Signals and connect them
        await connect_children(self, prefix + self.prefix, sim)


class Mover(Movable, Stoppable, HasReadableSignals, Device):
    """A demo movable that moves based on velocity"""

    def __init__(self, prefix: str, name=None) -> None:
        self.prefix = prefix
        # Define some signals
        self.setpoint = EpicsSignalRW(float, "Setpoint", wait=False)
        self.readback = EpicsSignalR(float, "Readback")
        self.velocity = EpicsSignalRW(float, "Velocity")
        self.units = EpicsSignalR(str, "Readback.EGU")
        self.precision = EpicsSignalR(int, "Readback.PREC")
        self.stop_ = EpicsSignalX("Stop.PROC", write_value=1)
        # Set the signals that read() etc. will read from
        self.set_readable_signals(
            primary=self.readback,
            config=[self.velocity, self.units],
        )
        # Goes at the end so signals are named
        self.set_name(name)

    async def connect(self, prefix: str = "", sim=False):
        await connect_children(self, prefix + self.prefix, sim)

    def set(self, new_position: float, timeout: float = None) -> AsyncStatus[float]:
        start = time.time()
        watchers: List[Callable] = []

        async def do_set():
            old_position, units, precision = await asyncio.gather(
                self.setpoint.get_value(),
                self.units.get_value(),
                self.precision.get_value(),
            )
            await self.setpoint.set(new_position)

            async for current_position in observe_value(self.readback):
                for watcher in watchers:
                    watcher(
                        name=self.name,
                        current=current_position,
                        initial=old_position,
                        target=new_position,
                        unit=units,
                        precision=precision,
                        time_elapsed=time.time() - start,
                    )
                if np.isclose(current_position, new_position):
                    break

        status = AsyncStatus(asyncio.wait_for(do_set(), timeout=timeout), watchers)
        return status

    async def stop(self, success=True):
        await self.stop_.execute()


class SampleStage(Device):
    """A demo sample stage with X and Y movables"""

    def __init__(self, prefix: str, name=None) -> None:
        self.prefix = prefix
        # Define some child Devices
        self.x = Mover("X:")
        self.y = Mover("Y:")
        # Goes at the end so signals are named
        self.set_name(name)

    async def connect(self, prefix: str = "", sim=False):
        await connect_children(self, prefix + self.prefix, sim)


def start_ioc_subprocess() -> str:
    """Start an IOC subprocess with EPICS database for sample stage and sensor
    with the same pv prefix
    """
    import atexit
    import random
    import string
    import subprocess
    import sys
    from pathlib import Path

    pv_prefix = "".join(random.choice(string.ascii_uppercase) for _ in range(12)) + ":"
    here = Path(__file__).absolute().parent
    args = [sys.executable, "-m", "epicscorelibs.ioc"]
    args += ["-m", f"P={pv_prefix}"]
    args += ["-d", str(here / "sensor.db")]
    for suff in "XY":
        args += ["-m", f"P={pv_prefix}{suff}:"]
        args += ["-d", str(here / "mover.db")]
    process = subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    atexit.register(process.communicate, "exit")
    return pv_prefix
