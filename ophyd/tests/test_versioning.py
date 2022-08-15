import logging

import pytest

from ophyd import Device

logger = logging.getLogger(__name__)


def test_specify_version():
    # Define a versioned Device:
    class MyDevice(Device, version=1, version_type="ioc"):
        ...

    info = MyDevice._class_info_
    assert info == {
        "version": 1,
        "versions": {1: MyDevice},
        "version_type": "ioc",
        "version_of": MyDevice,
    }

    # Define a new version of that Device:
    class MyDevice_V2(MyDevice, version=2, version_of=MyDevice):
        ...

    info = MyDevice_V2._class_info_
    assert info == {
        "version": 2,
        "versions": {1: MyDevice, 2: MyDevice_V2},
        "version_type": "ioc",
        "version_of": MyDevice,
    }

    # Ensure that the original Device has also been updated:
    assert MyDevice._class_info_["versions"] == {1: MyDevice, 2: MyDevice_V2}

    # Define a user device that inherits - but does not define a new version
    class UserDevice(MyDevice_V2):
        ...

    assert UserDevice._class_info_ == {
        "versions": {1: MyDevice, 2: MyDevice_V2},
        "version": 2,
        "version_type": "ioc",
        "version_of": MyDevice,
    }


def test_version_requires_subclass():
    class MyDevice(Device, version=1):
        ...

    with pytest.raises(RuntimeError):

        class UnrelatedDevice(Device, version=2, version_of=MyDevice):
            ...
