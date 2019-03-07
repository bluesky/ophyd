import pytest
import logging

from ophyd.sim import FakeEpicsSignalRO, FakeEpicsSignal
import numpy

def test_trigger_fake_signal():
    """Test that reading a simulated signal works
    """
    a_signal = FakeEpicsSignal("a_test_var", name = "a_test_signal")
    a_signal.sim_put(0.0)
    a_signal.trigger()

def test_reading_ro_signal():
    """Test that reading a simulated read only signal works

    Warning:
        Warning: that currently fails
    """
    a_signal = FakeEpicsSignalRO("a_test_var_ro", name = "a_ro_test_signal")
    a_signal.sim_put(0.0)
    a_signal.trigger()
