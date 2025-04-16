import logging

import pytest

from ophyd import Component, Device, EpicsSignal
from ophyd.signal import EpicsSignalBase
from ophyd.tests import subprocess_run_helper

logger = logging.getLogger(__name__)


def test_timeout():
    class SubSubDevice(Device):
        cpt5 = Component(EpicsSignal, "5")

    class SubDevice(Device):
        cpt4 = Component(EpicsSignal, "4")
        subsub1 = Component(SubSubDevice, "sub_")

    class MyDevice(Device):
        sub1 = Component(EpicsSignal, "1")
        sub2 = Component(SubDevice, "_")
        cpt3 = Component(EpicsSignal, "3")

    device = MyDevice("prefix:", name="dev")

    with pytest.raises(TimeoutError) as cm:
        device.wait_for_connection(timeout=1e-6)

    ex_msg = str(cm.value)
    assert "dev.sub1" in ex_msg
    assert "dev.sub2.cpt4" in ex_msg
    assert "dev.sub2.subsub1.cpt5" in ex_msg
    assert "dev.cpt3" in ex_msg
    assert "prefix:1" in ex_msg
    assert "prefix:_4" in ex_msg
    assert "prefix:_sub_5" in ex_msg
    assert "prefix:3" in ex_msg


def _test_epics_signal_base_connection_timeout():
    """
    Tests that the connection timeout is applied correctly to EpicsSignalBase.

    We mock the ensure_connected method to raise a TimeoutError if the timeout
    is less than 1.0 seconds which tests that the default connection timeout
    is applied correctly.

    We also test that the default connection timeout can be overidden by individual
    Component connection timeouts.

    NOTE: This test does NOT try to connect to a running IOC.
    """

    def mock_ensure_connected(self, *pvs, timeout=None):
        """Assume that the connection occurs in 1.0 seconds"""
        if timeout < 1.0:
            raise TimeoutError("Timeout")

    EpicsSignalBase._ensure_connected = mock_ensure_connected
    EpicsSignalBase.set_defaults(connection_timeout=1e-4)

    class MyDevice(Device):
        # Should timeout using default connection timeout
        cpt1 = Component(EpicsSignalBase, "1", lazy=True)
        # Should *not* timeout using custom connection timeout
        cpt2 = Component(EpicsSignalBase, "2", lazy=True, connection_timeout=3.0)

    # Connect to fake device
    device = MyDevice("prefix:", name="dev")
    with pytest.raises(TimeoutError):
        device.cpt1.kind = "hinted"
    device.cpt2.kind = "hinted"


def test_epics_signal_base_connection_timeout():
    """Test that the global and local connection timeouts are set correctly for EpicsSignalBase."""
    subprocess_run_helper(_test_epics_signal_base_connection_timeout, timeout=60)


def _test_device_connection_timeout():
    """
    Tests that the connection timeout is applied correctly to Device.

    We mock the connected property of the underlying EpicsSignalBase
    to raise a TimeoutError if the number of connections exceeds a limit
    which tests that the default connection timeout is applied correctly.

    We also test that the default connection timeout can be overidden by individual
    Component connection timeouts.

    NOTE: This test does NOT try to connect to a running IOC.
    """
    # Track connection property access counts
    access_counts = {}

    # How many access attempts before a connection is established
    ATTEMPTS_BEFORE_CONNECTED = 3

    def mock_connected(self):
        """Mock that returns True after N access attempts"""
        # Create a unique key for each signal instance
        key = id(self)

        # Initialize counter for this signal if not exists
        if key not in access_counts:
            access_counts[key] = 0

        # Increment the access counter
        access_counts[key] += 1

        # Return True after ATTEMPTS_BEFORE_CONNECTED attempts
        return access_counts[key] > ATTEMPTS_BEFORE_CONNECTED

    EpicsSignalBase.connected = property(mock_connected)
    # Set global timeout small enough to fail for dev1
    Device.set_defaults(connection_timeout=0.01)

    class SubDevice(Device):
        sig1 = Component(EpicsSignalBase, "sig1")
        sig2 = Component(EpicsSignalBase, "sig2")
        sig3 = Component(EpicsSignalBase, "sig3")
        sig4 = Component(EpicsSignalBase, "sig4")
        sig5 = Component(EpicsSignalBase, "sig5")

    class MyDevice(Device):
        # Should timeout using default connection timeout
        dev1 = Component(SubDevice, "dev1:", lazy=True)
        # Should *not* timeout using custom connection timeout
        dev2 = Component(SubDevice, "dev2:", lazy=True, connection_timeout=1.0)

    # Connect to fake device
    device = MyDevice("prefix:", name="dev")

    # This should fail - default timeout is too short for ATTEMPTS_BEFORE_CONNECTED checks
    with pytest.raises(TimeoutError):
        device.dev1.wait_for_connection()

    # This should succeed - we've given it enough time for ATTEMPTS_BEFORE_CONNECTED checks
    device.dev2.wait_for_connection()


def test_device_connection_timeout():
    """Test that the global and local connection timeouts are set correctly for Device."""
    subprocess_run_helper(_test_device_connection_timeout, timeout=60)
