# Import bluesky and ophyd
import bluesky.plans as bp  # noqa
import matplotlib.pyplot as plt
from bluesky import RunEngine
from bluesky.callbacks.best_effort import BestEffortCallback
from bluesky.utils import ProgressBarManager

from ophyd import Component, Device, EpicsSignal, EpicsSignalRO
from ophyd.v2 import epicsdemo, magics
from ophyd.v2.core import DeviceCollector

# Create a run engine, with plotting and progressbar
RE = RunEngine({})
bec = BestEffortCallback()
RE.subscribe(bec)
RE.waiting_hook = ProgressBarManager()
plt.ion()

# Make magics like mov and rd work
magics.register()

# Start IOC with demo pvs in subprocess
pv_prefix = epicsdemo.start_ioc_subprocess()


# Create v1 device
class OldSensor(Device):
    energy = Component(EpicsSignal, "Energy", kind="config")
    value = Component(EpicsSignalRO, "Value", kind="hinted")


det_old = OldSensor(pv_prefix, name="det_old")

# Create v2 devices
with DeviceCollector():
    det = epicsdemo.Sensor(pv_prefix)
    samp = epicsdemo.SampleStage(pv_prefix)
