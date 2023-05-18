from functools import reduce
from ophyd import Device, DeviceStatus


def ArrayDevice(devices, *args, **kwargs):
    """
    A function, that behaves like a class init, that dynamically creates an
    ArrayDevice class. This is needed to set class attributes before the init.
    Adding devices in the init can subvert important ophyd code that
    manages sub devices.

    Parameters
    ----------
    devices: interable
        An iterable of devices with the same type.

    Example
    -------
    array_device = ArrayDevice([ExampleTernary(i) for i in range(10)], name='array_device')
    """

    class _ArrayDeviceBase(Device):
        """
        An ophyd.Device that is an array of devices.

        The set method takes a list of values.
        the get method returns a list of values.
        Parameters
        ----------
        devices: iterable
            The array of ophyd devices.
        """
        def set(self, values):
            if len(values) != len(self.devices):
                raise ValueError(
                    f"The number of values ({len(values)}) must match "
                    f"the number of devices ({len(self.devices)})"
                )

            # If the device already has the requested state, return a finished status.
            diff = [self.devices[i].get() != value for i, value in enumerate(values)]
            if not any(diff):
                return DeviceStatus(self)._finished()

            # Set the value of each device and return a union of the statuses.
            statuses = [self.devices[i].set(value) for i, value in enumerate(values)]
            st = reduce(lambda a, b: a & b, statuses)
            return st

        def reset(self):
            self.set([0 for i in range(len(self.devices))])

        def get(self):
            return [device.get() for device in self.devices]

    types = {type(device) for device in devices}
    if len(types) != 1:
        raise TypeError("All devices must have the same type")

    _ArrayDevice = type('ArrayDevice', (_ArrayDeviceBase,), {'devices': devices})
    return _ArrayDevice(*args, **kwargs)
