import os
import tempfile
import time

from bluesky import RunEngine
from bluesky.plans import count
from databroker import temp
from ophyd import Component
from ophyd.areadetector import SimDetector, HDF5Plugin, SingleTrigger
from ophyd.areadetector.filestore_mixins import (
    FileStoreHDF5,
    FileStoreIterativeWrite,
)

RE = RunEngine()
db = temp()
catalog = db.v2
RE.subscribe(db.insert)

PV_PREFIX = "13SIM1:"
# prefixes = ['13SIM1:', 'XF:31IDA-BI{Cam:Tbl}']

# Create a directory for the HDF5 file which we will cleanup at the end.
d = tempfile.TemporaryDirectory()
directory = d.name

os.makedirs(directory, exist_ok=True)

class FileWriter(HDF5Plugin, FileStoreHDF5, FileStoreIterativeWrite):

    def get_frames_per_point(self):
        # Base class uses self.num_capture and always returns 0, it seems.
        return self.parent.cam.num_images.get()

class MyDetector(SingleTrigger, SimDetector):
    hdf1 = Component(
        FileWriter,
        "HDF1:",
        write_path_template=directory,
        read_path_template=directory,
        root="/",
    )

det = MyDetector(PV_PREFIX, name="det")
det.read_attrs = ["hdf1"]
det.hdf1.read_attrs = []
det.cam.image_mode.put(1)

det.cam.acquire_time.put(0.1)
det.hdf1.warmup()
time.sleep(1)

# RE(count([det]))
# catalog[-1].primary.read()
