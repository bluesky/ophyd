import time
import threading

from ophyd.device import Device
from ophyd.status import DeviceStatus


class BusyStatus(DeviceStatus):
    """
    A "busy" device that takes a fixed amount of time in seconds to report complete.

    The clock starts as soon as the device is created (so do not hold onto these things!)

    Parameters
    ----------
    device : Device
        This object this status object belongs to

    delay : float
        Total delay in seconds

    tick : float, default=0.1
        Time between updating the

    """

    def __init__(self, device, delay, *, tick=0.1, **kwargs):
        super().__init__(device, **kwargs)
        start = time.monotonic()
        deadline = start + delay

        def busy_status_loop():
            current = time.monotonic()
            while current < deadline:
                elapsed = current - start
                for w in self._watchers:
                    w(
                        name=self.device.name,
                        curent=elapsed,
                        initial=0,
                        target=delay,
                        units="s",
                        fraction=(1 - elapsed / delay),
                        time_elapsed=elapsed,
                        time_remaining=delay - elapsed,
                    )
                time.sleep(tick)
                current = time.monotonic()
            w(
                name=self.device.name,
                curent=delay,
                initial=0,
                target=delay,
                unit="s",
                fraction=0,
                time_elapsed=current - start,
                time_remaining=0,
            )
            self.set_finished()

        threading.Thread(target=busy_status_loop).start()


class Busy(Device):
    """
    A "busy" device that takes a fixed amount of time in seconds to report complete.


    """

    def set(self, delay):
        return BusyStatus(self, delay, tick=max(1, min(0.1, delay / 100)))
