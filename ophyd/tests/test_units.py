import threading
import unittest.mock

import pytest

import ophyd.sim
import ophyd.units


class MockCallbackHelper:
    """
    Simple helper for getting a callback, setting an event, and checking args.

    Use __call__ as the hook and inspect/verify ``mock`` or ``call_kwargs``.
    """

    def __init__(self):
        self.event = threading.Event()
        self.mock = unittest.mock.Mock()

    def __call__(self, *args, **kwargs):
        self.mock(*args, **kwargs)
        self.event.set()

    def wait(self, timeout=1.0):
        """Wait for the callback to be called."""
        self.event.wait(timeout)

    @property
    def call_kwargs(self):
        """Call keyword arguments."""
        _, kwargs = self.mock.call_args
        return kwargs


@pytest.fixture(scope="function")
def unit_conv_signal():
    orig = ophyd.sim.FakeEpicsSignal("sig", name="orig")
    assert "units" in orig.metadata_keys

    orig.sim_put(5)

    return ophyd.units.UnitConversionDerivedSignal(
        derived_from=orig,
        original_units="m",
        derived_units="mm",
        name="converted",
    )


def test_unit_conversion_signal_units(unit_conv_signal):
    assert unit_conv_signal.original_units == "m"
    assert unit_conv_signal.derived_units == "mm"
    assert unit_conv_signal.describe()[unit_conv_signal.name]["units"] == "mm"


def test_unit_conversion_signal_get_put(unit_conv_signal):
    assert unit_conv_signal.get() == 5_000
    unit_conv_signal.put(10_000, wait=True)
    assert unit_conv_signal.derived_from.get() == 10


def test_unit_conversion_signal_value_sub(unit_conv_signal):
    helper = MockCallbackHelper()
    unit_conv_signal.subscribe(helper, run=False)
    unit_conv_signal.derived_from.put(20, wait=True)
    helper.wait(1)
    helper.mock.assert_called_once()

    assert helper.call_kwargs["value"] == 20_000
    assert unit_conv_signal.get() == 20_000


def test_unit_conversion_signal_metadata_sub(unit_conv_signal):
    helper = MockCallbackHelper()
    unit_conv_signal.subscribe(helper, run=True, event_type="meta")
    helper.wait(1)
    helper.mock.assert_called_once()
    assert helper.call_kwargs["units"] == "mm"
