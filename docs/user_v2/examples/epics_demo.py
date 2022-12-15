# Import bluesky and ophyd
import matplotlib.pyplot as plt
from bluesky import RunEngine
from bluesky.callbacks.best_effort import BestEffortCallback
from bluesky.plan_stubs import mov, movr, rd  # noqa
from bluesky.plans import grid_scan  # noqa
from bluesky.utils import ProgressBarManager, register_transform

from ophyd import Component, Device, EpicsSignal, EpicsSignalRO
from ophyd.v2 import epicsdemo
from ophyd.v2.core import DeviceCollector

# Create a run engine, with plotting, progressbar and transform
RE = RunEngine({}, call_returns_result=True)
bec = BestEffortCallback()
RE.subscribe(bec)
RE.waiting_hook = ProgressBarManager()
plt.ion()
register_transform("RE", prefix="<")

# Start IOC with demo pvs in subprocess
pv_prefix = epicsdemo.start_ioc_subprocess()


# Create v1 device
class OldSensor(Device):
    mode = Component(EpicsSignal, "Mode", kind="config")
    value = Component(EpicsSignalRO, "Value", kind="hinted")


det_old = OldSensor(pv_prefix, name="det_old")

# Create v2 devices
with DeviceCollector():
    det = epicsdemo.Sensor(pv_prefix)
    samp = epicsdemo.SampleStage(pv_prefix)
