import asyncio
import subprocess
import sys
import time

from enum import Enum
from functools import partial, reduce
from collections import OrderedDict
from caproto.server import PVGroup, ioc_arg_parser, pvproperty, run
from ophyd import Device, DeviceStatus, EpicsSignal, EpicsSignalRO, FormattedComponent
from ophyd.array import ArrayDevice
from ophyd.ternary import TernaryDevice


class StateEnum(Enum):
    In = True
    Out = False
    Unknown = None


class TernaryDeviceSim:
    """
    A device with three states.

    Parameters
    ----------
    delay: float, optional
        The time it takes for the device to change from state-0 to state-1.
    """

    def __init__(self, delay=0.5):
        self._delay = delay
        self._state = False

    async def set(self):
        if not self._state:
            self._state = None
            await asyncio.sleep(self._delay)
            self._state = True

    async def reset(self):
        if self._state or self._state is None:
            self._state = None
            await asyncio.sleep(self._delay)
            self._state = False

    @property
    def state(self):
        return self._state


class TernaryArrayIOC(PVGroup):
    """
    Example IOC that has an array of TernaryDevices.

    Parameters
    ----------
    count: integer
        The number of devices in the array.
    """

    def __init__(self, count=10, *args, **kwargs):
        self._devices = [TernaryDeviceSim() for i in range(count)]

        # Dynamically setup the pvs.
        for i in range(count):
            # Create the set pv.
            setattr(
                self,
                f"device{i}_set",
                pvproperty(value=0, dtype=int, name=f"device{i}_set"),
            )

            # Create the set putter.
            partial_set = partial(self.set_putter, i)
            partial_set.__name__ = f"set_putter{i}"
            getattr(self, f"device{i}_set").putter(partial_set)

            # Create the reset pv.
            setattr(
                self,
                f"device{i}_reset",
                pvproperty(value=0, dtype=int, name=f"device{i}_reset"),
            )

            # Create the reset putter.
            partial_reset = partial(self.reset_putter, i)
            partial_reset.__name__ = f"reset_putter{i}"
            getattr(self, f"device{i}_reset").putter(partial_reset)

            # Create the readback pv.
            setattr(
                self,
                f"device{i}_rbv",
                pvproperty(value="Unknown", dtype=str, name=f"device{i}_rbv"),
            )

            # Create the readback scan.
            partial_scan = partial(self.general_scan, i)
            partial_scan.__name__ = f"scan{i}"
            getattr(self, f"device{i}_rbv").scan(period=0.1)(partial_scan)

        # Unfortunate hack to register the late pvs.
        self.__dict__["_pvs_"] = OrderedDict(PVGroup.find_pvproperties(self.__dict__))
        super().__init__(*args, **kwargs)

    async def set_putter(self, index, group, instance, value):
        if value:
            await self._devices[index].set()

    async def reset_putter(self, index, group, instance, value):
        if value:
            await self._devices[index].reset()

    async def general_scan(self, index, group, instance, async_lib):
        # A hacky way to write to the pv.
        await self.pvdb[f"{self.prefix}device{index}_rbv"].write(
            StateEnum(self._devices[index].state).name
        )
        # This is the normal way to do this, but it doesn't work correctly for this example.
        # await getattr(self, f'device{index}_rbv').write(StateEnum(self._devices[index].state).name)


class ExampleTernary(TernaryDevice):
    """
    This class is an example about how to create a TernaryDevice specialization
    for a specific implementation.
    """

    def __init__(self, index, *args, **kwargs):
        super().__init__(
            *args,
            name=f"Filter{index}",
            set_name=f"TernaryArray:device{index}_set",
            reset_name=f"TernaryArray:device{index}_reset",
            state_name=f"TernaryArray:device{index}_rbv",
            state_enum=StateEnum,
            **kwargs,
        )


array_device = ArrayDevice([ExampleTernary(i) for i in range(10)], name='array_device')


def start_test_ioc():
    ioc = TernaryArrayIOC(prefix='TernaryArray:')
    print("Prefix =", "TernaryArray:")
    print("PVs:", list(ioc.pvdb))
    run(ioc.pvdb)


def test_ioc(f):
    """
    Decorator that starts a test ioc using subproccess,
    calls your function and then cleans up the process.
    """
    def wrap():
        try:
            ps = subprocess.Popen([sys.executable, '-c', 'from ophyd.tests.test_array import start_test_ioc; start_test_ioc()'])
            time.sleep(5)
            f()
        finally:
            ps.kill()
    return wrap


@test_ioc
def test_arraydevice():
    arraydevice = ArrayDevice([ExampleTernary(i) for i in range(10)],
                              name='arraydevice')
    values = [1,1,1,0,0,0,1,1,1,0]
    arraydevice.set(values)
    time.sleep(1)
    print(arraydevice.get())
    assert arraydevice.get() == values
