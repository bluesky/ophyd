"""Check if a missing value stops program
"""
import unittest

from ophyd import sim, Device, Component as Cpt


class TestDevice(Device):
    """Just to create a device
    """
    signal = Cpt(sim.FakeEpicsSignalRO, 'a_fake_signal')


class TestMissingReadBack(unittest.TestCase):

    def setUp(self):
        self.fake_signal = TestDevice(name = "fake_device")

    def testDescribeFail(self):
        """If readback was never set does descirbe fail?

        I guess that's a bug
        """
        # self.assertRaises(ValueError, self.fake_signal.describe)
        self.assertRaises(AssertionError, self.fake_signal.describe)

    def testDescribeAfterSet(self):
        """If the value is once set it does not fail any longer
        """
        fs = self.fake_signal
        fs.signal.sim_put(42)

if __name__ == '__main__':
    #TestDevice(name = "fake_device").describe()
    unittest.main()
